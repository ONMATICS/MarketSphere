import csv
import io
import json
import math
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Max, Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Prefetch
from django.contrib.contenttypes.models import ContentType

from allauth.account.models import EmailAddress
from notifications.models import ActivityLog
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)

from accounts.models import Address, User, Seller, SellerApplicationDocument
from accounts.services import get_seller_application_documents
from orders.models import Order, OrderItem
from products import services
from products.models import Product, Brand, Category
from services.cloudinary_service import store_catalog_image


def get_buyer_details(user_id):
    buyer = get_object_or_404(User, id=user_id)
    addresses = Address.objects.filter(user=buyer)

    total_orders = buyer.orders.count()

    today = timezone.now()
    current_month_start = today.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    orders_this_month = buyer.orders.filter(
        created_at__gte=current_month_start,
    ).count()

    orders = buyer.orders.select_related("seller")

    completed_orders = sum(
        1 for order in orders if order.status == Order.Status.DELIVERED
    )

    pending_orders = sum(
        1
        for order in orders
        if order.status
        not in (
            Order.Status.DELIVERED,
            Order.Status.CANCELLED,
        )
    )

    cancelled_orders = sum(
        1 for order in orders if order.status == Order.Status.CANCELLED
    )

    completion_percentage = (
        round((completed_orders / total_orders) * 100) if total_orders else 0
    )

    cancelled_percentage = (
        round((cancelled_orders / total_orders) * 100) if total_orders else 0
    )

    paid_orders = buyer.orders.filter(payment_status=Order.PaymentStatus.PAID)

    total_spent = paid_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    total_paid_orders = paid_orders.count()

    average_order_value = (
        total_spent / total_paid_orders if total_paid_orders else Decimal("0.00")
    )

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
            (timezone.now().year - buyer.date_joined.year) * 12
            + timezone.now().month
            - buyer.date_joined.month
        ),
    )

    order_frequency = round(total_orders / months, 1)

    # Last 12 months
    chart_start = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=365)

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

    monthly_map = {
        item["month"].strftime("%b"): float(item["total"]) for item in monthly_spending
    }

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

    recent_orders = buyer.orders.select_related(
        "seller",
    ).prefetch_related("items__product").order_by("-created_at")[:10]

    for order in recent_orders:
        order.seller_name = order.seller.store_name if order.seller else "Unknown Seller"
        order.items_count = sum(item.quantity for item in order.items.all())

    order_content_type = ContentType.objects.get_for_model(Order)
    activity_logs = ActivityLog.objects.select_related("actor").filter(
        Q(actor=buyer)
        | Q(
            target_content_type=order_content_type,
            target_object_id__in=buyer.orders.values("pk"),
        )
    )[:20]

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
        "wishlist": services.get_user_wishlist(buyer),
        "activity_logs": activity_logs,
    }


