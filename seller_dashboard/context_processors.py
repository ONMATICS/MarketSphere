from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import F, Q, Sum
from django.utils import timezone

from accounts.models import Seller
from orders.models import Order
from products.models import Product
from admin_panel.catalog import get_catalog_settings
from admin_panel.settings_data import get_admin_setting
from notifications.models import ActivityLog

from orders.services import get_seller_orders

today = timezone.now()
week_ago = today - timedelta(days=7)


def seller_dashboard(request):
    if not request.user.is_authenticated:
        return {}

    try:
        seller = request.user.seller_profile
    except Seller.DoesNotExist:
        return {}

    seller_products = Product.objects.filter(seller=seller)
    seller_orders = Order.objects.filter(seller=seller)
    order_content_type = ContentType.objects.get_for_model(Order)
    activity_logs = ActivityLog.objects.select_related("actor").filter(
        Q(actor=request.user)
        | Q(
            target_content_type=order_content_type,
            target_object_id__in=seller_orders.values("pk"),
        )
    )[:8]

    total_products = seller_products.count()

    drafted_products = seller_products.filter(
        status=Product.Status.DRAFT
    )
    
    published_products = seller_products.filter(
        status=Product.Status.PUBLISHED
    ).count()

    pending_orders = seller_orders.filter(
        status=Order.Status.PENDING
    ).count()
    
    processing_orders = seller_orders.filter(
        status=Order.Status.PROCESSING
    ).count()

    completed_orders = seller_orders.filter(
        status=Order.Status.DELIVERED
    ).count()

    completed_revenue = (
        seller_orders.filter(
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.PAID,
        ).aggregate(
            revenue=Sum("total")
        )["revenue"]
        or 0
    )

    new_orders_this_week = seller_orders.filter(
        created_at__gte=week_ago
    ).count()

    month_orders = seller_orders.filter(
        created_at__year=today.year,
        created_at__month=today.month,
    ).count()

    recent_orders = (
        seller_orders.select_related("user")
        .prefetch_related("items", "items__product")
        .order_by("-created_at")[:4]
    )

    low_stock_products = seller_products.filter(
        stock_quantity__lte=get_catalog_settings().low_stock_threshold
    )

    out_of_stock_products = seller_products.filter(
        stock_quantity__lte=0
    )

    return {
        "dashboard_seller": seller,
        "dashboard_pending_orders": pending_orders,
        "dashboard_completed_orders": completed_orders,
        "dashboard_processing_orders": processing_orders,
        "dashboard_total_products": total_products,
        "dashboard_seller_products": seller_products,
        "dashboard_published_products": published_products,
        "dashboard_low_stock_products": low_stock_products,
        "dashboard_out_of_stock_products": out_of_stock_products,
        "dashboard_completed_revenue": completed_revenue,
        "dashboard_month_orders": month_orders,
        "dashboard_new_orders_this_week": new_orders_this_week,
        "dashboard_recent_orders": recent_orders,
        "dashboard_drafted_products": drafted_products,
        "dashboard_seller_orders": get_seller_orders(seller),
        "allow_seller_drafts": str(get_admin_setting("catalog", "allow_seller_drafts", True)).lower() in {"1", "true", "yes", "on"},
        "dashboard_activity_logs": activity_logs,
    }
