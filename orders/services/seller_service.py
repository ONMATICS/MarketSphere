from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from admin_panel.checkout import get_checkout_settings
from notifications.emails.orders import (
    send_order_confirmed_email,
    send_order_shipped_email,
)
from notifications.models import ActivityLog, Notification
from notifications.services.notifications import schedule_notification
from orders.models import Order

from .email_service import _send_cancelled_emails, _send_delivered_emails


def get_user_order_for_seller(seller: Any, order_number: str) -> Order:
    """Retrieve an order specifically scoped to the assigned seller."""
    return get_object_or_404(
        Order.objects.select_related("user", "seller")
        .prefetch_related("items", "items__product", "items__product__images"),
        seller=seller,
        order_number=order_number,
    )


def get_seller_orders(seller: Any) -> QuerySet[Order]:
    """Return all orders fulfilled by a specific seller."""
    return (
        Order.objects.filter(seller=seller)
        .select_related("user")
        .prefetch_related("items", "items__product")
        .order_by("-created_at")
    )


@transaction.atomic
def update_order_status(seller: Any, order_number: str, status: str) -> int:
    """Advance the fulfillment status of a specific order."""
    order = Order.objects.select_for_update().filter(order_number=order_number, seller=seller).first()
    if not order or status == order.status:
        return 0

    update_fields = {"status": status, "updated_at": timezone.now()}
    
    if status == Order.Status.SHIPPED:
        update_fields["shipped_at"] = timezone.now()
    elif status == Order.Status.DELIVERED:
        if order.payment_status == Order.PaymentStatus.UNPAID:
            update_fields["payment_status"] = Order.PaymentStatus.PAID
        update_fields["delivered_at"] = timezone.now()

    for field, value in update_fields.items():
        setattr(order, field, value)
    
    order.save(update_fields=list(update_fields.keys()))

    seller_url = reverse("order-detail", kwargs={"order_no": order.order_number})
    notification_type = getattr(Notification.NotificationType, f"ORDER_{status.upper()}", None)

    if notification_type and status in {
        Order.Status.CONFIRMED, Order.Status.SHIPPED, Order.Status.DELIVERED, Order.Status.CANCELLED,
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

        if status in {Order.Status.DELIVERED, Order.Status.CANCELLED}:
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
        transaction.on_commit(lambda: send_order_confirmed_email(order), robust=True)
    elif status == Order.Status.SHIPPED:
        transaction.on_commit(lambda: send_order_shipped_email(order), robust=True)
    elif status == Order.Status.DELIVERED:
        transaction.on_commit(lambda: _send_delivered_emails(order), robust=True)
    elif status == Order.Status.CANCELLED:
        transaction.on_commit(lambda: _send_cancelled_emails(order), robust=True)

    return 1


def update_seller_note(seller: Any, order_number: str, note: str) -> bool:
    """Save an internal seller note to an order, honoring checkout configuration."""
    if not get_checkout_settings().allow_seller_notes:
        return False

    order = Order.objects.filter(order_number=order_number, seller=seller).first()
    if order:
        order.seller_notes = note
        order.save(update_fields=['seller_notes'])
        return True

    return False


def update_shipping_information(order: Order, data: dict[str, Any]) -> Order:
    """Update courier and tracking metadata on a given order."""
    order.courier = data.get("courier", "").strip()
    order.tracking_number = data.get("tracking_number", "").strip()

    eta = data.get("estimated_delivery")
    order.estimated_delivery = parse_date(eta) if eta else None
    order.shipping_notes = data.get("shipping_notes", "").strip()

    order.save(update_fields=[
        "courier", "tracking_number", "estimated_delivery", "shipping_notes", "updated_at",
    ])

    return order