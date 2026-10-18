import re
from collections import defaultdict
from decimal import Decimal
from typing import Any
from uuid import uuid4

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from accounts.models import Address, SellerSettings
from admin_panel.checkout import get_checkout_settings
from admin_panel.marketplace import get_marketplace_settings
from notifications.models import ActivityLog, Notification
from notifications.services.notifications import (
    schedule_low_stock_event,
    schedule_notification,
)
from orders.models import Order, OrderItem
from products.models import CartItem, Product
from products.services import get_cart_item_pricing

from .email_service import _send_order_created_emails


def _format_order_number(order_format: str | None) -> str:
    """Expand the configured order number format into a concrete value."""
    value = order_format or "MS-{YYYY}{#####}"
    value = value.replace("{YYYY}", timezone.localtime().strftime("%Y"))

    def replace_sequence(match: re.Match) -> str:
        length = len(match.group(1))
        return str(uuid4().int)[-length:].zfill(length)

    return re.sub(r"\{(#+)\}", replace_sequence, value)[:64]


def _new_order_number(order_format: str | None) -> str:
    """Generate a unique order number based on the format configuration."""
    for _ in range(5):
        order_number = _format_order_number(order_format)
        if not Order.objects.filter(order_number=order_number).exists():
            return order_number
    return uuid4().hex[:12].upper()


@transaction.atomic
def place_order(
    user: Any,
    address_id: int | str,
    full_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    notes: str = "",
    cart_item_id: int | str | None = None,
) -> list[Order]:
    """Process a user's cart to generate and place distinct orders by seller."""
    cart_items_qs = (
        CartItem.objects.select_related(
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
            raise ValueError("The selected cart item could not be found.")
        raise ValueError("Your cart is empty.")

    marketplace_settings = get_marketplace_settings()
    checkout_settings = get_checkout_settings()

    seller_ids = {item.product.seller_id for item in cart_items}

    if (
        not marketplace_settings.multi_seller_orders
        or not checkout_settings.split_orders
    ) and len(seller_ids) > 1:
        raise ValueError("Orders containing products from multiple sellers are currently unavailable.")

    if checkout_settings.require_email and not (email or getattr(user, "email", "")):
        raise ValueError("An email address is required to place an order.")

    address = get_object_or_404(Address, id=address_id, user=user)
    full_name = full_name or f"{user.first_name} {user.last_name}".strip() or user.username
    email = email or user.email
    phone = phone or address.phone or user.contact

    if checkout_settings.require_phone and not phone:
        raise ValueError("A phone number is required to place an order.")

    items_by_seller = defaultdict(list)
    for item in cart_items:
        if item.product.seller_id is None:
            raise ValueError(f"'{item.product.name}' has no seller assigned and cannot be ordered.")
        items_by_seller[item.product.seller_id].append(item)

    created_orders = []

    for seller_id, items in items_by_seller.items():
        order_subtotal = Decimal("0.00")
        order_discount = Decimal("0.00")
        pending_order_items = []

        order = Order.objects.create(
            user=user,
            seller_id=seller_id,
            order_number=_new_order_number(checkout_settings.order_number_format),
            status=(
                Order.Status.CONFIRMED if checkout_settings.auto_confirm_orders else Order.Status.PENDING
            ),
            shipping_name=full_name,
            shipping_phone=phone,
            shipping_address=address.address_line_1,
            shipping_city=address.city,
            shipping_postal_code=address.postal_code,
            buyer_notes=(notes if checkout_settings.allow_order_notes else ""),
        )

        for item in items:
            product = (
                Product.objects.select_for_update()
                .select_related("seller")
                .get(pk=item.product_id)
            )
            item.product = product
            pricing = get_cart_item_pricing(item)
            price = pricing["effective_price"]

            if (
                product.status != Product.Status.PUBLISHED
                or not product.seller
                or product.seller.status != product.seller.Status.VERIFIED
            ):
                raise ValueError(f"'{product.name}' is no longer available for purchase.")

            if product.stock_quantity < item.quantity and not checkout_settings.backorders:
                raise ValueError(f"Only {product.stock_quantity} units of '{product.name}' are available.")

            item_total = pricing["line_subtotal"]
            order_subtotal += (
                pricing["original_price"] if pricing["is_promotion"] else pricing["effective_price"]
            ) * item.quantity
            order_discount += pricing["discount_amount"]

            previous_stock = product.stock_quantity
            product.stock_quantity = max(0, product.stock_quantity - item.quantity)
            product.status = (
                Product.Status.OUT_OF_STOCK if product.stock_quantity == 0 else Product.Status.PUBLISHED
            )
            product.save(update_fields=["stock_quantity", "status"])

            schedule_low_stock_event(product, previous_stock, product.stock_quantity)

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
            raise ValueError(f"The minimum checkout amount is {checkout_settings.min_checkout_amount}.")

        if (
            marketplace_settings.max_order_amount
            and order_subtotal > marketplace_settings.max_order_amount
        ):
            raise ValueError(f"The maximum checkout amount is {marketplace_settings.max_order_amount}.")

        OrderItem.objects.bulk_create(pending_order_items)

        seller_settings = SellerSettings.objects.filter(seller_id=seller_id).first()
        shipping_cost = seller_settings.shipping_fee if seller_settings and seller_settings.shipping_fee else Decimal("0.00")
        tax = Decimal("0.00")
        discount = order_discount
        total = order_subtotal + shipping_cost + tax - discount

        order.subtotal = order_subtotal
        order.shipping_cost = shipping_cost
        order.discount = discount
        order.tax = tax
        order.total = total
        order.save(update_fields=["subtotal", "shipping_cost", "discount", "tax", "total"])

        created_orders.append(order)
        seller = order.seller

        schedule_notification(
            user_id=user.id,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="Order placed successfully",
            message=f"Your order #{order.order_number} has been placed successfully.",
            audience=Notification.Audience.BUYER,
            icon="bi-bag-check",
            target_url=reverse("order", kwargs={"order_number": order.order_number}),
            activity=True,
            activity_category=ActivityLog.Category.ORDER,
            activity_action="ORDER_CREATED",
            activity_title="Order placed",
            activity_description=f"Order #{order.order_number} was placed.",
            activity_actor=user,
            activity_actor_type=ActivityLog.ActorType.BUYER,
            activity_target=order,
            activity_metadata={"order_number": order.order_number},
        )

        schedule_notification(
            user_id=seller.user_id,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="New order needs attention",
            message=f"You received a new order #{order.order_number} worth {order.total}.",
            audience=Notification.Audience.SELLER,
            icon="bi-bag-check",
            target_url=reverse("order-detail", kwargs={"order_no": order.order_number}),
        )

        transaction.on_commit(lambda order=order: _send_order_created_emails(order), robust=True)

    CartItem.objects.filter(id__in=[item.id for item in cart_items]).delete()

    return created_orders