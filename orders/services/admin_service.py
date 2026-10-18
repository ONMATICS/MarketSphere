from decimal import Decimal
from typing import Any

from django.db.models import QuerySet, Sum
from django.utils import timezone

from orders.models import Order


def _percentage_change(current: int | float | Decimal, previous: int | float | Decimal) -> float | int:
    """Calculate the percentage change between two numerical values."""
    if previous == 0:
        if current == 0:
            return 0
        return 100

    return round(float(((current - previous) / previous) * 100), 1)


def get_admin_order_stats() -> dict[str, Any]:
    """Calculate overarching platform order statistics and period-over-period changes."""
    now = timezone.localtime()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if current_month_start.month == 1:
        previous_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
    else:
        previous_month_start = current_month_start.replace(month=current_month_start.month - 1)

    current_month_end = now
    orders = Order.objects.all()

    current_orders = orders.filter(created_at__gte=current_month_start, created_at__lte=current_month_end)
    previous_orders = orders.filter(created_at__gte=previous_month_start, created_at__lt=current_month_start)

    pending_orders = orders.filter(status=Order.Status.PENDING).count()
    processing_orders = orders.filter(status=Order.Status.PROCESSING).count()
    delivered_orders = orders.filter(status=Order.Status.DELIVERED).count()

    current_pending_orders = current_orders.filter(status=Order.Status.PENDING).count()
    previous_pending_orders = previous_orders.filter(status=Order.Status.PENDING).count()

    current_processing_orders = current_orders.filter(status=Order.Status.PROCESSING).count()
    previous_processing_orders = previous_orders.filter(status=Order.Status.PROCESSING).count()

    current_delivered_orders = current_orders.filter(status=Order.Status.DELIVERED).count()
    previous_delivered_orders = previous_orders.filter(status=Order.Status.DELIVERED).count()

    total_revenue = orders.filter(status=Order.Status.DELIVERED).aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    current_revenue = current_orders.filter(status=Order.Status.DELIVERED).aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    previous_revenue = previous_orders.filter(status=Order.Status.DELIVERED).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

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


def get_admin_orders() -> QuerySet[Order]:
    """Retrieve a queryset of all platform orders tailored for the administration dashboard."""
    return (
        Order.objects
        .select_related("user", "seller")
        .prefetch_related("items", "items__product")
        .order_by("-created_at")
    )