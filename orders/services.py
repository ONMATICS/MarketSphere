from collections import defaultdict
import logging
import re
from decimal import Decimal
from uuid import uuid4
from calendar import monthrange
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Prefetch, Sum, Count, F, Q, IntegerField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import Address
from products.models import CartItem, Product
from products.services import get_or_create_cart, get_cart_item_pricing
from admin_panel.marketplace import get_marketplace_settings
from admin_panel.checkout import get_checkout_settings

from .models import Order, OrderItem
from notifications.emails.orders import (
    send_order_placed_email,
    send_order_confirmed_email,
    send_order_delivered_email,
    send_order_shipped_email,
    send_order_cancelled_email,
)
from notifications.emails.sellers import (
    send_new_order_email,
    send_cancelled_order_email,
    send_delivered_order_email,
)
CANCELABLE_ORDER_STATUSES = (
    Order.Status.PENDING,
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
)


def _format_order_number(order_format):
    """Expand the configured order number format into a concrete value."""
    value = order_format or "MS-{YYYY}{#####}"
    value = value.replace("{YYYY}", timezone.localtime().strftime("%Y"))

    def replace_sequence(match):
        length = len(match.group(1))
        return str(uuid4().int)[-length:].zfill(length)

    return re.sub(r"\{(#+)\}", replace_sequence, value)[:64]


def _new_order_number(order_format):
    for _ in range(5):
        order_number = _format_order_number(order_format)
        if not Order.objects.filter(order_number=order_number).exists():
            return order_number
    return uuid4().hex[:12].upper()

from notifications.models import ActivityLog, Notification
from notifications.services.notifications import (
    schedule_low_stock_event,
    schedule_notification,
)

logger = logging.getLogger(__name__)


def _send_order_created_emails(order):
    for sender in (send_order_placed_email, send_new_order_email):
        try:
            sender(order)
        except Exception:
            logger.exception("Order-created email failed for %s", order.order_number)


def _send_cancelled_emails(order):
    reason = getattr(order, "cancellation_reason", None)
    for sender in (send_order_cancelled_email, send_cancelled_order_email):
        try:
            sender(order, reason)
        except Exception:
            logger.exception("Order-cancelled email failed for %s", order.order_number)


def _send_delivered_emails(order):
    for sender in (send_order_delivered_email, send_delivered_order_email):
        try:
            sender(order)
        except Exception:
            logger.exception("Order-delivered email failed for %s", order.order_number)

from accounts.models import Address

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse

from accounts.models import Address, SellerSettings
from products.models import Product
from orders.models import Order, OrderItem
from products.models import CartItem, Cart
from notifications.models import Notification, ActivityLog