def get_seller_detail(user_id):
    seller = Seller.objects.filter(id=user_id).first()

    if seller:
        total_sales = seller.orders.filter(
            status=Order.Status.DELIVERED
        ).aggregate(
            total=Coalesce(
                Sum("total"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
    else:
        total_sales = Decimal("0.00")

    total_products = seller.products.count()

    current_month_start = timezone.now().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    products_added_this_month = seller.products.filter(
        created_at__gte=current_month_start
    ).count()

    published_products = seller.products.filter(status=Product.Status.PUBLISHED).count()
    drafted_products = seller.products.filter(status=Product.Status.DRAFT).count()
    hidden_products = seller.products.filter(status=Product.Status.HIDDEN).count()
    pending_products = seller.products.filter(status=Product.Status.PENDING).count()
    archived_products = seller.products.filter(status=Product.Status.ARCHIVED).count()

    out_of_stock_products = seller.products.filter(
        Q(status=Product.Status.OUT_OF_STOCK) | Q(stock_quantity=0)
    ).count()

    published_catalog_percentage = (
        round((published_products / total_products) * 100, 1) if total_products else 0
    )

    previous_month_end = current_month_start - timedelta(seconds=1)
    previous_month_start = previous_month_end.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    total_orders = seller.orders.count()
    pending_orders = seller.orders.filter(status=Order.Status.PENDING).count()
    processing_orders = seller.orders.filter(status=Order.Status.PROCESSING).count()
    shipped_orders = seller.orders.filter(status=Order.Status.SHIPPED).count()
    completed_orders = seller.orders.filter(status=Order.Status.DELIVERED).count()

    today = timezone.localdate()

    today_orders = seller.orders.filter(created_at__date=today).count()

    orders = (
        seller.orders.select_related("user")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    completed_order_percentage = (
        round((completed_orders / total_orders) * 100, 1) if total_orders else 0
    )
    cancelled_orders = seller.orders.filter(status=Order.Status.CANCELLED).count()

    cancelled_order_percentage = (
        round((cancelled_orders / total_orders) * 100, 1) if total_orders else 0
    )
    previous_month_orders = seller.orders.filter(
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    ).count()

    if previous_month_orders:
        order_change = round(
            ((total_orders - previous_month_orders) / previous_month_orders) * 100, 1
        )
    else:
        order_change = 100 if total_orders else 0

    order_increased = total_orders >= previous_month_orders

    lifetime_revenue = seller.orders.filter(
        status=Order.Status.DELIVERED
    ).aggregate(
        total=Coalesce(
            Sum("total"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )["total"]

    current_month_revenue = seller.orders.filter(
        status=Order.Status.DELIVERED,
        created_at__gte=current_month_start,
    ).aggregate(
        total=Coalesce(
            Sum("total"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )["total"]

    previous_month_revenue = seller.orders.filter(
        status=Order.Status.DELIVERED,
        created_at__gte=previous_month_start,
        created_at__lt=current_month_start,
    ).aggregate(
        total=Coalesce(
            Sum("total"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )["total"]

    if previous_month_revenue:
        revenue_growth = round(
            ((current_month_revenue - previous_month_revenue) / previous_month_revenue)
            * 100,
            1,
        )
    else:
        revenue_growth = 100 if current_month_revenue else 0

    monthly_revenue = current_month_revenue

    average_order_value = (
        round(lifetime_revenue / total_orders, 2)
        if total_orders
        else Decimal("0.00")
    )

    preferred_category = (
        seller.products.exclude(category=None)
        .values("category__name")
        .annotate(product_count=Count("id"))
        .order_by("-product_count")
        .first()
    )

    preferred_category = (
        preferred_category["category__name"] if preferred_category else "N/A"
    )

    best_selling_product = (
        OrderItem.objects.filter(
            order__seller=seller,
            order__status=Order.Status.DELIVERED,
        )
        .values("product__name")
        .annotate(quantity_sold=Sum("quantity"))
        .order_by("-quantity_sold")
        .first()
    )

    best_selling_product = (
        best_selling_product["product__name"] if best_selling_product else "N/A"
    )

    average_shipping_duration = seller.orders.filter(
        shipped_at__isnull=False,
        delivered_at__isnull=False,
    ).aggregate(
        avg=Avg(
            ExpressionWrapper(
                F("delivered_at") - F("shipped_at"),
                output_field=DurationField(),
            )
        )
    )["avg"]

    average_shipping_days = (
        round(average_shipping_duration.total_seconds() / 86400, 1)
        if average_shipping_duration
        else None
    )

    repeat_buyers = (
        seller.orders.values("user")
        .annotate(order_count=Count("id"))
        .filter(order_count__gte=2)
        .count()
    )

    total_buyers = seller.orders.values("user").distinct().count()

    repeat_buyers_rate = (
        round(repeat_buyers * 100 / total_buyers, 1) if total_buyers else 0
    )

    fulfilled_orders = seller.orders.filter(status=Order.Status.DELIVERED).count()

    fulfillment_rate = (
        round(fulfilled_orders * 100 / total_orders, 1) if total_orders else 0
    )

    products = seller.products.annotate(
        total_sales=Coalesce(
            Sum(
                "order_items__quantity",
                filter=Q(
                    order_items__order__status=Order.Status.DELIVERED
                ),
            ),
            0,
        )
    )

    top_buyers = (
        seller.orders.values(
            "user__id",
            "user__first_name",
            "user__last_name",
            "user__profile_image_url",
        )
        .annotate(
            total_orders=Count("id"),
            total_spent=Sum("total"),
        )
        .order_by("-total_spent")[:5]
    )
    customer_locations = (
        seller.orders.values("shipping_city")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    total_location_orders = seller.orders.count()

    for city in customer_locations:
        city["percentage"] = round(
            city["total"] * 100 / total_location_orders, 1
        )

    recent_customers = (
        seller.orders.values(
            "user__id",
            "user__first_name",
            "user__last_name",
        )
        .annotate(
            total_orders=Count("id"),
            total_spent=Sum("total"),
            last_order=Max("created_at"),
        )
        .order_by("-last_order")[:3]
    )
    for customer in recent_customers:
        customer["repeat_buyer"] = customer["total_orders"] >= 2

    delivered_percentage = (
        round((completed_orders / total_orders) * 100, 1) if total_orders else 0
    )

    top_selling_products = (
        OrderItem.objects.filter(
            order__seller=seller,
            order__status=Order.Status.DELIVERED,
        )
        .values("product__name")
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:5]
    )
    max_sold = top_selling_products[0]["total_sold"] if top_selling_products else 0

    for product in top_selling_products:
        product["percentage"] = (
            round(product["total_sold"] * 100 / max_sold, 1) if max_sold else 0
        )

    top_categories = (
        OrderItem.objects.filter(
            order__seller=seller,
            order__status=Order.Status.DELIVERED,
        )
        .values("product__category__name")
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:5]
    )

    max_category_sales = top_categories[0]["total_sold"] if top_categories else 0

    for category in top_categories:
        category["percentage"] = (
            round(category["total_sold"] * 100 / max_category_sales, 1)
            if max_category_sales
            else 0
        )

    DONUT_CIRCUMFERENCE = 2 * math.pi * 60

    donut_offset = round(
        DONUT_CIRCUMFERENCE * (100 - delivered_percentage) / 100, 1
    )

    documents = get_seller_application_documents(seller)

    order_content_type = ContentType.objects.get_for_model(Order)
    product_content_type = ContentType.objects.get_for_model(Product)
    activity_logs = ActivityLog.objects.select_related("actor").filter(
        Q(actor=seller.user)
        | Q(
            target_content_type=order_content_type,
            target_object_id__in=seller.orders.values("pk"),
        )
        | Q(
            target_content_type=product_content_type,
            target_object_id__in=seller.products.values("pk"),
        )
    )[:20]

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
        "monthly_revenue": monthly_revenue,
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
    }


def get_pending_sellers():
    return Seller.objects.filter(status=Seller.Status.PENDING).all()


def get_pending_seller(seller_id):
    seller = Seller.objects.select_related(
        "application",
        "profile",
        "settings",
        "user",
    ).get(
        id=seller_id,
        status=Seller.Status.PENDING,
    )

    application = seller.application
    profile = getattr(seller, "profile", None)
    settings = getattr(seller, "settings", None)

    verification_score = 0

    if seller.store_name:
        verification_score += 15
    if seller.store_email:
        verification_score += 15
    if seller.store_description:
        verification_score += 20
    if seller.store_logo:
        verification_score += 15
    if seller.store_banner:
        verification_score += 15
    if seller.business_address:
        verification_score += 20

    trust_score = verification_score

    if trust_score >= 80:
        risk_level = "low"
    elif trust_score >= 60:
        risk_level = "medium"
    else:
        risk_level = "high"

    required_documents = len(SellerApplicationDocument.DocumentType.choices)
    uploaded_documents = application.documents.count()
    verified_documents = application.documents.filter(verified=True).count()
    documents_submitted = uploaded_documents

    flags_raised = application.flags.filter(resolved=False).count()

    document_completeness = (
        int(uploaded_documents / required_documents * 100) if required_documents else 0
    )

    profile_fields = [
        seller.store_name,
        seller.store_email,
        seller.store_description,
        seller.store_logo,
        seller.store_banner,
        seller.business_address,
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
        verified_documents >= 2,  # CNIC Front + Back
        settings.business_registration_verified if settings else False,
        settings.bank_account_verified if settings else False,
        settings.address_verified if settings else False,
    ]

    compliance_score = int(sum(compliance_checks) / len(compliance_checks) * 100)

    payment_verified = settings.bank_account_verified if settings else False

    duplicate_accounts = None  # Future feature
    blacklist_clean = None  # Future feature

    CIRCUMFERENCE = 2 * math.pi * 60
    score_offset = CIRCUMFERENCE * (1 - trust_score / 100)

    documents = get_seller_application_documents(seller)

    # -----------------------------
    # Identity Documents
    # -----------------------------
    cnic_front = documents.get("cnic_front")
    cnic_back = documents.get("cnic_back")

    identity_verified = (
        cnic_front
        and cnic_back
        and cnic_front.file
        and cnic_back.file
        and cnic_front.verified
        and cnic_back.verified
    )

    # -----------------------------
    # Email Verification
    # -----------------------------
    email_verified = EmailAddress.objects.filter(
        user=seller.user,
        verified=True,
    ).exists()

    # -----------------------------
    # Store Profile Completeness
    # -----------------------------
    store_profile_complete = all(
        [
            seller.store_logo,
            seller.store_banner,
            seller.store_description,
        ]
    )

    # -----------------------------
    # Business Address
    # -----------------------------
    business_address = bool(seller.business_address)

    return {
        "seller": seller,
        "application": application,
        "verification_score": verification_score,
        "trust_score": trust_score,
        "score_offset": score_offset,
        "risk_level": risk_level,
        "documents_submitted": documents_submitted,
        "verified_documents": verified_documents,
        "document_completeness": document_completeness,
        "flags_raised": flags_raised,
        "profile_completeness": profile_completeness,
        "compliance_score": compliance_score,
        "payment_verified": payment_verified,
        "duplicate_accounts": duplicate_accounts,
        "blacklist_clean": blacklist_clean,
        "documents": documents,
        # Checklist
        "identity_verified": identity_verified,
        "email_verified": email_verified,
        "store_profile_complete": store_profile_complete,
        "business_address": business_address,
    }


def get_products_catalog():
    published_products = Product.objects.filter(
        status=Product.Status.PUBLISHED,
    ).count()

    total_products = Product.objects.all().count()

    published_percentage_catalog = (
        round((published_products / total_products) * 100, 1) if total_products else 0
    )

    hidden_products = Product.objects.filter(status=Product.Status.HIDDEN).count()

    out_of_stock_products = Product.objects.filter(
        Q(status=Product.Status.OUT_OF_STOCK) | Q(stock_quantity=0)
    ).count()

    featured_products = Product.objects.filter(is_featured=True).count()
    archived_products = Product.objects.filter(status=Product.Status.ARCHIVED).count()
    drafted_products = Product.objects.filter(status=Product.Status.DRAFT).count()

    products = Product.objects.all().annotate(
        total_orders=Coalesce(
            Sum(
                "order_items__quantity",
                filter=Q(
                    order_items__order__status=Order.Status.DELIVERED
                ),
            ),
            0,
        )
    )

    recently_added_products = products.order_by("-created_at")[:10]
    pending_approval_products = products.filter(status=Product.Status.PENDING)

    return {
        "published_products": published_products,
        "total_products": total_products,
        "published_percentage_catalog": published_percentage_catalog,
        "hidden_products": hidden_products,
        "out_of_stock_products": out_of_stock_products,
        "featured_products": featured_products,
        "archived_products": archived_products,
        "drafted_products": drafted_products,
        "products": products,
        "recently_added_products": recently_added_products,
        "pending_approval_products": pending_approval_products,
    }


def send_admin_email(
    *,
    user,
    subject,
    message,
    button_text=None,
    button_url=None,
    attachments=None,
):
    """
    Sends a branded MarketSphere email to a user.
    """
    context = {
        "user": user,
        "message": message,
        "button_text": button_text,
        "button_url": button_url,
    }

    html_body = render_to_string("email_components/send_email.html", context)
    text_body = render_to_string("email_components/send_email.txt", context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_body, "text/html")

    if attachments:
        for uploaded_file in attachments:
            email.attach(
                uploaded_file.name,
                uploaded_file.read(),
                uploaded_file.content_type,
            )

    email.send(fail_silently=False)


def get_product_performance(product):
    now = timezone.now()

    # ---------------------------------------------------------
    # CURRENT MONTH
    # ---------------------------------------------------------
    current_month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    # ---------------------------------------------------------
    # PREVIOUS MONTH
    # ---------------------------------------------------------
    if current_month_start.month == 1:
        previous_month_start = current_month_start.replace(
            year=current_month_start.year - 1, month=12
        )
    else:
        previous_month_start = current_month_start.replace(
            month=current_month_start.month - 1
        )

    delivered = Order.Status.DELIVERED

    # ---------------------------------------------------------
    # ALL-TIME PERFORMANCE
    # ---------------------------------------------------------
    all_time = product.order_items.filter(
        order__status=delivered,
    ).aggregate(
        sales=Sum("total"),
        orders=Count("order", distinct=True),
        units=Sum("quantity"),
    )

    total_sales = all_time["sales"] or Decimal("0.00")
    total_orders = all_time["orders"] or 0
    units_sold = all_time["units"] or 0

    # ---------------------------------------------------------
    # CURRENT MONTH PERFORMANCE
    # ---------------------------------------------------------
    current_month = product.order_items.filter(
        order__status=delivered,
        order__delivered_at__gte=current_month_start,
        order__delivered_at__lt=now,
    ).aggregate(
        sales=Sum("total"),
        orders=Count("order", distinct=True),
        units=Sum("quantity"),
    )

    current_sales = current_month["sales"] or Decimal("0.00")
    current_orders = current_month["orders"] or 0
    current_units = current_month["units"] or 0

    # ---------------------------------------------------------
    # PREVIOUS MONTH PERFORMANCE
    # ---------------------------------------------------------
    previous_month = product.order_items.filter(
        order__status=delivered,
        order__delivered_at__gte=previous_month_start,
        order__delivered_at__lt=current_month_start,
    ).aggregate(
        sales=Sum("total"),
        orders=Count("order", distinct=True),
        units=Sum("quantity"),
    )

    previous_sales = previous_month["sales"] or Decimal("0.00")
    previous_orders = previous_month["orders"] or 0
    previous_units = previous_month["units"] or 0

    def calculate_change(current, previous):
        if previous == 0:
            if current == 0:
                return 0
            return None
        return round(((current - previous) / previous) * 100, 1)

    sales_change = calculate_change(current_sales, previous_sales)
    orders_change = calculate_change(current_orders, previous_orders)
    units_change = calculate_change(current_units, previous_units)

    sales_increased = current_sales > previous_sales
    orders_increased = current_orders > previous_orders
    units_increased = current_units > previous_units

    revenue = total_sales
    return_rate = None
    current_stock = product.stock_quantity
    low_stock_threshold = get_catalog_settings().low_stock_threshold
    wishlist_adds = product.wishlisted_by.count()
    product_views = None

    reserved_units = (
        product.order_items.filter(
            order__status__in=[
                Order.Status.PENDING,
                Order.Status.CONFIRMED,
                Order.Status.PROCESSING,
                Order.Status.SHIPPED,
            ]
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    if current_stock <= 0:
        stock_health = "out_of_stock"
    elif current_stock <= low_stock_threshold:
        stock_health = "low"
    else:
        stock_health = "healthy"

    available_stock = current_stock - reserved_units

    return {
        "total_sales": total_sales,
        "sales_change": sales_change,
        "sales_increased": sales_increased,
        "total_orders": total_orders,
        "orders_change": orders_change,
        "orders_increased": orders_increased,
        "units_sold": units_sold,
        "units_change": units_change,
        "units_increased": units_increased,
        "revenue": revenue,
        "return_rate": return_rate,
        "current_stock": current_stock,
        "low_stock_threshold": low_stock_threshold,
        "wishlist_adds": wishlist_adds,
        "product_views": product_views,
        "reserved_units": reserved_units,
        "available_stock": available_stock,
        "stock_health": stock_health,
    }


def get_product_orders(product):
    statuses = Order.Status

    product_order_items = product.order_items.select_related(
        "order",
        "order__seller",
        "order__user",
    )

    total_orders = product_order_items.values("order_id").distinct().count()

    pending_orders = (
        product_order_items.filter(order__status=statuses.PENDING)
        .values("order_id").distinct().count()
    )
    confirmed_orders = (
        product_order_items.filter(order__status=statuses.CONFIRMED)
        .values("order_id").distinct().count()
    )
    processing_orders = (
        product_order_items.filter(order__status=statuses.PROCESSING)
        .values("order_id").distinct().count()
    )
    shipped_orders = (
        product_order_items.filter(order__status=statuses.SHIPPED)
        .values("order_id").distinct().count()
    )
    delivered_orders = (
        product_order_items.filter(order__status=statuses.DELIVERED)
        .values("order_id").distinct().count()
    )
    cancelled_orders = (
        product_order_items.filter(order__status=statuses.CANCELLED)
        .values("order_id").distinct().count()
    )

    refunded_orders = (
        product_order_items.filter(order__payment_status=Order.PaymentStatus.REFUNDED)
        .values("order_id").distinct().count()
    )

    return_orders = None

    orders = (
        Order.objects.filter(items__product=product)
        .select_related("user", "seller")
        .prefetch_related(
            Prefetch(
                "items",
                queryset=OrderItem.objects.filter(product=product),
                to_attr="product_items",
            )
        )
        .order_by("-created_at")
        .distinct()
    )

    return {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "confirmed_orders": confirmed_orders,
        "processing_orders": processing_orders,
        "shipped_orders": shipped_orders,
        "delivered_orders": delivered_orders,
        "cancelled_orders": cancelled_orders,
        "return_orders": return_orders,
        "refunded_orders": refunded_orders,
        "orders": orders,
    }


def get_product_revenue_trend(product):
    now = timezone.localtime(timezone.now())

    current_week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    week_starts = [current_week_start - timedelta(weeks=i) for i in range(7, -1, -1)]

    first_week_start = week_starts[0]
    next_week_start = current_week_start + timedelta(weeks=1)

    weekly_sales = (
        product.order_items.filter(
            order__status=Order.Status.DELIVERED,
            order__delivered_at__gte=first_week_start,
            order__delivered_at__lt=next_week_start,
        )
        .values("order__delivered_at")
        .annotate(revenue=Sum("total"))
    )

    revenue_by_week = {week_start: Decimal("0.00") for week_start in week_starts}

    for row in weekly_sales:
        delivered_at = timezone.localtime(row["order__delivered_at"])
        week_start = (delivered_at - timedelta(days=delivered_at.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if week_start in revenue_by_week:
            revenue_by_week[week_start] += row["revenue"] or Decimal("0.00")

    trend = []

    for week_start in week_starts:
        trend.append(
            {
                "date": week_start,
                "label": week_start.strftime("%b %d").replace(" 0", " "),
                "revenue": revenue_by_week[week_start],
                "revenue_display": (f"Rs. {revenue_by_week[week_start]:,.0f}"),
            }
        )
    return trend


def get_product_order_status_mix(product):
    statuses = Order.Status

    status_counts = product.order_items.values("order__status").annotate(
        total=Count("order", distinct=True)
    )

    counts = {row["order__status"]: row["total"] for row in status_counts}
    total_orders = sum(counts.values())

    delivered = counts.get(statuses.DELIVERED, 0)
    pending = counts.get(statuses.PENDING, 0)
    confirmed = counts.get(statuses.CONFIRMED, 0)
    processing = counts.get(statuses.PROCESSING, 0)
    shipped = counts.get(statuses.SHIPPED, 0)
    cancelled = counts.get(statuses.CANCELLED, 0)

    def percentage(value):
        if total_orders == 0:
            return 0
        return round((value / total_orders) * 100, 1)

    return {
        "total": total_orders,
        "delivered": delivered,
        "delivered_percentage": percentage(delivered),
        "pending": pending,
        "pending_percentage": percentage(pending),
        "confirmed": confirmed,
        "confirmed_percentage": percentage(confirmed),
        "processing": processing,
        "processing_percentage": percentage(processing),
        "shipped": shipped,
        "shipped_percentage": percentage(shipped),
        "cancelled": cancelled,
        "cancelled_percentage": percentage(cancelled),
    }


def get_product_customer_locations(product):
    product_orders = product.order_items.values("order_id").distinct()
    total_orders = product_orders.count()

    if total_orders == 0:
        return []

    city_counts = (
        Order.objects.filter(id__in=product_orders)
        .exclude(shipping_city__isnull=True)
        .exclude(shipping_city__exact="")
        .values("shipping_city")
        .annotate(orders=Count("id", distinct=True))
        .order_by("-orders", "shipping_city")
    )

    cities = list(city_counts)
    top_cities = cities[:4]
    top_count = sum(city["orders"] for city in top_cities)

    locations = []
    for city in top_cities:
        percentage = round((city["orders"] / total_orders) * 100, 1)
        locations.append(
            {
                "name": city["shipping_city"],
                "orders": city["orders"],
                "percentage": percentage,
            }
        )

    other_orders = total_orders - top_count
    if other_orders > 0:
        locations.append(
            {
                "name": "Other",
                "orders": other_orders,
                "percentage": round((other_orders / total_orders) * 100, 1),
            }
        )

    return locations


def get_product_kpis(product):
    now = timezone.now()

    current_month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    if current_month_start.month == 1:
        previous_month_start = current_month_start.replace(
            year=current_month_start.year - 1, month=12
        )
    else:
        previous_month_start = current_month_start.replace(
            month=current_month_start.month - 1
        )

    total_wishlist_adds = product.wishlisted_by.count()
    current_wishlist_adds = product.wishlisted_by.filter(
        created_at__gte=current_month_start
    ).count()
    previous_wishlist_adds = product.wishlisted_by.filter(
        created_at__gte=previous_month_start, created_at__lt=current_month_start
    ).count()

    def calculate_change(current, previous):
        if previous == 0:
            if current == 0:
                return 0
            return None
        return round(((current - previous) / previous) * 100, 1)

    wishlist_change = calculate_change(current_wishlist_adds, previous_wishlist_adds)
    wishlist_increased = current_wishlist_adds > previous_wishlist_adds

    order_data = product.order_items.filter(
        order__status=Order.Status.DELIVERED,
    ).aggregate(
        revenue=Sum("total"),
        orders=Count("order", distinct=True),
    )

    revenue = order_data["revenue"] or Decimal("0.00")
    total_orders = order_data["orders"] or 0

    if total_orders:
        average_order_value = revenue / total_orders
    else:
        average_order_value = Decimal("0.00")

    current_orders_data = product.order_items.filter(
        order__status=Order.Status.DELIVERED,
        order__delivered_at__gte=current_month_start,
    ).aggregate(
        revenue=Sum("total"),
        orders=Count("order", distinct=True),
    )

    current_revenue = current_orders_data["revenue"] or Decimal("0.00")
    current_orders = current_orders_data["orders"] or 0
    current_aov = (
        current_revenue / current_orders if current_orders else Decimal("0.00")
    )

    previous_orders_data = product.order_items.filter(
        order__status=Order.Status.DELIVERED,
        order__delivered_at__gte=previous_month_start,
        order__delivered_at__lt=current_month_start,
    ).aggregate(
        revenue=Sum("total"),
        orders=Count("order", distinct=True),
    )

    previous_revenue = previous_orders_data["revenue"] or Decimal("0.00")
    previous_orders = previous_orders_data["orders"] or 0
    previous_aov = (
        previous_revenue / previous_orders if previous_orders else Decimal("0.00")
    )

    aov_change = calculate_change(current_aov, previous_aov)
    aov_increased = current_aov > previous_aov

    conversion_rate = None
    conversion_change = None
    conversion_increased = None

    return_rate = None
    return_change = None
    return_increased = None

    return {
        "wishlist_adds": total_wishlist_adds,
        "wishlist_change": wishlist_change,
        "wishlist_increased": wishlist_increased,
        "conversion_rate": conversion_rate,
        "conversion_change": conversion_change,
        "conversion_increased": conversion_increased,
        "average_order_value": average_order_value,
        "aov_change": aov_change,
        "aov_increased": aov_increased,
        "return_rate": return_rate,
        "return_change": return_change,
        "return_increased": return_increased,
    }


def get_product_moderation(product):
    seller = product.seller

    approval_status = {
        "label": "Approved" if product.is_approved else "Not Approved",
        "class": "c-success" if product.is_approved else "c-warning",
    }

    publication_labels = {
        Product.Status.DRAFT: "Draft",
        Product.Status.PUBLISHED: "Published",
        Product.Status.HIDDEN: "Hidden",
        Product.Status.OUT_OF_STOCK: "Out of Stock",
        Product.Status.ARCHIVED: "Archived",
        Product.Status.PENDING: "Pending",
        Product.Status.REJECTED: "Rejected",
    }

    publication_status = {
        "label": publication_labels.get(
            product.status,
            product.status.title(),
        ),
        "class": (
            "c-success" if product.status == Product.Status.PUBLISHED else "c-warning"
        ),
    }

    is_visible = product.status == Product.Status.PUBLISHED and product.is_approved
    visibility = {
        "label": "Visible" if is_visible else "Hidden",
        "class": "c-success" if is_visible else "c-muted",
    }

    featured_status = {
        "label": "Featured" if product.is_featured else "Not Featured",
        "class": "c-accent" if product.is_featured else "c-muted",
    }

    seller_verified = bool(seller and seller.status == seller.Status.VERIFIED)
    seller_verification = {
        "label": "Verified" if seller_verified else "Not Verified",
        "class": "c-success" if seller_verified else "c-warning",
    }

    product_information_complete = bool(product.name and product.description)
    image_count = product.images.count()
    images_available = image_count > 0
    category_assigned = product.category is not None
    brand_assigned = product.brand is not None

    price_valid = (
        product.price is not None
        and product.price > 0
        and (
            product.discount_price is None
            or (product.discount_price > 0 and product.discount_price < product.price)
        )
    )

    stock_available = product.stock_quantity > 0
    required_information_provided = bool(product.sku and product.barcode)

    description_length = len((product.description or "").strip())
    description_requires_review = description_length < 100

    policy_compliance = None
    moderation_score = None

    if product_information_complete and not description_requires_review:
        content_quality = {
            "label": "Good",
            "class": "c-success",
        }
    elif product_information_complete:
        content_quality = {
            "label": "Needs Review",
            "class": "c-warning",
        }
    else:
        content_quality = {
            "label": "Incomplete",
            "class": "c-danger",
        }

    checklist = [
        {
            "title": "Product Information Complete",
            "description": "Name and description provided",
            "complete": product_information_complete,
            "warning": False,
        },
        {
            "title": "Images Available",
            "description": f"{image_count} product image{'' if image_count == 1 else 's'} uploaded",
            "complete": images_available,
            "warning": False,
        },
        {
            "title": "Category Assigned",
            "description": product.category.name if product.category else "No category assigned",
            "complete": category_assigned,
            "warning": False,
        },
        {
            "title": "Brand Assigned",
            "description": product.brand.name if product.brand else "No brand assigned",
            "complete": brand_assigned,
            "warning": False,
        },
        {
            "title": "Price Valid",
            "description": "Regular and discount price set correctly" if price_valid else "Price information requires review",
            "complete": price_valid,
            "warning": not price_valid,
        },
        {
            "title": "Stock Available",
            "description": f"{product.stock_quantity} units in stock",
            "complete": stock_available,
            "warning": not stock_available,
        },
        {
            "title": "Seller Verified",
            "description": f"{seller.store_name} is a verified seller" if seller else "No seller assigned",
            "complete": seller_verified,
            "warning": not seller_verified,
        },
        {
            "title": "Required Information Provided",
            "description": "SKU and barcode present" if required_information_provided else "SKU or barcode is missing",
            "complete": required_information_provided,
            "warning": not required_information_provided,
        },
        {
            "title": "Description Review",
            "description": "Long description could be more detailed for SEO" if description_requires_review else "Description length looks good",
            "complete": not description_requires_review,
            "warning": description_requires_review,
        },
    ]

    return {
        "approval_status": approval_status,
        "publication_status": publication_status,
        "visibility": visibility,
        "featured_status": featured_status,
        "policy_compliance": policy_compliance,
        "content_quality": content_quality,
        "seller_verification": seller_verification,
        "moderation_score": moderation_score,
        "checklist": checklist,
    }


def get_product_risk_review(product):
    seller = product.seller
    risks = []

    duplicate_queryset = Product.objects.exclude(pk=product.pk)

    duplicate_sku = (
        product.sku and duplicate_queryset.filter(sku=product.sku).exists()
    )

    duplicate_barcode = (
        product.barcode and duplicate_queryset.filter(barcode=product.barcode).exists()
    )

    duplicate_name = duplicate_queryset.filter(name__iexact=product.name).exists()

    if duplicate_sku or duplicate_barcode:
        risks.append(
            {
                "title": "Duplicate Product",
                "description": "Matching SKU or barcode found",
                "level": "High",
                "class": "is-high",
            }
        )
    elif duplicate_name:
        risks.append(
            {
                "title": "Duplicate Product",
                "description": "Another listing has the same product name",
                "level": "Medium",
                "class": "is-medium",
            }
        )
    else:
        risks.append(
            {
                "title": "Duplicate Product",
                "description": "No matching SKU, barcode, or product name found",
                "level": "Low",
                "class": "",
            }
        )

    if product.brand:
        risks.append(
            {
                "title": "Counterfeit Risk",
                "description": "Brand is assigned to the product",
                "level": "Not Available",
                "class": "",
            }
        )
    else:
        risks.append(
            {
                "title": "Counterfeit Risk",
                "description": "No brand assigned for verification",
                "level": "Not Available",
                "class": "",
            }
        )

    risks.append(
        {
            "title": "Copyright Risk",
            "description": "Copyright ownership cannot be verified from current data",
            "level": "Not Available",
            "class": "",
        }
    )

    if product.category:
        risks.append(
            {
                "title": "Restricted Category",
                "description": f"Category assigned: {product.category.name}; restricted-category rules are not configured",
                "level": "Not Available",
                "class": "",
            }
        )
    else:
        risks.append(
            {
                "title": "Restricted Category",
                "description": "No category assigned",
                "level": "Medium",
                "class": "is-medium",
            }
        )

    if product.price and product.discount_price:
        discount_percentage = (
            (product.price - product.discount_price) / product.price
        ) * 100

        if discount_percentage >= 50:
            pricing_level = "Medium"
            pricing_class = "is-medium"
            pricing_description = f"{round(discount_percentage)}% discount detected"
        else:
            pricing_level = "Low"
            pricing_class = ""
            pricing_description = f"{round(discount_percentage)}% discount"

    elif product.price:
        pricing_level = "Low"
        pricing_class = ""
        pricing_description = "No discount currently applied"
    else:
        pricing_level = "Medium"
        pricing_class = "is-medium"
        pricing_description = "Product price is missing"

    risks.append(
        {
            "title": "Suspicious Pricing",
            "description": pricing_description,
            "level": pricing_level,
            "class": pricing_class,
        }
    )

    risks.append(
        {
            "title": "Policy Violation",
            "description": "No policy violation data is available",
            "level": "Not Available",
            "class": "",
        }
    )

    missing_fields = []
    if not product.name:
        missing_fields.append("name")
    if not product.description:
        missing_fields.append("description")
    if not product.sku:
        missing_fields.append("SKU")
    if not product.barcode:
        missing_fields.append("barcode")
    if not product.category:
        missing_fields.append("category")

    if missing_fields:
        risks.append(
            {
                "title": "Invalid Product Information",
                "description": ("Missing: " + ", ".join(missing_fields)),
                "level": "Medium",
                "class": "is-medium",
            }
        )
    else:
        risks.append(
            {
                "title": "Invalid Product Information",
                "description": "All available required fields are populated",
                "level": "Low",
                "class": "",
            }
        )

    if not seller:
        risks.append(
            {
                "title": "Seller Risk",
                "description": "No seller assigned",
                "level": "High",
                "class": "is-high",
            }
        )
    elif seller.status == seller.Status.VERIFIED:
        risks.append(
            {
                "title": "Seller Risk",
                "description": "Seller is verified",
                "level": "Low",
                "class": "",
            }
        )
    elif seller.status in (
        seller.Status.SUSPENDED,
        seller.Status.BLOCKED,
        seller.Status.REJECTED,
    ):
        risks.append(
            {
                "title": "Seller Risk",
                "description": f"Seller status: {seller.get_status_display()}",
                "level": "High",
                "class": "is-high",
            }
        )
    else:
        risks.append(
            {
                "title": "Seller Risk",
                "description": f"Seller status: {seller.get_status_display()}",
                "level": "Medium",
                "class": "is-medium",
            }
        )

    image_count = product.images.count()
    if image_count == 0:
        risks.append(
            {
                "title": "Image Quality",
                "description": "No product images uploaded",
                "level": "Medium",
                "class": "is-medium",
            }
        )
    else:
        risks.append(
            {
                "title": "Image Quality",
                "description": f"{image_count} product image{'' if image_count == 1 else 's'} uploaded; image resolution is not stored",
                "level": "Not Available",
                "class": "",
            }
        )

    if product.brand:
        risks.append(
            {
                "title": "Trademark Risk",
                "description": f"Brand assigned: {product.brand.name}; trademark ownership cannot be verified",
                "level": "Not Available",
                "class": "",
            }
        )
    else:
        risks.append(
            {
                "title": "Trademark Risk",
                "description": "No brand assigned",
                "level": "Not Available",
                "class": "",
            }
        )

    high_count = sum(1 for risk in risks if risk["level"] == "High")
    medium_count = sum(1 for risk in risks if risk["level"] == "Medium")
    low_count = sum(1 for risk in risks if risk["level"] == "Low")
    unavailable_count = sum(1 for risk in risks if risk["level"] == "Not Available")

    return {
        "risks": risks,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "unavailable_count": unavailable_count,
    }


def get_product_seller_summary(product):
    seller = product.seller

    if not seller:
        return {
            "verification_status": {
                "label": "Not Available",
                "class": "c-muted",
            },
            "seller_status": {
                "label": "Not Available",
                "class": "c-muted",
            },
            "store_rating": None,
            "total_products": 0,
            "seller_orders": 0,
            "seller_revenue": Decimal("0.00"),
        }

    is_verified = seller.status == seller.Status.VERIFIED

    verification_status = {
        "label": "Verified" if is_verified else "Not Verified",
        "class": "c-success" if is_verified else "c-warning",
    }

    seller_status_labels = {
        seller.Status.PENDING: "Pending",
        seller.Status.VERIFIED: "Active",
        seller.Status.DEACTIVATED: "Inactive",
        seller.Status.SUSPENDED: "Suspended",
        seller.Status.BLOCKED: "Blocked",
        seller.Status.REJECTED: "Rejected",
    }

    seller_status_classes = {
        seller.Status.PENDING: "c-warning",
        seller.Status.VERIFIED: "c-success",
        seller.Status.DEACTIVATED: "c-muted",
        seller.Status.SUSPENDED: "c-danger",
        seller.Status.BLOCKED: "c-danger",
        seller.Status.REJECTED: "c-danger",
    }

    seller_status = {
        "label": seller_status_labels.get(seller.status, seller.status),
        "class": seller_status_classes.get(seller.status, "c-muted"),
    }

    store_rating = None
    total_products = seller.products.count()
    seller_orders = seller.orders.count()

    revenue_data = seller.orders.filter(
        status=Order.Status.DELIVERED,
    ).aggregate(revenue=Sum("total"))

    seller_revenue = revenue_data["revenue"] or Decimal("0.00")

    return {
        "verification_status": verification_status,
        "seller_status": seller_status,
        "store_rating": store_rating,
        "total_products": total_products,
        "seller_orders": seller_orders,
        "seller_revenue": seller_revenue,
    }


def get_product_detail(product_slug):
    product = (
        Product.objects.filter(slug=product_slug)
        .select_related("category", "brand", "seller")
        .prefetch_related("images")
        .first()
    )

    if not product:
        return None

    performance = get_product_performance(product)
    order_data = get_product_orders(product)
    revenue_trend = get_product_revenue_trend(product)
    customer_locations = get_product_customer_locations(product)
    kpis = get_product_kpis(product)
    moderation = get_product_moderation(product)
    risk_review = get_product_risk_review(product)
    seller_summary = get_product_seller_summary(product)
    brands = Brand.objects.filter(is_active=True).order_by("name")
    status_mix = get_product_order_status_mix(product)

    return {
        "product": product,
        "performance": performance,
        "brands": brands,
        "order_data": order_data,
        "revenue_trend": revenue_trend,
        "status_mix": status_mix,
        "customer_locations": customer_locations,
        "kpis": kpis,
        "moderation": moderation,
        "risk_review": risk_review,
        "seller_summary": seller_summary,
    }


def export_order_history(user_id):
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
    writer.writerow(
        [
            "Order Number",
            "Order Date",
            "Status",
            "Payment Status",
            "Seller",
            "Products",
            "Subtotal",
            "Shipping",
            "Discount",
            "Tax",
            "Total",
            "Tracking Number",
            "Courier",
        ]
    )

    for order in orders:
        products = ", ".join(
            [f"{item.product.name} (x{item.quantity})" for item in order.items.all()]
        )

        writer.writerow(
            [
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
            ]
        )

    return response


def export_seller_orders(seller):
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
    writer.writerow(
        [
            "Order Number",
            "Order Date",
            "Status",
            "Payment Status",
            "Customer",
            "Products",
            "Subtotal",
            "Shipping",
            "Discount",
            "Tax",
            "Total",
            "Tracking Number",
            "Courier",
            "Shipped At",
            "Delivered At",
        ]
    )

    for order in orders:
        products = ", ".join(
            f"{item.product.name} (x{item.quantity})" for item in order.items.all()
        )

        writer.writerow(
            [
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
            ]
        )

    return response


def get_categories_data():
    now = timezone.now()

    categories = (
        Category.objects.annotate(
            product_count=Count("products", distinct=True),
            subcategory_count=Count("children", distinct=True),
        )
        .select_related("parent")
        .prefetch_related("products")
        .order_by("name")
    )

    total_categories = categories.count()
    active_categories = categories.filter(is_active=True).count()
    inactive_categories = categories.filter(is_active=False).count()

    percentage_active = (
        (active_categories / total_categories) * 100 if total_categories else 0
    )

    categories_added_this_month = categories.filter(
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()

    total_parent_categories = categories.filter(parent__isnull=True).count()
    total_subcategories = categories.filter(parent__isnull=False).count()
    empty_categories = categories.filter(product_count=0).count()
    products_assigned = Product.objects.filter(category__isnull=False).count()

    average_products_per_category = (
        products_assigned / total_categories if total_categories else 0
    )

    category_nodes = {}

    for category in categories:
        category_products = []
        for product in category.products.all():
            sold_units = (
                product.order_items.filter(
                    order__payment_status=Order.PaymentStatus.PAID
                ).aggregate(total=Coalesce(Sum("quantity"), 0))["total"]
                or 0
            )
            category_products.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "slug": product.slug,
                    "sku": product.sku or "",
                    "seller": getattr(product.seller, "store_name", "") if product.seller else "",
                    "price": str(product.discount_price or product.price or ""),
                    "stock_quantity": product.stock_quantity,
                    "status": product.status,
                    "orders": sold_units,
                }
            )

        paid_order_items = OrderItem.objects.filter(
            product__category=category,
            order__payment_status=Order.PaymentStatus.PAID,
        )
        order_summary = paid_order_items.aggregate(
            order_count=Count("order", distinct=True),
            revenue=Coalesce(
                Sum("total"),
                0,
                output_field=DecimalField(max_digits=18, decimal_places=2),
            ),
        )
        top_products = sorted(
            [product for product in category_products if product["orders"]],
            key=lambda product: product["orders"],
            reverse=True,
        )[:4]
        product_queryset = category.products.all()

        revenue_trend = []
        growth_trend = []
        for month_offset in range(8, -1, -1):
            month_index = now.year * 12 + now.month - 1 - month_offset
            month_start = now.replace(
                year=month_index // 12,
                month=month_index % 12 + 1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            next_month = (month_start + timedelta(days=32)).replace(day=1)
            month_summary = paid_order_items.filter(
                order__created_at__gte=month_start,
                order__created_at__lt=next_month,
            ).aggregate(
                order_count=Count("order", distinct=True),
                revenue=Coalesce(
                    Sum("total"),
                    0,
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
            )
            label = month_start.strftime("%b")
            revenue_trend.append(
                {
                    "label": label,
                    "value": str(month_summary["revenue"] or 0),
                }
            )
            growth_trend.append(
                {
                    "label": label,
                    "value": month_summary["order_count"] or 0,
                }
            )

        category_nodes[category.id] = {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description or "",
            "icon": category.icon or "bi bi-grid",
        "image": category.image if category.image else "",
            "is_active": category.is_active,
            "status": "active" if category.is_active else "inactive",
            "parent_id": category.parent_id,
            "_parentName": category.parent.name if category.parent else None,
            "parent": (
                {
                    "id": category.parent.id,
                    "name": category.parent.name,
                    "slug": category.parent.slug,
                }
                if category.parent
                else None
            ),
            "product_count": category.product_count,
            "products": category_products,
            "subcategory_count": category.subcategory_count,
            "children": [],
            "analytics": {
                "published": product_queryset.filter(status=Product.Status.PUBLISHED).count(),
                "pending": product_queryset.filter(status=Product.Status.PENDING).count(),
                "out_of_stock": product_queryset.filter(status=Product.Status.OUT_OF_STOCK).count(),
                "orders": order_summary["order_count"] or 0,
                "revenue": str(order_summary["revenue"] or 0),
                "conversion_rate": None,
                "top_products": top_products,
                "revenue_trend": revenue_trend,
                "growth_trend": growth_trend,
            },
            "created_at": category.created_at.isoformat() if getattr(category, "created_at", None) else None,
            "updated_at": category.updated_at.isoformat() if getattr(category, "updated_at", None) else None,
            "created": category.created_at.strftime("%b %d, %Y") if getattr(category, "created_at", None) else None,
            "updated": category.updated_at.strftime("%b %d, %Y") if getattr(category, "updated_at", None) else None,
        }

    category_tree = []

    for category in categories:
        node = category_nodes[category.id]
        if category.parent_id is None:
            category_tree.append(node)
        else:
            parent_node = category_nodes.get(category.parent_id)
            if parent_node:
                parent_node["children"].append(node)

    return {
        "categories": list(category_nodes.values()),
        "category_tree": category_tree,
        "total_categories": total_categories,
        "active_categories": active_categories,
        "inactive_categories": inactive_categories,
        "percentage_active": round(percentage_active, 1),
        "categories_added_this_month": categories_added_this_month,
        "total_parent_categories": total_parent_categories,
        "total_subcategories": total_subcategories,
        "empty_categories": empty_categories,
        "products_assigned": products_assigned,
        "average_products_per_category": round(average_products_per_category, 1),
    }


def get_categories_api_data():
    """Return JSON-safe category data for the category management frontend."""
    context = get_categories_data()
    return {
        "categories": context["category_tree"],
        "category_tree": context["category_tree"],
        "total_categories": context["total_categories"],
        "active_categories": context["active_categories"],
        "inactive_categories": context["inactive_categories"],
        "percentage_active": context["percentage_active"],
        "categories_added_this_month": context["categories_added_this_month"],
        "total_parent_categories": context["total_parent_categories"],
        "total_subcategories": context["total_subcategories"],
        "empty_categories": context["empty_categories"],
        "products_assigned": context["products_assigned"],
        "average_products_per_category": context["average_products_per_category"],
    }


def get_brands_data():
    now = timezone.now()

    brands = (
        Brand.objects.annotate(
            products_count=Count("products", distinct=True),
            categories_count=Count("products__category", distinct=True),
            orders_count=Count(
                "products__order_items__order",
                distinct=True,
            ),
        )
        .order_by("name")
    )

    total_brands = brands.count()

    brands_added_this_month = brands.filter(
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()

    active_brands = brands.filter(is_active=True).count()
    percentage_active = (active_brands / total_brands) * 100 if total_brands else 0

    inactive_brands = brands.filter(is_active=False).count()
    inactive_brands_added_this_month = brands.filter(
        is_active=False,
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()

    featured_brands = brands.filter(is_featured=True).count()
    empty_brands = brands.filter(products_count=0).count()

    products_assigned_qs = Product.objects.filter(brand__isnull=False)
    products_assigned_this_month = products_assigned_qs.filter(
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()
    products_assigned = products_assigned_qs.count()

    return {
        "brands": brands,
        "total_brands": total_brands,
        "brands_added_this_month": brands_added_this_month,
        "active_brands": active_brands,
        "percentage_active": percentage_active,
        "inactive_brands": inactive_brands,
        "inactive_brands_added_this_month": inactive_brands_added_this_month,
        "featured_brands": featured_brands,
        "empty_brands": empty_brands,
        "products_assigned": products_assigned,
        "products_assigned_this_month": products_assigned_this_month,
    }


BRAND_WRITE_FIELDS = (
    "name", "slug", "description", "country_of_origin", "founded_year",
    "website", "official_email", "official_phone", "facebook", "instagram",
    "linkedin", "is_active", "is_featured", "display_order",
)


def brand_payload(brand):
    return {
        "id": brand.id, "name": brand.name, "slug": brand.slug,
        "description": brand.description, "country_of_origin": brand.country_of_origin,
        "founded_year": brand.founded_year, "website": brand.website,
        "official_email": brand.official_email, "official_phone": brand.official_phone,
        "facebook": brand.facebook, "instagram": brand.instagram, "linkedin": brand.linkedin,
        "is_active": brand.is_active, "is_featured": brand.is_featured,
        "display_order": brand.display_order,
        "logo_url": brand.logo if brand.logo else "",
        "cover_image_url": brand.cover_image if brand.cover_image else "",
        "products_count": brand.products.count(),
        "categories_count": brand.products.values("category_id").distinct().count(),
        "created_at": brand.created_at.isoformat(), "updated_at": brand.updated_at.isoformat(),
    }


def get_brands_api_data():
    return {"brands": [brand_payload(b) for b in Brand.objects.all()]}


def brand_detail_payload(brand):
    products = brand.products.select_related("category", "seller").annotate(
        order_count=Count("order_items__order", distinct=True),
        units_sold=Sum("order_items__quantity"),
        revenue_total=Sum("order_items__total"),
    ).order_by("-created_at")

    product_rows = []
    for product in products[:20]:
        product_rows.append({
            "id": product.id, "name": product.name, "sku": product.sku or "—",
            "seller": product.seller.store_name if product.seller else "—",
            "category": product.category.name if product.category else "Uncategorized",
            "price": float(product.discount_price or product.price or 0),
            "stock": product.stock_quantity, "orders": product.order_count, "units_sold": product.units_sold or 0,
            "revenue": float(product.revenue_total or 0), "status": product.status,
            "slug": product.slug if product.slug else "undefined",
        "image_url": product.primary_image.image if product.primary_image else "",
        })

    category_rows = list(brand.products.values("category__id", "category__name").annotate(
        product_count=Count("id", distinct=True), units_sold=Sum("order_items__quantity"), revenue=Sum("order_items__total")
    ).order_by("-product_count", "category__name"))

    categories = [
        {
            "id": row["category__id"], "name": row["category__name"] or "Uncategorized", 
            "products": row["product_count"], "units_sold": row["units_sold"] or 0, 
            "revenue": float(row["revenue"] or 0)
        } for row in category_rows
    ]

    revenue = brand.products.aggregate(total=Sum("order_items__total"))["total"] or 0
    orders = brand.products.aggregate(total=Count("order_items__order", distinct=True))["total"] or 0
    
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_end = month_start
    previous_month_start = (month_start - timedelta(days=1)).replace(day=1)
    
    def month_metrics(start, end):
        scoped = brand.products.filter(order_items__order__created_at__gte=start, order_items__order__created_at__lt=end)
        return {
            "products": brand.products.filter(created_at__gte=start, created_at__lt=end).count(),
            "orders": scoped.aggregate(value=Count("order_items__order", distinct=True))["value"] or 0,
            "units": scoped.aggregate(value=Sum("order_items__quantity"))["value"] or 0,
            "revenue": float(scoped.aggregate(value=Sum("order_items__total"))["value"] or 0),
        }

    current_month = month_metrics(month_start, now)
    previous_month = month_metrics(previous_month_start, previous_month_end)

    def change(current, previous):
        if not previous:
            return 100 if current else 0
        return round(((current - previous) / previous) * 100, 1)

    weekly = []
    for index in range(7, -1, -1):
        start = now - timedelta(days=(index + 1) * 7)
        end = now - timedelta(days=index * 7)
        aggregate = brand.products.filter(
            order_items__order__created_at__gte=start, order_items__order__created_at__lt=end
        ).aggregate(total=Sum("order_items__total"))["total"] or 0
        weekly.append({
            "label": start.strftime("%b %-d") if not __import__("sys").platform.startswith("win") else start.strftime("%b %#d"), 
            "revenue": float(aggregate)
        })

    monthly = []
    cursor = (month_start - timedelta(days=330)).replace(day=1)
    for _ in range(12):
        next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        scoped = brand.products.filter(order_items__order__created_at__gte=cursor, order_items__order__created_at__lt=next_month)
        monthly.append({
            "label": cursor.strftime("%b"),
            "orders": scoped.aggregate(value=Count("order_items__order", distinct=True))["value"] or 0,
            "units": scoped.aggregate(value=Sum("order_items__quantity"))["value"] or 0,
        })

    payload = brand_payload(brand)
    payload.update({
        "products": product_rows, "categories": categories, "revenue": float(revenue), "orders": orders,
        "weekly_revenue": weekly, "latest_product": product_rows[0] if product_rows else None,
        "top_category": categories[0] if categories else None,
        "analytics": {
            "top_products": sorted(product_rows, key=lambda item: item["units_sold"], reverse=True)[:3], 
            "top_categories": sorted(categories, key=lambda item: item["units_sold"], reverse=True)[:3], 
            "monthly": monthly
        },
        "overview": {
            "products_this_month": current_month["products"], "products_change": change(current_month["products"], previous_month["products"]),
            "orders_this_month": current_month["orders"], "orders_change": change(current_month["orders"], previous_month["orders"]),
            "revenue_this_month": current_month["revenue"], "revenue_change": change(current_month["revenue"], previous_month["revenue"]),
            "units_sold": current_month["units"], "categories": len(categories),
            "rating": None, "reviews": None, "return_rate": None, "views": None, "conversion_rate": None,
        },
        "activity": [
            {"type": "brand", "title": "Brand created", "description": f"{brand.name} was added to the marketplace catalog.", "time": brand.created_at.isoformat()}, 
            {"type": "brand", "title": "Brand updated", "description": "Brand information was updated.", "time": brand.updated_at.isoformat()}
        ],
    })
    return payload


def save_brand(data, files=None, brand=None):
    files = files or {}
    with transaction.atomic():
        brand = brand or Brand()
        for field in BRAND_WRITE_FIELDS:
            if field not in data:
                continue
            value = data.get(field)
            if field in ("is_active", "is_featured"):
                value = str(value).lower() in ("1", "true", "yes", "on")
            elif field in ("founded_year", "display_order"):
                value = int(value) if str(value or "").strip() else None if field == "founded_year" else 0
            elif field == "slug":
                value = str(value or "").strip() or slugify(data.get("name", brand.name))
            else:
                value = str(value or "").strip()
            setattr(brand, field, value)
            
        if not brand.name:
            raise ValidationError("Brand name is required.")
        if not brand.slug:
            brand.slug = slugify(brand.name)
        uploaded_logo = files.get("logo")
        uploaded_cover = files.get("cover_image")
        if str(data.get("remove_logo", "")).lower() == "true" and brand.logo:
            brand.logo = None
        if str(data.get("remove_cover_image", "")).lower() == "true" and brand.cover_image:
            brand.cover_image = None
            
        brand.is_active = True
        brand.full_clean()
        brand.save()

        if uploaded_logo:
            result = store_catalog_image(uploaded_logo, "brands", str(brand.id), "logo")
            brand.logo = result.get("secure_url") or result.get("url")
        if uploaded_cover:
            result = store_catalog_image(uploaded_cover, "brands", str(brand.id), "cover_image")
            brand.cover_image = result.get("secure_url") or result.get("url")
        if uploaded_logo or uploaded_cover:
            brand.save(update_fields=[field for field, uploaded in (("logo", uploaded_logo), ("cover_image", uploaded_cover)) if uploaded])
    return brand


def delete_brand(brand, remove_products=False):
    if remove_products:
        brand.products.update(brand=None)
    elif brand.products.exists():
        raise ValidationError("Brands with products cannot be deleted. Remove the brand from products first.")
    brand.delete()


def import_brands(upload):
    raw = upload.read()
    if upload.name.lower().endswith(".json"):
        records = json.loads(raw.decode("utf-8"))
    else:
        records = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        
    if isinstance(records, dict):
        records = records.get("brands", [])
        
    created = 0
    with transaction.atomic():
        for record in records:
            if not record.get("name"):
                raise ValidationError("Every imported brand must have a name.")
            save_brand(record)
            created += 1
    return created


def export_categories(export_format="CSV", category_ids=None):
    export_format = str(export_format or "CSV").upper()

    categories = (
        Category.objects
        .select_related("parent")
        .annotate(
            product_count=Count(
                "products",
                distinct=True,
            ),
            subcategory_count=Count(
                "children",
                distinct=True,
            ),
        )
        .order_by("name")
    )

    if category_ids:
        categories = categories.filter(id__in=category_ids)

    if export_format == "CSV":
        return _export_categories_csv(categories)

    if export_format == "JSON":
        return _export_categories_json(categories)

    if export_format == "PDF":
        return _export_categories_pdf(categories)

    raise ValueError("Unsupported export format.")


def _export_categories_csv(categories):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Name", "Slug", "Parent", "Type", "Status",
        "Products", "Subcategories", "Description", "Icon", "Image",
    ])

    for category in categories:
        writer.writerow([
            category.id,
            category.name,
            category.slug,
            category.parent.name if category.parent else "",
            "Subcategory" if category.parent_id else "Category",
            "Active" if category.is_active else "Inactive",
            category.product_count,
            category.subcategory_count,
            category.description or "",
            category.icon or "",
            category.image if category.image else "",
        ])

    response = HttpResponse(
        output.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="categories.csv"'
    return response


def _export_categories_json(categories):
    data = []
    for category in categories:
        data.append({
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "parent_id": category.parent_id,
            "parent": (
                {
                    "id": category.parent.id,
                    "name": category.parent.name,
                    "slug": category.parent.slug,
                }
                if category.parent
                else None
            ),
            "type": "Subcategory" if category.parent_id else "Category",
            "status": "active" if category.is_active else "inactive",
            "is_active": category.is_active,
            "product_count": category.product_count,
            "subcategory_count": category.subcategory_count,
            "description": category.description or "",
            "icon": category.icon or "",
            "image": category.image if category.image else "",
            "created_at": category.created_at.isoformat() if getattr(category, "created_at", None) else None,
            "updated_at": category.updated_at.isoformat() if getattr(category, "updated_at", None) else None,
        })

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="categories.json"'
    return response


# =============================================================
# BRAND & STYLE CONSTANTS (PDF)
# =============================================================
ACCENT_COLOR = colors.HexColor("#9D6638")
HEADING_COLOR = colors.HexColor("#4E220F")
MUTED_COLOR = colors.HexColor("#6B6B6B")
BORDER_COLOR = colors.HexColor("#D9D2C4")
LIGHT_BG = colors.HexColor("#F7F1DE")

PAGE_MARGIN = 20 * mm


def _get_styles():
    """Defines the typography system for the report."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportBrand", fontName="Helvetica-Bold", fontSize=20, textColor=HEADING_COLOR, spaceAfter=4))
    styles.add(ParagraphStyle(name="ReportTitle", fontName="Helvetica", fontSize=12, spaceBefore=4, textColor=MUTED_COLOR))
    styles.add(ParagraphStyle(name="MetaRight", fontName="Helvetica", fontSize=9, textColor=MUTED_COLOR, alignment=TA_RIGHT, leading=12))
    styles.add(ParagraphStyle(name="TableHeader", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="TableCell", fontName="Helvetica", fontSize=9, textColor=colors.black, leading=12, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="TableCellLeft", parent=styles["TableCell"], alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="TableCellRight", parent=styles["TableCell"], alignment=TA_RIGHT))
    return styles


def _draw_footer(canvas, doc):
    """Canvas hook for drawing the universal footer on every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED_COLOR)
    
    timestamp = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
    landscape_width = landscape(A4)[0]
    
    canvas.drawString(PAGE_MARGIN, 10 * mm, f"MarketSphere Admin Dashboard | {timestamp}")
    canvas.drawCentredString(landscape_width / 2.0, 10 * mm, "Confidential Document")
    canvas.drawRightString(landscape_width - PAGE_MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _build_data_table(headers, row_data, col_widths, styles, align_left_cols=None, align_right_cols=None):
    """Builds standard list tables with alternating row colors."""
    align_left_cols = align_left_cols or []
    align_right_cols = align_right_cols or []
    table_data = []

    header_row = [Paragraph(h, styles["TableHeader"]) for h in headers]
    table_data.append(header_row)

    if not row_data:
        table_data.append([Paragraph("<i>No data available</i>", styles["TableCellLeft"])] + [""] * (len(headers) - 1))
    else:
        for row in row_data:
            formatted_row = []
            for idx, cell_value in enumerate(row):
                style = styles["TableCellLeft"] if idx in align_left_cols else (styles["TableCellRight"] if idx in align_right_cols else styles["TableCell"])
                formatted_row.append(Paragraph(str(cell_value), style))
            table_data.append(formatted_row)

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADING_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, BORDER_COLOR),
    ]
    
    if row_data:
        t_style.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_BG]))
        
    t.setStyle(TableStyle(t_style))
    return t


def _export_categories_pdf(categories):
    buffer = io.BytesIO()
    styles = _get_styles()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN,
        title="MarketSphere - Category Export"
    )

    elements = []

    brand_block = [
        Paragraph("MARKETSPHERE", styles["ReportBrand"]),
        Paragraph("Category Export Report", styles["ReportTitle"]),
    ]
    meta_block = [
        Paragraph(f"<b>Generated Date:</b> {timezone.now().strftime('%b %d, %Y')}", styles["MetaRight"]),
        Paragraph(f"<b>Time:</b> {timezone.now().strftime('%H:%M:%S')}", styles["MetaRight"]),
        Paragraph(f"<b>Total Categories:</b> {len(categories)}", styles["MetaRight"]),
    ]
    
    header_table = Table([[brand_block, meta_block]], colWidths=[130*mm, 127*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), 
        ('ALIGN', (1, 0), (1, 0), 'RIGHT')
    ]))
    
    elements.extend([
        header_table, 
        Spacer(1, 10), 
        HRFlowable(width="100%", thickness=1.5, color=ACCENT_COLOR, spaceAfter=15)
    ])

    headers = [
        "ID", "Category", "Slug", "Parent", 
        "Type", "Status", "Products", "Subcategories"
    ]

    row_data = []
    for category in categories:
        row_data.append([
            str(category.id),
            category.name,
            category.slug,
            category.parent.name if category.parent else "Top Level",
            "Subcategory" if category.parent_id else "Category",
            "Active" if category.is_active else "Inactive",
            str(category.product_count),
            str(category.subcategory_count),
        ])

    col_widths = [15*mm, 45*mm, 45*mm, 45*mm, 25*mm, 22*mm, 25*mm, 35*mm]

    table = _build_data_table(
        headers=headers,
        row_data=row_data,
        col_widths=col_widths,
        styles=styles,
        align_left_cols=[1, 2, 3],
        align_right_cols=[6, 7]
    )

    elements.append(table)
    document.build(elements, onFirstPage=_draw_footer, onLaterPages=_draw_footer)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="categories.pdf"'

    return response


from decimal import Decimal
from django.core.cache import cache

from .models import (
    StoreSettings,
    MarketplaceSettings,
    CheckoutSettings,
    CatalogSettings,
    NotificationSettings,
    AdminAuditLog,
)
from .marketplace import invalidate_marketplace_settings_cache
from .checkout import invalidate_checkout_settings_cache
from .catalog import invalidate_catalog_settings_cache
from .notification_settings import invalidate_notification_settings_cache
from .settings_data import invalidate_admin_settings_data_cache
from .store import invalidate_store_settings_cache

MARKETPLACE_ONLINE_CACHE_KEY = "marketplace_settings:marketplace_online"


PLATFORM_SETTINGS_CACHE_KEY = "platform_settings"
PLATFORM_SETTINGS_CACHE_TIMEOUT = 3600


def get_platform_settings():
    cached = cache.get(PLATFORM_SETTINGS_CACHE_KEY)

    if cached is not None:
        return cached

    settings_data = {
        "store": StoreSettings.load(),
        "marketplace": MarketplaceSettings.load(),
        "checkout": CheckoutSettings.load(),
        "catalog": CatalogSettings.load(),
        "notifications": NotificationSettings.load(),
    }

    cache.set(
        PLATFORM_SETTINGS_CACHE_KEY,
        settings_data,
        timeout=PLATFORM_SETTINGS_CACHE_TIMEOUT,
    )

    return settings_data


def invalidate_platform_settings_cache():
    cache.delete(PLATFORM_SETTINGS_CACHE_KEY)
    invalidate_marketplace_settings_cache()
    invalidate_checkout_settings_cache()
    invalidate_catalog_settings_cache()
    invalidate_notification_settings_cache()
    invalidate_admin_settings_data_cache()
    invalidate_store_settings_cache()


def serialize_setting_value(value):
    if value is None:
        return ""

    if isinstance(value, Decimal):
        return str(value)

    if hasattr(value, "url"):
        try:
            return value.url
        except ValueError:
            return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    return str(value)


SENSITIVE_SETTING_NAMES = {
    "password",
    "smtp_password",
    "api_key",
    "secret_key",
    "client_secret",
    "access_token",
    "refresh_token",
    "private_key",
    "encryption_key",
    "webhook_secret",
}


def is_sensitive_setting(setting_name):
    name = setting_name.lower()

    return (
        name in SENSITIVE_SETTING_NAMES
        or any(
            sensitive in name
            for sensitive in (
                "password",
                "secret",
                "token",
                "private_key",
                "api_key",
            )
        )
    )


def log_audit_event(
    admin,
    action,
    section,
    setting_name,
    old_value,
    new_value,
    ip_address=None,
):
    if is_sensitive_setting(setting_name):
        old_value = "********"
        new_value = "********"
    else:
        old_value = serialize_setting_value(old_value)
        new_value = serialize_setting_value(new_value)

    AdminAuditLog.objects.create(
        admin=admin,
        action=action,
        section=section,
        setting_name=setting_name,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )


# admin_panel/services/settings.py

from admin_panel.models import (
    StoreSettings,
    MarketplaceSettings,
    CheckoutSettings,
    CatalogSettings,
)


def get_store_settings():
    from .store import get_store_settings as get_cached_store_settings

    return get_cached_store_settings()


def get_marketplace_settings():
    from .marketplace import get_marketplace_settings as get_cached_marketplace_settings

    return get_cached_marketplace_settings()


def get_checkout_settings():
    from .checkout import get_checkout_settings as get_cached_checkout_settings

    return get_cached_checkout_settings()


def get_catalog_settings():
    from .catalog import get_catalog_settings as get_cached_catalog_settings

    return get_cached_catalog_settings()
