from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet

from allauth.mfa.models import Authenticator

from accounts.models import User
from notifications.models import ActivityLog
from orders.models import Order
from products.models import WishlistItem

from .address_service import get_default_address, get_user_addresses


def _order_status_value(order: Any) -> str:
    """Return a normalized lowercase status string for an order record."""
    value = getattr(order, "overall_status", None)
    if value is None:
        value = getattr(order, "status", "")
    return str(value or "").lower()


def _order_status_display(order: Any) -> str:
    """Resolve the human-readable display value for an order's status."""
    if hasattr(order, "get_overall_status_display"):
        try:
            return order.get_overall_status_display()
        except Exception:
            pass
    if hasattr(order, "get_status_display"):
        try:
            return order.get_status_display()
        except Exception:
            pass
    return _order_status_value(order).title() or "—"


def _order_items_count(order: Any) -> int:
    """Sum line items belonging to an order by checking common relation schemas."""
    for attr in ("items", "order_items", "orderitem_set"):
        manager = getattr(order, attr, None)
        if manager is not None and hasattr(manager, "count"):
            try:
                return manager.count()
            except Exception:
                continue

    seller_orders = getattr(order, "seller_orders", None)
    if seller_orders is not None and hasattr(seller_orders, "all"):
        total = 0
        for seller_order in seller_orders.all():
            for attr in ("items", "order_items", "orderitem_set"):
                manager = getattr(seller_order, attr, None)
                if manager is not None and hasattr(manager, "count"):
                    total += manager.count()
                    break
        return total

    return 0


def _get_wishlist_queryset(user: User) -> QuerySet | None:
    """Resolve the user's wishlist items regardless of app related_name."""
    for attr in ("wishlist_items", "wishlistitem_set", "wishlist_set"):
        manager = getattr(user, attr, None)
        if manager is not None and hasattr(manager, "all"):
            return manager.all()
    return None


def _get_reviews_queryset(user: User) -> QuerySet | None:
    """Resolve the user's reviews regardless of app related_name."""
    for attr in ("review_set", "reviews"):
        manager = getattr(user, attr, None)
        if manager is not None and hasattr(manager, "all"):
            return manager.all()
    return None


def get_buyer_orders_queryset(user: User) -> QuerySet[Order]:
    """Retrieve all base orders placed by the user."""
    return Order.objects.filter(user=user).order_by("-created_at")


def get_buyer_recent_orders(user: User, limit: int = 5) -> list[Order]:
    """Retrieve the most recent orders placed by the user."""
    return list(get_buyer_orders_queryset(user)[:limit])


def get_buyer_dashboard_stats(user: User) -> dict[str, int | Decimal]:
    """Compile macro-level statistics for a buyer's activity dashboard."""
    orders = list(get_buyer_orders_queryset(user))

    total_orders = len(orders)
    completed_orders = sum(1 for order in orders if _order_status_value(order) in ("delivered", "completed"))
    cancelled_orders = sum(1 for order in orders if _order_status_value(order) == "cancelled")
    pending_orders = sum(1 for order in orders if _order_status_value(order) in ("pending", "confirmed", "processing"))

    total_spent = sum(
        (getattr(order, "total", Decimal("0.00")) or Decimal("0.00"))
        for order in orders
        if _order_status_value(order) != "cancelled"
    )

    wishlist_qs = _get_wishlist_queryset(user)
    wishlist_count = wishlist_qs.count() if wishlist_qs is not None else 0

    reviews_qs = _get_reviews_queryset(user)
    reviews_count = reviews_qs.count() if reviews_qs is not None else 0

    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "pending_orders": pending_orders,
        "total_spent": total_spent,
        "wishlist_count": wishlist_count,
        "reviews_count": reviews_count,
        "saved_addresses": user.addresses.count(),
    }


def calculate_buyer_profile_completion(user: User) -> dict[str, Any]:
    """Analyze which core identity properties a user has completed."""
    completed = 0
    total = 0
    missing = []

    def check(condition: Any, label: str) -> None:
        nonlocal completed, total
        total += 1
        if condition:
            completed += 1
        else:
            missing.append(label)

    check(bool(user.first_name), "First name")
    check(bool(user.last_name), "Last name")
    check(bool(user.contact), "Phone number")
    check(bool(user.profile_image_url), "Profile photo")
    check(user.addresses.filter(is_default=True).exists(), "Default address")
    check(user.account_status == User.AccountStatus.VERIFIED, "Email verification")

    percentage = round((completed / total) * 100) if total else 0

    return {
        "percentage": percentage,
        "completed": completed,
        "total": total,
        "missing": missing,
        "is_complete": percentage == 100,
    }


def get_buyer_wishlist_preview(user: User, limit: int = 4) -> list[WishlistItem]:
    """Fetch a limited set of pre-fetched wishlist items for a buyer."""
    return list(
        WishlistItem.objects.filter(user=user)
        .select_related("product", "product__brand")
        .prefetch_related("product__images")[:limit]
    )


def get_buyer_recent_activity(user: User, limit: int = 6) -> list[ActivityLog]:
    """Fetch the chronological activity feed matching the user or their orders."""
    order_content_type = ContentType.objects.get_for_model(Order)
    return list(
        ActivityLog.objects.select_related("actor").filter(
            Q(actor=user)
            | Q(target_content_type=order_content_type, target_object_id__in=user.orders.values("pk"))
        )[:limit]
    )


def get_buyer_notifications(user: User, limit: int = 5) -> tuple[list[Any], int]:
    """Fetch recent unread alerts intended for the buyer.

    Note: The notifications model may act as a dynamic fallback depending 
    on the current schema deployment stage of the notifications app.
    """
    for attr in ("notifications", "notification_set"):
        manager = getattr(user, attr, None)
        if manager is not None and hasattr(manager, "all"):
            qs = manager.order_by("-created_at")
            try:
                unread_count = qs.filter(is_read=False).count()
            except Exception:
                unread_count = 0
            return list(qs[:limit]), unread_count
    return [], 0


def get_buyer_profile_context(user) -> dict[str, Any]:
    """Orchestrate all statistical, activity, and related data for the My Account page."""
    notifications, notifications_unread_count = get_buyer_notifications(user)

    return {
        "addresses": get_user_addresses(user),
        "default_address": get_default_address(user),
        "recent_orders": get_buyer_recent_orders(user),
        "buyer_stats": get_buyer_dashboard_stats(user),
        "profile_completion": calculate_buyer_profile_completion(user),
        "wishlist_items": get_buyer_wishlist_preview(user),
        "activities": get_buyer_recent_activity(user),
        "notifications": notifications,
        "notifications_unread_count": notifications_unread_count,
        "two_factor_enabled": Authenticator.objects.filter(
            user=user, type=Authenticator.Type.TOTP
        ).exists(),
    }