@transaction.atomic
def place_order(
    user,
    address_id,
    full_name=None,
    email=None,
    phone=None,
    notes="",
    cart_item_id=None,
):
    cart_items_qs = (
        CartItem.objects
        .select_related(
            "product",
            "product__seller",
            "cart",
            "promotion_product__promotion",
        )
        .filter(cart__user=user)
        .select_for_update()
    )

    if cart_item_id is not None:
        cart_items_qs = cart_items_qs.filter(id=cart_item_id)

    cart_items = list(cart_items_qs)

    if not cart_items:
        if cart_item_id is not None:
            raise ValueError(
                "The selected cart item could not be found."
            )

        raise ValueError("Your cart is empty.")

    marketplace_settings = get_marketplace_settings()
    checkout_settings = get_checkout_settings()

    seller_ids = {
        item.product.seller_id
        for item in cart_items
    }

    if (
        (
            not marketplace_settings.multi_seller_orders
            or not checkout_settings.split_orders
        )
        and len(seller_ids) > 1
    ):
        raise ValueError(
            "Orders containing products from multiple sellers "
            "are currently unavailable."
        )

    if (
        checkout_settings.require_email
        and not (email or getattr(user, "email", ""))
    ):
        raise ValueError(
            "An email address is required to place an order."
        )

    address = get_object_or_404(
        Address,
        id=address_id,
        user=user,
    )

    full_name = (
        full_name
        or f"{user.first_name} {user.last_name}".strip()
        or user.username
    )

    email = email or user.email
    phone = phone or address.phone or user.contact

    if checkout_settings.require_phone and not phone:
        raise ValueError(
            "A phone number is required to place an order."
        )

    items_by_seller = defaultdict(list)

    for item in cart_items:
        if item.product.seller_id is None:
            raise ValueError(
                f"'{item.product.name}' has no seller assigned "
                "and cannot be ordered."
            )

        items_by_seller[item.product.seller_id].append(item)

    created_orders = []

    for seller_id, items in items_by_seller.items():

        order_subtotal = Decimal("0.00")
        order_discount = Decimal("0.00")

        pending_order_items = []

        order = Order.objects.create(
            user=user,
            seller_id=seller_id,
            order_number=_new_order_number(
                checkout_settings.order_number_format
            ),
            status=(
                Order.Status.CONFIRMED
                if checkout_settings.auto_confirm_orders
                else Order.Status.PENDING
            ),
            shipping_name=full_name,
            shipping_phone=phone,
            shipping_address=address.address_line_1,
            shipping_city=address.city,
            shipping_postal_code=address.postal_code,
            buyer_notes=(
                notes
                if checkout_settings.allow_order_notes
                else ""
            ),
        )

        for item in items:

            product = (
                Product.objects
                .select_for_update()
                .select_related("seller")
                .get(pk=item.product_id)
            )

            item.product = product

            pricing = get_cart_item_pricing(item)

            price = pricing["effective_price"]

            if (
                product.status != Product.Status.PUBLISHED
                or not product.seller
                or product.seller.status
                != product.seller.Status.VERIFIED
            ):
                raise ValueError(
                    f"'{product.name}' is no longer available "
                    "for purchase."
                )

            if (
                product.stock_quantity < item.quantity
                and not checkout_settings.backorders
            ):
                raise ValueError(
                    f"Only {product.stock_quantity} units of "
                    f"'{product.name}' are available."
                )

            item_total = pricing["line_subtotal"]

            order_subtotal += (
                pricing["original_price"]
                if pricing["is_promotion"]
                else pricing["effective_price"]
            ) * item.quantity

            order_discount += pricing["discount_amount"]

            previous_stock = product.stock_quantity

            product.stock_quantity = max(
                0,
                product.stock_quantity - item.quantity,
            )

            product.status = (
                Product.Status.OUT_OF_STOCK
                if product.stock_quantity == 0
                else Product.Status.PUBLISHED
            )

            product.save(
                update_fields=[
                    "stock_quantity",
                    "status",
                ]
            )

            schedule_low_stock_event(
                product,
                previous_stock,
                product.stock_quantity,
            )

            pending_order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    price=price,
                    quantity=item.quantity,
                    total=item_total,
                )
            )

        if order_subtotal < checkout_settings.min_checkout_amount:
            raise ValueError(
                f"The minimum checkout amount is "
                f"{checkout_settings.min_checkout_amount}."
            )

        if (
            marketplace_settings.max_order_amount
            and order_subtotal
            > marketplace_settings.max_order_amount
        ):
            raise ValueError(
                f"The maximum checkout amount is "
                f"{marketplace_settings.max_order_amount}."
            )

        OrderItem.objects.bulk_create(
            pending_order_items
        )

        # ---------------------------------------------------------
        # SHIPPING
        # ---------------------------------------------------------

        seller_settings = (
            SellerSettings.objects
            .filter(seller_id=seller_id)
            .first()
        )

        shipping_cost = Decimal("0.00")

        if seller_settings:
            shipping_cost = (
                seller_settings.shipping_fee
                or Decimal("0.00")
            )

        # ---------------------------------------------------------
        # TOTALS
        # ---------------------------------------------------------

        tax = Decimal("0.00")
        discount = order_discount

        total = (
            order_subtotal
            + shipping_cost
            + tax
            - discount
        )

        order.subtotal = order_subtotal
        order.shipping_cost = shipping_cost
        order.discount = discount
        order.tax = tax
        order.total = total

        order.save(
            update_fields=[
                "subtotal",
                "shipping_cost",
                "discount",
                "tax",
                "total",
            ]
        )

        created_orders.append(order)

        seller = order.seller

        schedule_notification(
            user_id=user.id,
            notification_type=(
                Notification.NotificationType.ORDER_CREATED
            ),
            title="Order placed successfully",
            message=(
                f"Your order #{order.order_number} "
                "has been placed successfully."
            ),
            audience=Notification.Audience.BUYER,
            icon="bi-bag-check",
            target_url=reverse(
                "order",
                kwargs={
                    "order_number": order.order_number
                },
            ),
            activity=True,
            activity_category=ActivityLog.Category.ORDER,
            activity_action="ORDER_CREATED",
            activity_title="Order placed",
            activity_description=(
                f"Order #{order.order_number} was placed."
            ),
            activity_actor=user,
            activity_actor_type=(
                ActivityLog.ActorType.BUYER
            ),
            activity_target=order,
            activity_metadata={
                "order_number": order.order_number
            },
        )

        schedule_notification(
            user_id=seller.user_id,
            notification_type=(
                Notification.NotificationType.ORDER_CREATED
            ),
            title="New order needs attention",
            message=(
                f"You received a new order "
                f"#{order.order_number} "
                f"worth {order.total}."
            ),
            audience=Notification.Audience.SELLER,
            icon="bi-bag-check",
            target_url=reverse(
                "order-detail",
                kwargs={
                    "order_no": order.order_number
                },
            ),
        )

        transaction.on_commit(
            lambda order=order: _send_order_created_emails(order),
            robust=True,
        )

    # Delete only the cart items that were actually ordered.
    CartItem.objects.filter(
        id__in=[item.id for item in cart_items]
    ).delete()

    return created_orders

