import csv
import math
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    Avg, Count, DecimalField, DurationField, ExpressionWrapper, F, Max, Q, Sum, Value, QuerySet
)
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone

from allauth.account.models import EmailAddress

from accounts.models import Seller, SellerApplicationDocument
from accounts.services import get_seller_application_documents
from notifications.models import ActivityLog
from orders.models import Order, OrderItem
from products.models import Product
from support.models.product_reviews import Review


def get_seller_detail(user_id: int) -> dict[str, Any]:
    """Retrieve comprehensive dashboard details, statistics, and reviews for a seller."""
    seller = Seller.objects.filter(id=user_id).first()

    if seller:
        total_sales = seller.orders.filter(status=Order.Status.DELIVERED).aggregate(
            total=Coalesce(
                Sum("total"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
    else:
        total_sales = Decimal("0.00")

    total_products = seller.products.count() if seller else 0
    
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_end = current_month_start - timedelta(seconds=1)
    previous_month_start = previous_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if not seller:
        return {} # Early exit if no seller matches to prevent unbound references

    products_added_this_month = seller.products.filter(created_at__gte=current_month_start).count()
    published_products = seller.products.filter(status=Product.Status.PUBLISHED).count()
    drafted_products = seller.products.filter(status=Product.Status.DRAFT).count()
    hidden_products = seller.products.filter(status=Product.Status.HIDDEN).count()
    pending_products = seller.products.filter(status=Product.Status.PENDING).count()
    archived_products = seller.products.filter(status=Product.Status.ARCHIVED).count()

    out_of_stock_products = seller.products.filter(
        Q(status=Product.Status.OUT_OF_STOCK) | Q(stock_quantity=0)
    ).count()

    published_catalog_percentage = round((published_products / total_products) * 100, 1) if total_products else 0

    total_orders = seller.orders.count()
    pending_orders = seller.orders.filter(status=Order.Status.PENDING).count()
    processing_orders = seller.orders.filter(status=Order.Status.PROCESSING).count()
    shipped_orders = seller.orders.filter(status=Order.Status.SHIPPED).count()
    completed_orders = seller.orders.filter(status=Order.Status.DELIVERED).count()

    today = timezone.localdate()
    today_orders = seller.orders.filter(created_at__date=today).count()
    orders = seller.orders.select_related("user").prefetch_related("items__product").order_by("-created_at")

    completed_order_percentage = round((completed_orders / total_orders) * 100, 1) if total_orders else 0
    cancelled_orders = seller.orders.filter(status=Order.Status.CANCELLED).count()
    cancelled_order_percentage = round((cancelled_orders / total_orders) * 100, 1) if total_orders else 0
    
    previous_month_orders = seller.orders.filter(
        created_at__gte=previous_month_start, created_at__lt=current_month_start
    ).count()

    if previous_month_orders:
        order_change = round(((total_orders - previous_month_orders) / previous_month_orders) * 100, 1)
    else:
        order_change = 100 if total_orders else 0

    order_increased = total_orders >= previous_month_orders

    lifetime_revenue = total_sales
    current_month_revenue = seller.orders.filter(
        status=Order.Status.DELIVERED, created_at__gte=current_month_start
    ).aggregate(
        total=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField(max_digits=12, decimal_places=2))
    )["total"]

    previous_month_revenue = seller.orders.filter(
        status=Order.Status.DELIVERED,
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    ).aggregate(
        total=Coalesce(Sum("total"), Value(Decimal("0.00")), output_field=DecimalField(max_digits=12, decimal_places=2))
    )["total"]

    if previous_month_revenue:
        revenue_growth = round(((current_month_revenue - previous_month_revenue) / previous_month_revenue) * 100, 1)
    else:
        revenue_growth = 100 if current_month_revenue else 0

    average_order_value = round(lifetime_revenue / total_orders, 2) if total_orders else Decimal("0.00")

    preferred_cat_obj = (
        seller.products.exclude(category=None)
        .values("category__name")
        .annotate(product_count=Count("id"))
        .order_by("-product_count")
        .first()
    )
    preferred_category = preferred_cat_obj["category__name"] if preferred_cat_obj else "N/A"

    best_selling_obj = (
        OrderItem.objects.filter(order__seller=seller, order__status=Order.Status.DELIVERED)
        .values("product__name")
        .annotate(quantity_sold=Sum("quantity"))
        .order_by("-quantity_sold")
        .first()
    )
    best_selling_product = best_selling_obj["product__name"] if best_selling_obj else "N/A"

    average_shipping_duration = seller.orders.filter(
        shipped_at__isnull=False, delivered_at__isnull=False
    ).aggregate(
        avg=Avg(ExpressionWrapper(F("delivered_at") - F("shipped_at"), output_field=DurationField()))
    )["avg"]
    average_shipping_days = round(average_shipping_duration.total_seconds() / 86400, 1) if average_shipping_duration else None

    repeat_buyers = seller.orders.values("user").annotate(order_count=Count("id")).filter(order_count__gte=2).count()
    total_buyers = seller.orders.values("user").distinct().count()
    repeat_buyers_rate = round(repeat_buyers * 100 / total_buyers, 1) if total_buyers else 0

    fulfillment_rate = round(completed_orders * 100 / total_orders, 1) if total_orders else 0

    products = seller.products.annotate(
        total_sales=Coalesce(
            Sum("order_items__quantity", filter=Q(order_items__order__status=Order.Status.DELIVERED)), 0
        )
    )

    top_buyers = seller.orders.values(
        "user__id", "user__first_name", "user__last_name", "user__profile_image_url"
    ).annotate(total_orders=Count("id"), total_spent=Sum("total")).order_by("-total_spent")[:5]

    customer_locations = seller.orders.values("shipping_city").annotate(total=Count("id")).order_by("-total")
    for city in customer_locations:
        city["percentage"] = round(city["total"] * 100 / total_orders, 1) if total_orders else 0

    recent_customers = seller.orders.values(
        "user__id", "user__first_name", "user__last_name"
    ).annotate(total_orders=Count("id"), total_spent=Sum("total"), last_order=Max("created_at")).order_by("-last_order")[:3]
    for customer in recent_customers:
        customer["repeat_buyer"] = customer["total_orders"] >= 2

    top_selling_products = OrderItem.objects.filter(
        order__seller=seller, order__status=Order.Status.DELIVERED
    ).values("product__name").annotate(total_sold=Sum("quantity")).order_by("-total_sold")[:5]
    
    max_sold = top_selling_products[0]["total_sold"] if top_selling_products else 0
    for product in top_selling_products:
        product["percentage"] = round(product["total_sold"] * 100 / max_sold, 1) if max_sold else 0

    top_categories = OrderItem.objects.filter(
        order__seller=seller, order__status=Order.Status.DELIVERED
    ).values("product__category__name").annotate(total_sold=Sum("quantity")).order_by("-total_sold")[:5]
    
    max_category_sales = top_categories[0]["total_sold"] if top_categories else 0
    for category in top_categories:
        category["percentage"] = round(category["total_sold"] * 100 / max_category_sales, 1) if max_category_sales else 0

    DONUT_CIRCUMFERENCE = 2 * math.pi * 60
    delivered_percentage = completed_order_percentage
    donut_offset = round(DONUT_CIRCUMFERENCE * (100 - delivered_percentage) / 100, 1)

    documents = get_seller_application_documents(seller)

    order_content_type = ContentType.objects.get_for_model(Order)
    product_content_type = ContentType.objects.get_for_model(Product)
    activity_logs = ActivityLog.objects.select_related("actor").filter(
        Q(actor=seller.user)
        | Q(target_content_type=order_content_type, target_object_id__in=seller.orders.values("pk"))
        | Q(target_content_type=product_content_type, target_object_id__in=seller.products.values("pk"))
    )[:20]

    seller_reviews_qs = Review.objects.filter(product__seller=seller)
    review_stats = seller_reviews_qs.aggregate(total=Count('id'), average=Avg('rating'))
    total_seller_reviews = review_stats['total']
    seller_average_rating = round(review_stats['average'], 1) if review_stats['average'] else 0.0

    seller_average_stars = []
    for i in range(1, 6):
        if seller_average_rating >= i:
            seller_average_stars.append('bi-star-fill')
        elif seller_average_rating >= i - 0.5:
            seller_average_stars.append('bi-star-half')
        else:
            seller_average_stars.append('bi-star')

    distribution_counts = seller_reviews_qs.values('rating').annotate(count=Count('id'))
    seller_review_distribution = {i: {'count': 0, 'percent': 0} for i in range(5, 0, -1)}
    
    for c in distribution_counts:
        rating = c['rating']
        count = c['count']
        percent = (count / total_seller_reviews * 100) if total_seller_reviews > 0 else 0
        if rating in seller_review_distribution:
            seller_review_distribution[rating] = {'count': count, 'percent': round(percent)}

    recent_seller_reviews = seller_reviews_qs.select_related(
        'user', 'product'
    ).prefetch_related('reports').order_by('-created_at')[:20]

    return {
        "seller": seller,
        "total_sales": total_sales,
        "total_products": total_products,
        "products_this_month": products_added_this_month,
        "published_products": published_products,
        "published_catalog_percentage": published_catalog_percentage,
        "drafted_products": drafted_products,
        "hidden_products": hidden_products,
        "out_of_stock_products": out_of_stock_products,
        "pending_products": pending_products,
        "archived_products": archived_products,
        "total_orders": total_orders,
        "order_change": order_change,
        "order_increased": order_increased,
        "processing_orders": processing_orders,
        "shipped_orders": shipped_orders,
        "pending_orders": pending_orders,
        "today_orders": today_orders,
        "completed_orders": completed_orders,
        "completed_orders_percentage": completed_order_percentage,
        "cancelled_orders": cancelled_orders,
        "cancelled_orders_percentage": cancelled_order_percentage,
        "lifetime_revenue": lifetime_revenue,
        "revenue_growth": revenue_growth,
        "monthly_revenue": current_month_revenue,
        "average_order_value": average_order_value,
        "preferred_category": preferred_category,
        "best_selling_product": best_selling_product,
        "average_shipping_days": average_shipping_days,
        "repeat_buyers_rate": repeat_buyers_rate,
        "fulfillment_rate": fulfillment_rate,
        "response_time": "N/A",
        "products": products,
        "orders": orders,
        "top_buyers": top_buyers,
        "customer_locations": customer_locations,
        "recent_customers": recent_customers,
        "delivered_percentage": delivered_percentage,
        "donut_offset": donut_offset,
        "top_selling_products": top_selling_products,
        "top_categories": top_categories,
        "documents": documents,
        "activity_logs": activity_logs,
        "total_seller_reviews": total_seller_reviews,
        "seller_average_rating": seller_average_rating,
        "seller_average_stars": seller_average_stars,
        "seller_review_distribution": seller_review_distribution,
        "recent_seller_reviews": recent_seller_reviews,
    }


def get_pending_sellers() -> QuerySet[Seller]:
    """Retrieve all sellers currently pending approval."""
    return Seller.objects.filter(status=Seller.Status.PENDING).all()


def get_pending_seller(seller_id: int) -> dict[str, Any]:
    """Retrieve detailed compliance and progress metrics for a pending seller application."""
    seller = Seller.objects.select_related(
        "application", "profile", "settings", "user"
    ).get(id=seller_id, status=Seller.Status.PENDING)

    application = seller.application
    profile = getattr(seller, "profile", None)
    settings = getattr(seller, "settings", None)

    verification_score = 0
    if seller.store_name: verification_score += 15
    if seller.store_email: verification_score += 15
    if seller.store_description: verification_score += 20
    if seller.store_logo: verification_score += 15
    if seller.store_banner: verification_score += 15
    if seller.business_address: verification_score += 20

    trust_score = verification_score
    if trust_score >= 80: risk_level = "low"
    elif trust_score >= 60: risk_level = "medium"
    else: risk_level = "high"

    required_documents = len(SellerApplicationDocument.DocumentType.choices)
    uploaded_documents = application.documents.count()
    verified_documents = application.documents.filter(verified=True).count()
    
    document_completeness = int(uploaded_documents / required_documents * 100) if required_documents else 0
    flags_raised = application.flags.filter(resolved=False).count()

    profile_fields = [
        seller.store_name, seller.store_email, seller.store_description,
        seller.store_logo, seller.store_banner, seller.business_address,
        profile.business_category if profile else None,
        profile.business_type if profile else None,
        profile.national_id_number if profile else None,
        profile.years_in_business if profile else None,
        profile.expected_monthly_volume if profile else None,
        profile.product_categories if profile else None,
        profile.website if profile else None,
    ]

    completed_profile_fields = sum(bool(field) for field in profile_fields)
    profile_completeness = int(completed_profile_fields / len(profile_fields) * 100)

    compliance_checks = [
        verified_documents >= 2,
        settings.business_registration_verified if settings else False,
        settings.bank_account_verified if settings else False,
        settings.address_verified if settings else False,
    ]
    compliance_score = int(sum(compliance_checks) / len(compliance_checks) * 100)

    CIRCUMFERENCE = 2 * math.pi * 60
    score_offset = CIRCUMFERENCE * (1 - trust_score / 100)

    documents = get_seller_application_documents(seller)
    cnic_front = documents.get("cnic_front")
    cnic_back = documents.get("cnic_back")
    identity_verified = bool(cnic_front and cnic_back and cnic_front.file and cnic_back.file and cnic_front.verified and cnic_back.verified)

    email_verified = EmailAddress.objects.filter(user=seller.user, verified=True).exists()
    store_profile_complete = all([seller.store_logo, seller.store_banner, seller.store_description])
    
    return {
        "seller": seller,
        "application": application,
        "verification_score": verification_score,
        "trust_score": trust_score,
        "score_offset": score_offset,
        "risk_level": risk_level,
        "documents_submitted": uploaded_documents,
        "verified_documents": verified_documents,
        "document_completeness": document_completeness,
        "flags_raised": flags_raised,
        "profile_completeness": profile_completeness,
        "compliance_score": compliance_score,
        "payment_verified": settings.bank_account_verified if settings else False,
        "duplicate_accounts": None,
        "blacklist_clean": None,
        "documents": documents,
        "identity_verified": identity_verified,
        "email_verified": email_verified,
        "store_profile_complete": store_profile_complete,
        "business_address": bool(seller.business_address),
    }


def export_seller_orders(seller: Seller) -> HttpResponse:
    """Export all orders associated with a seller into a CSV format."""
    orders = (
        Order.objects.filter(seller=seller)
        .select_related("user", "seller")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"{seller.store_name}-orders-{timezone.now().strftime('%Y-%m-%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Order Number", "Order Date", "Status", "Payment Status",
        "Customer", "Products", "Subtotal", "Shipping", "Discount",
        "Tax", "Total", "Tracking Number", "Courier", "Shipped At", "Delivered At",
    ])

    for order in orders:
        products = ", ".join(f"{item.product.name} (x{item.quantity})" for item in order.items.all())
        writer.writerow([
            order.order_number,
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            order.get_status_display(),
            order.payment_status,
            order.shipping_name,
            products,
            order.subtotal,
            order.shipping_cost,
            order.discount,
            order.tax,
            order.total,
            order.tracking_number,
            order.courier,
            order.shipped_at.strftime("%Y-%m-%d %H:%M") if order.shipped_at else "",
            order.delivered_at.strftime("%Y-%m-%d %H:%M") if order.delivered_at else "",
        ])

    return response