from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import Seller
from orders.models import Order, OrderItem
from products.models import Brand, Product

from .settings_service import get_catalog_settings


def get_products_catalog() -> dict[str, Any]:
    """Retrieve top-level aggregates and lists for the product catalog dashboard."""
    total_products = Product.objects.all().count()
    published_products = Product.objects.filter(status=Product.Status.PUBLISHED).count()
    published_percentage_catalog = round((published_products / total_products) * 100, 1) if total_products else 0

    hidden_products = Product.objects.filter(status=Product.Status.HIDDEN).count()
    out_of_stock_products = Product.objects.filter(Q(status=Product.Status.OUT_OF_STOCK) | Q(stock_quantity=0)).count()
    featured_products = Product.objects.filter(is_featured=True).count()
    archived_products = Product.objects.filter(status=Product.Status.ARCHIVED).count()
    drafted_products = Product.objects.filter(status=Product.Status.DRAFT).count()

    products = Product.objects.all().annotate(
        total_orders=Coalesce(
            Sum("order_items__quantity", filter=Q(order_items__order__status=Order.Status.DELIVERED)), 0
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


def get_product_performance(product: Product) -> dict[str, Any]:
    """Calculate month-over-month sales performance and stock health for a product."""
    now = timezone.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if current_month_start.month == 1:
        previous_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
    else:
        previous_month_start = current_month_start.replace(month=current_month_start.month - 1)

    delivered = Order.Status.DELIVERED
    
    all_time = product.order_items.filter(order__status=delivered).aggregate(
        sales=Sum("total"), orders=Count("order", distinct=True), units=Sum("quantity")
    )
    total_sales = all_time["sales"] or Decimal("0.00")
    total_orders = all_time["orders"] or 0
    units_sold = all_time["units"] or 0

    current_month = product.order_items.filter(
        order__status=delivered, order__delivered_at__gte=current_month_start, order__delivered_at__lt=now
    ).aggregate(sales=Sum("total"), orders=Count("order", distinct=True), units=Sum("quantity"))
    current_sales = current_month["sales"] or Decimal("0.00")
    current_orders = current_month["orders"] or 0
    current_units = current_month["units"] or 0

    previous_month = product.order_items.filter(
        order__status=delivered, order__delivered_at__gte=previous_month_start, order__delivered_at__lt=current_month_start
    ).aggregate(sales=Sum("total"), orders=Count("order", distinct=True), units=Sum("quantity"))
    previous_sales = previous_month["sales"] or Decimal("0.00")
    previous_orders = previous_month["orders"] or 0
    previous_units = previous_month["units"] or 0

    def calculate_change(current: int | Decimal, previous: int | Decimal) -> float | int | None:
        if previous == 0:
            return 0 if current == 0 else None
        return round(((float(current) - float(previous)) / float(previous)) * 100, 1)

    reserved_units = product.order_items.filter(
        order__status__in=[Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.PROCESSING, Order.Status.SHIPPED]
    ).aggregate(total=Sum("quantity"))["total"] or 0

    low_stock_threshold = get_catalog_settings().low_stock_threshold
    current_stock = product.stock_quantity
    
    if current_stock <= 0: stock_health = "out_of_stock"
    elif current_stock <= low_stock_threshold: stock_health = "low"
    else: stock_health = "healthy"

    return {
        "total_sales": total_sales,
        "sales_change": calculate_change(current_sales, previous_sales),
        "sales_increased": current_sales > previous_sales,
        "total_orders": total_orders,
        "orders_change": calculate_change(current_orders, previous_orders),
        "orders_increased": current_orders > previous_orders,
        "units_sold": units_sold,
        "units_change": calculate_change(current_units, previous_units),
        "units_increased": current_units > previous_units,
        "revenue": total_sales,
        "return_rate": None,
        "current_stock": current_stock,
        "low_stock_threshold": low_stock_threshold,
        "wishlist_adds": product.wishlisted_by.count(),
        "product_views": None,
        "reserved_units": reserved_units,
        "available_stock": current_stock - reserved_units,
        "stock_health": stock_health,
    }


def get_product_orders(product: Product) -> dict[str, Any]:
    """Breakdown order statuses intersecting this product."""
    statuses = Order.Status
    product_order_items = product.order_items.select_related("order", "order__seller", "order__user")

    def count_status(status_enum: str | None = None, is_refund: bool = False) -> int:
        qs = product_order_items
        if is_refund:
            return qs.filter(order__payment_status=Order.PaymentStatus.REFUNDED).values("order_id").distinct().count()
        if status_enum:
            return qs.filter(order__status=status_enum).values("order_id").distinct().count()
        return qs.values("order_id").distinct().count()

    return {
        "total_orders": count_status(),
        "pending_orders": count_status(statuses.PENDING),
        "confirmed_orders": count_status(statuses.CONFIRMED),
        "processing_orders": count_status(statuses.PROCESSING),
        "shipped_orders": count_status(statuses.SHIPPED),
        "delivered_orders": count_status(statuses.DELIVERED),
        "cancelled_orders": count_status(statuses.CANCELLED),
        "return_orders": None,
        "refunded_orders": count_status(is_refund=True),
        "orders": Order.objects.filter(items__product=product).select_related("user", "seller").prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.filter(product=product), to_attr="product_items")
        ).order_by("-created_at").distinct(),
    }