def get_user_orders(user):
    return (
        Order.objects.filter(user=user)
        .select_related("seller")
        .prefetch_related("items__product")
        .annotate(total_items=Sum("items__quantity"))
        .order_by("-created_at")
    )


def get_user_order(user, order_number):
    return get_object_or_404(
        Order.objects.select_related("seller").prefetch_related("items__product"),
        order_number=order_number,
        user=user,
    )


@transaction.atomic
def cancel_user_order(user, order_number):
    checkout_settings = get_checkout_settings()
    if not checkout_settings.allow_cancellation:
        return False

    order = get_user_order(user, order_number)

    if order.status not in CANCELABLE_ORDER_STATUSES:
        return False

    cancellation_window = checkout_settings.cancellation_window
    if (
        cancellation_window <= 0
        or timezone.now() > order.created_at + timedelta(hours=cancellation_window)
    ):
        return False

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    schedule_notification(
        user_id=order.seller.user_id,
        notification_type=Notification.NotificationType.ORDER_CANCELLED,
        title="Order cancelled",
        message=f"Order #{order.order_number} has been cancelled.",
        icon="bi-x-circle",
        audience=Notification.Audience.SELLER,
        target_url=reverse("order-detail", kwargs={"order_no": order.order_number}),
        activity=True,
        activity_category=ActivityLog.Category.ORDER,
        activity_action="ORDER_CANCELLED",
        activity_title="Order cancelled",
        activity_description=f"Order #{order.order_number} was cancelled.",
        activity_actor=user,
        activity_actor_type=ActivityLog.ActorType.BUYER,
        activity_target=order,
        activity_metadata={"order_number": order.order_number},
    )
    transaction.on_commit(
        lambda order=order: _send_cancelled_emails(order),
        robust=True,
    )
    return True


