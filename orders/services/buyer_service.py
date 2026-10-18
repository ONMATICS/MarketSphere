from datetime import timedelta
from typing import Any

from django.db import transaction
from django.db.models import QuerySet, Sum
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from admin_panel.checkout import get_checkout_settings
from notifications.models import ActivityLog, Notification
from notifications.services.notifications import schedule_notification
from orders.models import Order

from .email_service import _send_cancelled_emails


CANCELABLE_ORDER_STATUSES = (
    Order.Status.PENDING,
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
)


def get_user_orders(user: Any) -> QuerySet[Order]:
    """Retrieve all base orders placed by the specified user."""
    return (
        Order.objects.filter(user=user)
        .select_related("seller")
        .prefetch_related("items__product")
        .annotate(total_items=Sum("items__quantity"))
        .order_by("-created_at")
    )


def get_user_order(user: Any, order_number: str) -> Order:
    """Retrieve a specific order tied to a user."""
    return get_object_or_404(
        Order.objects.select_related("seller").prefetch_related("items__product"),
        order_number=order_number,
        user=user,
    )


@transaction.atomic
def cancel_user_order(user: Any, order_number: str) -> bool:
    """Cancel an active user order if it falls within the cancellation policies."""
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

    transaction.on_commit(lambda order=order: _send_cancelled_emails(order), robust=True)
    return True