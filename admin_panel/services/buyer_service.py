import csv
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from allauth.mfa.utils import is_mfa_enabled

from accounts.models import Address, User
from notifications.models import ActivityLog
from orders.models import Order, OrderItem
from products import services as product_services
from support.models.product_reviews import Review


def get_buyer_details(user_id: int) -> dict[str, Any]:
    """Retrieve comprehensive dashboard details and statistics for a buyer."""
    buyer = get_object_or_404(User, id=user_id)
    addresses = Address.objects.filter(user=buyer)
    total_orders = buyer.orders.count()

    today = timezone.now()
    current_month_start = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    orders_this_month = buyer.orders.filter(created_at__gte=current_month_start).count()
    orders = buyer.orders.select_related("seller")

    completed_orders = sum(1 for order in orders if order.status == Order.Status.DELIVERED)
    pending_orders = sum(
        1 for order in orders if order.status not in (Order.Status.DELIVERED, Order.Status.CANCELLED)
    )
    cancelled_orders = sum(1 for order in orders if order.status == Order.Status.CANCELLED)

    completion_percentage = round((completed_orders / total_orders) * 100) if total_orders else 0
    cancelled_percentage = round((cancelled_orders / total_orders) * 100) if total_orders else 0

    paid_orders = buyer.orders.filter(payment_status=Order.PaymentStatus.PAID)
    total_spent = paid_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    total_paid_orders = paid_orders.count()
    average_order_value = total_spent / total_paid_orders if total_paid_orders else Decimal("0.00")

    wishlist_items = buyer.wishlist_items.count()

    preferred_category = (
        OrderItem.objects.filter(order__user=buyer)
        .values("product__category__name")
        .annotate(total_items=Sum("quantity"))
        .order_by("-total_items")
        .first()
    )
    preferred_seller = (
        Order.objects.filter(user=buyer)
        .values("seller__store_name")
        .annotate(total_orders=Sum("items__quantity"))
        .order_by("-total_orders")
        .first()
    )
    last_order = buyer.orders.order_by("-created_at").first()

    months = max(
        1,
        (
            (today.year - buyer.date_joined.year) * 12
            + today.month
            - buyer.date_joined.month
        ),
    )
    order_frequency = round(total_orders / months, 1)

    chart_start = current_month_start - timedelta(days=365)
    monthly_spending = (
        buyer.orders.filter(
            payment_status=Order.PaymentStatus.PAID,
            created_at__gte=chart_start,
        )
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("total"))
        .order_by("month")
    )

    monthly_map = {item["month"].strftime("%b"): float(item["total"]) for item in monthly_spending}
    months_list = []
    bars = []
    current = chart_start.replace(day=1)

    for _ in range(12):
        label = current.strftime("%b")
        months_list.append(label)
        bars.append(
            {
                "month": label,
                "total": monthly_map.get(label, 0),
                "height": 0,
            }
        )
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    max_total = max((bar["total"] for bar in bars), default=1)
    for bar in bars:
        bar["height"] = round((bar["total"] / max_total) * 100) if max_total > 0 else 0

    recent_orders = buyer.orders.select_related("seller").prefetch_related("items__product").order_by("-created_at")[:10]
    for order in recent_orders:
        order.seller_name = order.seller.store_name if order.seller else "Unknown Seller"
        order.items_count = sum(item.quantity for item in order.items.all())

    order_content_type = ContentType.objects.get_for_model(Order)
    activity_logs = ActivityLog.objects.select_related("actor").filter(
        Q(actor=buyer)
        | Q(target_content_type=order_content_type, target_object_id__in=buyer.orders.values("pk"))
    )[:20]

    total_reviews = buyer.reviews.count()
    avg_result = buyer.reviews.aggregate(average=Avg('rating'))
    average_rating = round(avg_result['average'] or 0.0, 1)
    recent_reviews = buyer.reviews.select_related("product").order_by("-created_at")[:10]

    return {
        "buyer": buyer,
        "addresses": addresses,
        "total_orders": total_orders,
        "orders_this_month": orders_this_month,
        "completed_orders": completed_orders,
        "completion_percentage": completion_percentage,
        "pending_orders": pending_orders,
        "cancelled_orders": cancelled_orders,
        "cancelled_percentage": cancelled_percentage,
        "total_spent": total_spent,
        "average_order_value": average_order_value,
        "wishlist_items": wishlist_items,
        "preferred_category": preferred_category,
        "preferred_seller": preferred_seller,
        "last_order": last_order,
        "order_frequency": order_frequency,
        "spending_trend": bars,
        "recent_orders": recent_orders,
        "wishlist": product_services.get_user_wishlist(buyer),
        "activity_logs": activity_logs,
        "total_reviews": total_reviews,
        "recent_reviews": recent_reviews,
        "average_rating": average_rating,
        "is_2fa_enabled": is_mfa_enabled(buyer),
    }


def export_order_history(user_id: int) -> HttpResponse:
    """Export a user's entire order history as a CSV file."""
    orders = (
        Order.objects.filter(user_id=user_id)
        .select_related("seller")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"order-history-user-{user_id}-{timezone.now().strftime('%Y-%m-%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Order Number", "Order Date", "Status", "Payment Status",
        "Seller", "Products", "Subtotal", "Shipping", "Discount",
        "Tax", "Total", "Tracking Number", "Courier",
    ])

    for order in orders:
        products = ", ".join([f"{item.product.name} (x{item.quantity})" for item in order.items.all()])
        writer.writerow([
            order.order_number,
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            order.get_status_display(),
            order.payment_status,
            order.seller.store_name if order.seller else "",
            products,
            order.subtotal,
            order.shipping_cost,
            order.discount,
            order.tax,
            order.total,
            order.tracking_number,
            order.courier,
        ])

    return response