def add_to_cart(user, product, quantity=1):
    cart = get_or_create_cart(user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": quantity},
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save(update_fields=["quantity", "updated_at"])

    return cart_item


def reorder_user_order(user, order_number):
    order = get_user_order(user, order_number)

    if order.status != Order.Status.DELIVERED:
        return None

    for item in order.items.select_related("product"):
        add_to_cart(
            user=user,
            product=item.product,
            quantity=item.quantity,
        )

    return order


def get_user_order_for_seller(seller, order_number):
    return get_object_or_404(
        Order.objects.select_related(
            "user",
            "seller",
        ).prefetch_related(
            "items",
            "items__product",
            "items__product__images",
        ),
        seller=seller,
        order_number=order_number,
    )


def get_seller_orders(seller):
    """
    Returns all orders belonging to a specific seller.
    """
    return (
        Order.objects.filter(seller=seller)
        .select_related("user")
        .prefetch_related(
            "items",
            "items__product",
        )
        .order_by("-created_at")
    )


def _percentage_change(current, previous):
    if previous == 0:
        if current == 0:
            return 0
        return 100

    return round(((current - previous) / previous) * 100, 1)


def get_admin_order_stats():
    now = timezone.localtime()

    current_month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    if current_month_start.month == 1:
        previous_month_start = current_month_start.replace(
            year=current_month_start.year - 1,
            month=12,
        )
    else:
        previous_month_start = current_month_start.replace(
            month=current_month_start.month - 1,
        )

    current_month_end = now

    orders = Order.objects.all()

    current_orders = orders.filter(
        created_at__gte=current_month_start,
        created_at__lte=current_month_end,
    )

    previous_orders = orders.filter(
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    )

    pending_orders = orders.filter(status=Order.Status.PENDING).count()
    processing_orders = orders.filter(status=Order.Status.PROCESSING).count()
    delivered_orders = orders.filter(status=Order.Status.DELIVERED).count()

    current_pending_orders = current_orders.filter(status=Order.Status.PENDING).count()
    previous_pending_orders = previous_orders.filter(status=Order.Status.PENDING).count()

    current_processing_orders = current_orders.filter(status=Order.Status.PROCESSING).count()
    previous_processing_orders = previous_orders.filter(status=Order.Status.PROCESSING).count()

    current_delivered_orders = current_orders.filter(status=Order.Status.DELIVERED).count()
    previous_delivered_orders = previous_orders.filter(status=Order.Status.DELIVERED).count()

    total_revenue = orders.filter(
        status=Order.Status.DELIVERED
    ).aggregate(
        total=Sum("total")
    )["total"] or Decimal("0.00")

    current_revenue = current_orders.filter(
        status=Order.Status.DELIVERED
    ).aggregate(
        total=Sum("total")
    )["total"] or Decimal("0.00")

    previous_revenue = previous_orders.filter(
        status=Order.Status.DELIVERED
    ).aggregate(
        total=Sum("total")
    )["total"] or Decimal("0.00")

    pending_change = _percentage_change(current_pending_orders, previous_pending_orders)
    processing_change = _percentage_change(current_processing_orders, previous_processing_orders)
    delivered_change = _percentage_change(current_delivered_orders, previous_delivered_orders)
    revenue_change = _percentage_change(current_revenue, previous_revenue)

    return {
        "pending_orders": pending_orders,
        "pending_orders_change": abs(pending_change),
        "pending_orders_increased": pending_change >= 0,

        "processing_orders": processing_orders,
        "processing_orders_change": abs(processing_change),
        "processing_orders_increased": processing_change >= 0,

        "delivered_orders": delivered_orders,
        "delivered_orders_change": abs(delivered_change),
        "delivered_orders_increased": delivered_change >= 0,

        "total_revenue": total_revenue,
        "revenue_change": abs(revenue_change),
        "revenue_increased": revenue_change >= 0,
    }


def get_admin_orders():
    return (
        Order.objects
        .select_related("user", "seller")
        .prefetch_related(
            "items",
            "items__product",
        )
        .order_by("-created_at")
    )


@transaction.atomic
def update_order_status(seller, order_number, status):
    order = Order.objects.select_for_update().filter(
        order_number=order_number, seller=seller,
    ).first()
    if not order or status == order.status:
        return 0

    update_fields = {"status": status, "updated_at": timezone.now()}
    if status == Order.Status.SHIPPED: 
        update_fields["shipped_at"] = timezone.now() 
    elif status == Order.Status.DELIVERED: 
        update_fields["delivered_at"] = timezone.now() 
    for field, value in update_fields.items():
        setattr(order, field, value)
    order.save(update_fields=list(update_fields))

    seller_url = reverse("order-detail", kwargs={"order_no": order.order_number})
    notification_type = getattr(
        Notification.NotificationType,
        f"ORDER_{status.upper()}",
        None,
    )
    if notification_type and status in {
        Order.Status.CONFIRMED,
        Order.Status.SHIPPED,
        Order.Status.DELIVERED,
        Order.Status.CANCELLED,
    }:
        status_display = order.get_status_display().lower()
        schedule_notification(
            user_id=order.user_id,
            notification_type=notification_type,
            title=f"Order {status_display}",
            message=f"Order #{order.order_number} is now {status_display}.",
            icon="bi-box-seam",
            target_url=reverse("order", kwargs={"order_number": order.order_number}),
            audience=Notification.Audience.BUYER,
            activity=True,
            activity_category=ActivityLog.Category.ORDER,
            activity_action=f"ORDER_{status.upper()}",
            activity_title=f"Order {status_display}",
            activity_description=f"Order #{order.order_number} is now {status_display}.",
            activity_actor=seller.user,
            activity_actor_type=ActivityLog.ActorType.SELLER,
            activity_target=order,
            activity_metadata={"order_number": order.order_number, "status": status},
        )
        if notification_type and status in {
                Order.Status.DELIVERED,
                Order.Status.CANCELLED,
            }:
            schedule_notification(
                user_id=order.seller.user_id,
                notification_type=notification_type,
                title=f"Order {status_display}",
                message=f"Order #{order.order_number} is now {status_display}.",
                icon="bi-box-seam",
                target_url=seller_url,
                audience=Notification.Audience.SELLER,
            )

    if status == Order.Status.CONFIRMED:
        transaction.on_commit(
            lambda: send_order_confirmed_email(order),
            robust=True,
        )

    elif status == Order.Status.SHIPPED:
        transaction.on_commit(
            lambda: send_order_shipped_email(order),
            robust=True,
        )

    elif status == Order.Status.DELIVERED:
        transaction.on_commit(
            lambda: _send_delivered_emails(order),
            robust=True,
        )

    elif status == Order.Status.CANCELLED:
        transaction.on_commit(
            lambda: _send_cancelled_emails(order),
            robust=True,
        )

    return 1

def update_seller_note(seller, order_number, note):
    if not get_checkout_settings().allow_seller_notes:
        return False

    order = Order.objects.filter(
        order_number=order_number, 
        seller=seller
    ).first()

    if order:
        order.seller_notes = note
        order.save(update_fields=['seller_notes'])
        return True
        
    return False


def update_shipping_information(order, data):
    order.courier = data.get("courier", "").strip()
    order.tracking_number = data.get("tracking_number", "").strip()

    eta = data.get("estimated_delivery")
    if eta:
        order.estimated_delivery = parse_date(eta)
    else:
        order.estimated_delivery = None

    order.shipping_notes = data.get("shipping_notes", "").strip()

    order.save(
        update_fields=[
            "courier",
            "tracking_number",
            "estimated_delivery",
            "shipping_notes",
            "updated_at",
        ]
    )

    return order