def get_product_revenue_trend(product: Product) -> list[dict[str, Any]]:
    """Determine the trailing 8-week revenue trend for a product."""
    now = timezone.localtime(timezone.now())
    current_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_starts = [current_week_start - timedelta(weeks=i) for i in range(7, -1, -1)]

    weekly_sales = product.order_items.filter(
        order__status=Order.Status.DELIVERED,
        order__delivered_at__gte=week_starts[0],
        order__delivered_at__lt=current_week_start + timedelta(weeks=1),
    ).values("order__delivered_at").annotate(revenue=Sum("total"))

    revenue_by_week = {week_start: Decimal("0.00") for week_start in week_starts}

    for row in weekly_sales:
        delivered_at = timezone.localtime(row["order__delivered_at"])
        week_start = (delivered_at - timedelta(days=delivered_at.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        if week_start in revenue_by_week:
            revenue_by_week[week_start] += row["revenue"] or Decimal("0.00")

    return [
        {
            "date": week,
            "label": week.strftime("%b %d").replace(" 0", " "),
            "revenue": revenue_by_week[week],
            "revenue_display": f"Rs. {revenue_by_week[week]:,.0f}",
        }
        for week in week_starts
    ]


def get_product_order_status_mix(product: Product) -> dict[str, Any]:
    """Calculate the percentage mix of order statuses for a product."""
    status_counts = product.order_items.values("order__status").annotate(total=Count("order", distinct=True))
    counts = {row["order__status"]: row["total"] for row in status_counts}
    total_orders = sum(counts.values())

    def percent(count: int) -> float:
        return round((count / total_orders) * 100, 1) if total_orders else 0.0

    return {
        "total": total_orders,
        "delivered": counts.get(Order.Status.DELIVERED, 0),
        "delivered_percentage": percent(counts.get(Order.Status.DELIVERED, 0)),
        "pending": counts.get(Order.Status.PENDING, 0),
        "pending_percentage": percent(counts.get(Order.Status.PENDING, 0)),
        "confirmed": counts.get(Order.Status.CONFIRMED, 0),
        "confirmed_percentage": percent(counts.get(Order.Status.CONFIRMED, 0)),
        "processing": counts.get(Order.Status.PROCESSING, 0),
        "processing_percentage": percent(counts.get(Order.Status.PROCESSING, 0)),
        "shipped": counts.get(Order.Status.SHIPPED, 0),
        "shipped_percentage": percent(counts.get(Order.Status.SHIPPED, 0)),
        "cancelled": counts.get(Order.Status.CANCELLED, 0),
        "cancelled_percentage": percent(counts.get(Order.Status.CANCELLED, 0)),
    }


def get_product_customer_locations(product: Product) -> list[dict[str, Any]]:
    """Determine top geographic shipment destinations for a product."""
    product_orders = product.order_items.values("order_id").distinct()
    total_orders = product_orders.count()

    if total_orders == 0:
        return []

    city_counts = list(
        Order.objects.filter(id__in=product_orders)
        .exclude(shipping_city__isnull=True)
        .exclude(shipping_city__exact="")
        .values("shipping_city")
        .annotate(orders=Count("id", distinct=True))
        .order_by("-orders", "shipping_city")
    )

    top_cities = city_counts[:4]
    top_count = sum(city["orders"] for city in top_cities)
    locations = [
        {"name": city["shipping_city"], "orders": city["orders"], "percentage": round((city["orders"] / total_orders) * 100, 1)}
        for city in top_cities
    ]

    if total_orders - top_count > 0:
        locations.append({
            "name": "Other", 
            "orders": total_orders - top_count, 
            "percentage": round(((total_orders - top_count) / total_orders) * 100, 1)
        })

    return locations


def get_product_kpis(product: Product) -> dict[str, Any]:
    """Return key performance indicators such as AOV and wishlist additions."""
    now = timezone.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_start = (
        current_month_start.replace(year=current_month_start.year - 1, month=12) if current_month_start.month == 1
        else current_month_start.replace(month=current_month_start.month - 1)
    )

    total_wishlist = product.wishlisted_by.count()
    current_wishlist = product.wishlisted_by.filter(created_at__gte=current_month_start).count()
    previous_wishlist = product.wishlisted_by.filter(created_at__gte=previous_month_start, created_at__lt=current_month_start).count()

    def calc_change(curr: int | Decimal, prev: int | Decimal) -> float | int | None:
        if prev == 0: return 0 if curr == 0 else None
        return round(((float(curr) - float(prev)) / float(prev)) * 100, 1)

    order_data = product.order_items.filter(order__status=Order.Status.DELIVERED).aggregate(revenue=Sum("total"), orders=Count("order", distinct=True))
    total_orders = order_data["orders"] or 0
    average_order_value = (order_data["revenue"] or Decimal("0.00")) / total_orders if total_orders else Decimal("0.00")

    curr_data = product.order_items.filter(order__status=Order.Status.DELIVERED, order__delivered_at__gte=current_month_start).aggregate(revenue=Sum("total"), orders=Count("order", distinct=True))
    curr_orders = curr_data["orders"] or 0
    curr_aov = (curr_data["revenue"] or Decimal("0.00")) / curr_orders if curr_orders else Decimal("0.00")

    prev_data = product.order_items.filter(order__status=Order.Status.DELIVERED, order__delivered_at__gte=previous_month_start, order__delivered_at__lt=current_month_start).aggregate(revenue=Sum("total"), orders=Count("order", distinct=True))
    prev_orders = prev_data["orders"] or 0
    prev_aov = (prev_data["revenue"] or Decimal("0.00")) / prev_orders if prev_orders else Decimal("0.00")

    return {
        "wishlist_adds": total_wishlist,
        "wishlist_change": calc_change(current_wishlist, previous_wishlist),
        "wishlist_increased": current_wishlist > previous_wishlist,
        "conversion_rate": None,
        "conversion_change": None,
        "conversion_increased": None,
        "average_order_value": average_order_value,
        "aov_change": calc_change(curr_aov, prev_aov),
        "aov_increased": curr_aov > prev_aov,
        "return_rate": None,
        "return_change": None,
        "return_increased": None,
    }


def get_product_moderation(product: Product) -> dict[str, Any]:
    """Determine moderation flags and visual checklist validation for a product."""
    seller = product.seller

    publication_labels = {
        Product.Status.DRAFT: "Draft", Product.Status.PUBLISHED: "Published",
        Product.Status.HIDDEN: "Hidden", Product.Status.OUT_OF_STOCK: "Out of Stock",
        Product.Status.ARCHIVED: "Archived", Product.Status.PENDING: "Pending",
        Product.Status.REJECTED: "Rejected",
    }
    
    is_visible = product.status == Product.Status.PUBLISHED and product.is_approved
    seller_verified = bool(seller and seller.status == seller.Status.VERIFIED)
    price_valid = product.price is not None and product.price > 0 and (
        product.discount_price is None or (0 < product.discount_price < product.price)
    )

    info_complete = bool(product.name and product.description)
    desc_review = len((product.description or "").strip()) < 100

    content_quality = {"label": "Good", "class": "c-success"} if info_complete and not desc_review \
        else {"label": "Needs Review", "class": "c-warning"} if info_complete \
        else {"label": "Incomplete", "class": "c-danger"}

    checklist = [
        {"title": "Product Information Complete", "description": "Name and description provided", "complete": info_complete, "warning": False},
        {"title": "Images Available", "description": f"{product.images.count()} image(s) uploaded", "complete": product.images.count() > 0, "warning": False},
        {"title": "Category Assigned", "description": product.category.name if product.category else "No category", "complete": bool(product.category), "warning": False},
        {"title": "Brand Assigned", "description": product.brand.name if product.brand else "No brand", "complete": bool(product.brand), "warning": False},
        {"title": "Price Valid", "description": "Prices set correctly" if price_valid else "Price requires review", "complete": price_valid, "warning": not price_valid},
        {"title": "Stock Available", "description": f"{product.stock_quantity} units", "complete": product.stock_quantity > 0, "warning": product.stock_quantity <= 0},
        {"title": "Seller Verified", "description": "Verified seller" if seller_verified else "No seller assigned/verified", "complete": seller_verified, "warning": not seller_verified},
        {"title": "Required Information Provided", "description": "SKU/Barcode present" if (product.sku and product.barcode) else "Missing SKU/Barcode", "complete": bool(product.sku and product.barcode), "warning": not bool(product.sku and product.barcode)},
        {"title": "Description Review", "description": "Needs detail for SEO" if desc_review else "Length looks good", "complete": not desc_review, "warning": desc_review},
    ]

    return {
        "approval_status": {"label": "Approved" if product.is_approved else "Not Approved", "class": "c-success" if product.is_approved else "c-warning"},
        "publication_status": {"label": publication_labels.get(product.status, product.status.title()), "class": "c-success" if product.status == Product.Status.PUBLISHED else "c-warning"},
        "visibility": {"label": "Visible" if is_visible else "Hidden", "class": "c-success" if is_visible else "c-muted"},
        "featured_status": {"label": "Featured" if product.is_featured else "Not Featured", "class": "c-accent" if product.is_featured else "c-muted"},
        "policy_compliance": None,
        "content_quality": content_quality,
        "seller_verification": {"label": "Verified" if seller_verified else "Not Verified", "class": "c-success" if seller_verified else "c-warning"},
        "moderation_score": None,
        "checklist": checklist,
    }


def get_product_risk_review(product: Product) -> dict[str, Any]:
    """Evaluate product risks (duplicates, copyright, suspicious pricing)."""
    risks = []
    duplicate_qs = Product.objects.exclude(pk=product.pk)
    
    dup_sku_bar = (product.sku and duplicate_qs.filter(sku=product.sku).exists()) or (product.barcode and duplicate_qs.filter(barcode=product.barcode).exists())
    if dup_sku_bar: risks.append({"title": "Duplicate Product", "description": "Matching SKU or barcode found", "level": "High", "class": "is-high"})
    elif duplicate_qs.filter(name__iexact=product.name).exists(): risks.append({"title": "Duplicate Product", "description": "Matching name found", "level": "Medium", "class": "is-medium"})
    else: risks.append({"title": "Duplicate Product", "description": "No matches found", "level": "Low", "class": ""})

    risks.append({"title": "Counterfeit Risk", "description": "Brand assigned" if product.brand else "No brand", "level": "Not Available", "class": ""})
    risks.append({"title": "Copyright Risk", "description": "Cannot verify copyright", "level": "Not Available", "class": ""})
    risks.append({"title": "Restricted Category", "description": f"Category: {product.category.name}" if product.category else "No category", "level": "Not Available" if product.category else "Medium", "class": "" if product.category else "is-medium"})

    if product.price and product.discount_price:
        perc = ((product.price - product.discount_price) / product.price) * 100
        risks.append({"title": "Suspicious Pricing", "description": f"{round(perc)}% discount", "level": "Medium" if perc >= 50 else "Low", "class": "is-medium" if perc >= 50 else ""})
    elif product.price:
        risks.append({"title": "Suspicious Pricing", "description": "No discount", "level": "Low", "class": ""})
    else:
        risks.append({"title": "Suspicious Pricing", "description": "Price missing", "level": "Medium", "class": "is-medium"})

    risks.append({"title": "Policy Violation", "description": "No data available", "level": "Not Available", "class": ""})

    missing = [f for f, v in (("name", product.name), ("description", product.description), ("SKU", product.sku), ("barcode", product.barcode), ("category", product.category)) if not v]
    risks.append({"title": "Invalid Product Information", "description": "Missing: " + ", ".join(missing) if missing else "All fields populated", "level": "Medium" if missing else "Low", "class": "is-medium" if missing else ""})
    
    if not product.seller: risks.append({"title": "Seller Risk", "description": "No seller", "level": "High", "class": "is-high"})
    elif product.seller.status == Seller.Status.VERIFIED: risks.append({"title": "Seller Risk", "description": "Verified seller", "level": "Low", "class": ""})
    elif product.seller.status in (Seller.Status.SUSPENDED, Seller.Status.BLOCKED, Seller.Status.REJECTED): risks.append({"title": "Seller Risk", "description": "Seller is suspended/blocked", "level": "High", "class": "is-high"})
    else: risks.append({"title": "Seller Risk", "description": "Seller pending", "level": "Medium", "class": "is-medium"})
    
    risks.append({"title": "Image Quality", "description": f"{product.images.count()} images" if product.images.count() else "No images", "level": "Not Available" if product.images.count() else "Medium", "class": "" if product.images.count() else "is-medium"})
    risks.append({"title": "Trademark Risk", "description": "Brand assigned" if product.brand else "No brand", "level": "Not Available", "class": ""})

    return {
        "risks": risks,
        "high_count": sum(1 for r in risks if r["level"] == "High"),
        "medium_count": sum(1 for r in risks if r["level"] == "Medium"),
        "low_count": sum(1 for r in risks if r["level"] == "Low"),
        "unavailable_count": sum(1 for r in risks if r["level"] == "Not Available"),
    }


def get_product_seller_summary(product: Product) -> dict[str, Any]:
    """Retrieve aggregate information about a product's governing seller."""
    seller = product.seller
    if not seller:
        return {
            "verification_status": {"label": "Not Available", "class": "c-muted"},
            "seller_status": {"label": "Not Available", "class": "c-muted"},
            "store_rating": None, "total_products": 0, "seller_orders": 0, "seller_revenue": Decimal("0.00")
        }

    seller_status_labels = {
        Seller.Status.PENDING: "Pending", Seller.Status.VERIFIED: "Active", Seller.Status.DEACTIVATED: "Inactive",
        Seller.Status.SUSPENDED: "Suspended", Seller.Status.BLOCKED: "Blocked", Seller.Status.REJECTED: "Rejected",
    }
    seller_status_classes = {
        Seller.Status.PENDING: "c-warning", Seller.Status.VERIFIED: "c-success", Seller.Status.DEACTIVATED: "c-muted",
        Seller.Status.SUSPENDED: "c-danger", Seller.Status.BLOCKED: "c-danger", Seller.Status.REJECTED: "c-danger",
    }

    return {
        "verification_status": {"label": "Verified" if seller.status == Seller.Status.VERIFIED else "Not Verified", "class": "c-success" if seller.status == Seller.Status.VERIFIED else "c-warning"},
        "seller_status": {"label": seller_status_labels.get(seller.status, seller.status), "class": seller_status_classes.get(seller.status, "c-muted")},
        "store_rating": None,
        "total_products": seller.products.count(),
        "seller_orders": seller.orders.count(),
        "seller_revenue": seller.orders.filter(status=Order.Status.DELIVERED).aggregate(rev=Sum("total"))["rev"] or Decimal("0.00"),
    }


def get_product_detail(product_slug: str) -> dict[str, Any] | None:
    """Consolidate the complete analytics dashboard payload for a specific product."""
    product = (
        Product.objects.filter(slug=product_slug)
        .select_related("category", "brand", "seller")
        .prefetch_related("images", "reviews__user")
        .first()
    )

    if not product:
        return None

    reviews = product.reviews.all().order_by("-created_at")
    total_reviews = reviews.count()
    avg_data = reviews.aggregate(average=Avg('rating'))
    average_rating = round(avg_data['average'], 1) if avg_data['average'] else 0.0

    average_stars = []
    for i in range(1, 6):
        if average_rating >= i: average_stars.append('bi-star-fill')
        elif average_rating >= i - 0.5: average_stars.append('bi-star-half')
        else: average_stars.append('bi-star')

    counts = reviews.values('rating').annotate(count=Count('id'))
    review_distribution = {i: {'count': 0, 'percent': 0} for i in range(5, 0, -1)}
    
    for c in counts:
        rating = c['rating']
        count = c['count']
        percent = (count / total_reviews * 100) if total_reviews > 0 else 0
        if rating in review_distribution:
            review_distribution[rating] = {'count': count, 'percent': round(percent)}

    return {
        "product": product,
        "performance": get_product_performance(product),
        "brands": Brand.objects.filter(is_active=True).order_by("name"),
        "order_data": get_product_orders(product),
        "revenue_trend": get_product_revenue_trend(product),
        "status_mix": get_product_order_status_mix(product),
        "customer_locations": get_product_customer_locations(product),
        "kpis": get_product_kpis(product),
        "moderation": get_product_moderation(product),
        "risk_review": get_product_risk_review(product),
        "seller_summary": get_product_seller_summary(product),
        "reviews": reviews,
        "total_reviews": total_reviews,
        "average_rating": average_rating,
        "average_stars": average_stars,
        "review_distribution": review_distribution,
    }