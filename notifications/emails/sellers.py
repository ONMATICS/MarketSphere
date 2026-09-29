import logging

from django.conf import settings
from django.urls import NoReverseMatch, reverse

from notifications.services.email import send_marketplace_email
from admin_panel.notification_settings import notification_channel_enabled

logger = logging.getLogger(__name__)


def _get_absolute_url(path):
    if not path:
        return ""
    return f"{settings.SITE_URL.rstrip('/')}/{path.lstrip('/')}"


def _safe_reverse(name, **kwargs):
    try:
        return _get_absolute_url(reverse(name, kwargs=kwargs))
    except NoReverseMatch:
        logger.exception("Could not reverse seller email URL %s", name)
        return ""


def _get_application_url():
    return _safe_reverse("seller-account")


def _get_seller_dashboard_url():
    return _safe_reverse("dashboard")


def _get_seller_order_url(order):
    return _safe_reverse("order-detail", order_no=order.order_number)


def _get_product_url(product):
    return _safe_reverse("seller-edit-product", product_slug=product.slug)


def _seller_email(seller):
    user = getattr(seller, "user", None)
    return getattr(user, "email", "") or ""


def _recipient_name(seller):
    user = getattr(seller, "user", None)
    return (
        getattr(user, "first_name", "")
        or getattr(user, "username", "")
        or getattr(seller, "store_name", "Seller")
    )


def _send(**kwargs):
    try:
        return bool(send_marketplace_email(**kwargs))
    except Exception:
        logger.exception("Seller marketplace email failed")
        return False

def send_application_incomplete_email(seller):
    user = getattr(seller, "user", None)
    application = getattr(seller, "application", None)

    if not getattr(user, "email", "") or application is None:
        return False

    return _send(
        subject="Complete Your Seller Application — MarketSphere",
        recipient=user.email,
        template="email_management/sellers/application_incomplete.html",
        context={
            "recipient_name": user.first_name or user.username,
            "seller": seller,
            "application": application,
            "application_url": _get_application_url(),
        },
    )


def send_application_received_email(application):
    seller = application.seller
    user = seller.user

    if not getattr(user, "email", ""):
        return False

    return _send(
        subject="Seller Application Received — MarketSphere",
        recipient=user.email,
        template="email_management/sellers/application_received.html",
        context={
            "recipient_name": user.first_name or user.username,
            "seller": seller,
            "application": application,
            "application_url": _get_application_url(),
        },
    )


def send_seller_verified_email(seller):
    user = getattr(seller, "user", None)
    if not getattr(user, "email", "") or not notification_channel_enabled("SELLER_APPLICATION_APPROVED", "SELLER", "email"):
        return False

    return _send(
        subject="Your Seller Account Is Verified — MarketSphere",
        recipient=user.email,
        template="email_management/sellers/verified.html",
        context={
            "recipient_name": user.first_name or user.username,
            "seller": seller,
            "seller_dashboard_url": _get_seller_dashboard_url(),
        },
    )

def send_seller_rejected_email(application, rejection_reason=None):
    seller = application.seller
    user = seller.user

    if not getattr(user, "email", "") or not notification_channel_enabled("SELLER_APPLICATION_REJECTED", "SELLER", "email"):
        return False

    return _send(
        subject="Seller Application Update — MarketSphere",
        recipient=user.email,
        template="email_management/sellers/rejected.html",
        context={
            "recipient_name": user.first_name or user.username,
            "seller": seller,
            "application": application,
            "rejection_reason": (
                rejection_reason
                or getattr(application, "rejection_reason", None)
            ),
            "application_url": _get_application_url(),
        },
    )


def _preference_enabled(seller, preference):
    try:
        seller_settings = seller.settings
    except Exception:
        return False
    return bool(getattr(seller_settings, preference, False))


def send_new_order_email(order):
    seller = getattr(order, "seller", None)
    recipient = _seller_email(seller)
    if not recipient or not _preference_enabled(seller, "email_new_order") or not notification_channel_enabled("ORDER_CREATED", "SELLER", "email"):
        return False
    return _send(
        subject="New Order Received — MarketSphere",
        recipient=recipient,
        template="email_management/sellers/new_order.html",
        context={
            "recipient_name": _recipient_name(seller),
            "seller": seller,
            "order": order,
            "order_url": _get_seller_order_url(order),
        },
    )


def send_cancelled_order_email(order, cancellation_reason=None):
    seller = getattr(order, "seller", None)
    recipient = _seller_email(seller)
    if not recipient or not _preference_enabled(seller, "email_cancelled_order") or not notification_channel_enabled("ORDER_CANCELLED", "SELLER", "email"):
        return False
    return _send(
        subject="Order Cancelled — MarketSphere",
        recipient=recipient,
        template="email_management/sellers/cancelled.html",
        context={
            "recipient_name": _recipient_name(seller),
            "seller": seller,
            "order": order,
            "cancellation_reason": cancellation_reason,
            "order_url": _get_seller_order_url(order),
        },
    )


def send_delivered_order_email(order):
    seller = getattr(order, "seller", None)
    recipient = _seller_email(seller)
    if not recipient or not _preference_enabled(seller, "email_delivered_order") or not notification_channel_enabled("ORDER_DELIVERED", "SELLER", "email"):
        return False
    return _send(
        subject="Order Delivered — MarketSphere",
        recipient=recipient,
        template="email_management/sellers/delivered.html",
        context={
            "recipient_name": _recipient_name(seller),
            "seller": seller,
            "order": order,
            "order_url": _get_seller_order_url(order),
        },
    )


def send_low_stock_email(product):
    seller = getattr(product, "seller", None)
    recipient = _seller_email(seller)
    if not recipient or not _preference_enabled(seller, "email_low_stock") or not notification_channel_enabled("LOW_STOCK", "SELLER", "email"):
        return False
    return _send(
        subject="Low Stock Alert — MarketSphere",
        recipient=recipient,
        template="email_management/sellers/low_stock.html",
        context={
            "recipient_name": _recipient_name(seller),
            "seller": seller,
            "product": product,
            "product_url": _get_product_url(product),
        },
    )
