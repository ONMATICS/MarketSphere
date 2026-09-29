from django.conf import settings
from django.urls import reverse

from notifications.services.email import send_marketplace_email
from admin_panel.notification_settings import notification_channel_enabled


def _get_absolute_url(path):
    return f"{settings.SITE_URL.rstrip('/')}/{path.lstrip('/')}"


def _get_order_url(order):
    path = reverse(
        "order",
        kwargs={"order_number": order.order_number},
    )

    return _get_absolute_url(path)


def send_order_placed_email(order):
    buyer = order.user

    if not buyer.email or not notification_channel_enabled("ORDER_CREATED", "BUYER", "email"):
        return False

    return send_marketplace_email(
        subject="Your Order Has Been Placed — MarketSphere",
        recipient=buyer.email,
        template="email_management/orders/placed.html",
        context={
            "recipient_name": buyer.first_name or buyer.username,
            "order": order,
            "order_url": _get_order_url(order),
        },
    )


def send_order_confirmed_email(order):
    buyer = order.user

    if not buyer.email or not notification_channel_enabled("ORDER_CONFIRMED", "BUYER", "email"):
        return False

    return send_marketplace_email(
        subject="Your Order Has Been Confirmed — MarketSphere",
        recipient=buyer.email,
        template="email_management/orders/confirmed.html",
        context={
            "recipient_name": buyer.first_name or buyer.username,
            "order": order,
            "order_url": _get_order_url(order),
        },
    )


def send_order_shipped_email(order):
    buyer = order.user

    if not buyer.email or not notification_channel_enabled("ORDER_SHIPPED", "BUYER", "email"):
        return False

    return send_marketplace_email(
        subject="Your Order Is On Its Way — MarketSphere",
        recipient=buyer.email,
        template="email_management/orders/shipped.html",
        context={
            "recipient_name": buyer.first_name or buyer.username,
            "order": order,
            "order_url": _get_order_url(order),
        },
    )


def send_order_delivered_email(order):
    buyer = order.user

    if not buyer.email or not notification_channel_enabled("ORDER_DELIVERED", "BUYER", "email"):
        return False

    return send_marketplace_email(
        subject="Your Order Has Been Delivered — MarketSphere",
        recipient=buyer.email,
        template="email_management/orders/delivered.html",
        context={
            "recipient_name": buyer.first_name or buyer.username,
            "order": order,
            "order_url": _get_order_url(order),
        },
    )


def send_order_cancelled_email(order, cancellation_reason=None):
    buyer = order.user

    if not buyer.email or not notification_channel_enabled("ORDER_CANCELLED", "BUYER", "email"):
        return False

    return send_marketplace_email(
        subject="Your Order Has Been Cancelled — MarketSphere",
        recipient=buyer.email,
        template="email_management/orders/cancelled.html",
        context={
            "recipient_name": buyer.first_name or buyer.username,
            "order": order,
            "cancellation_reason": cancellation_reason,
            "order_url": _get_order_url(order),
        },
    )
