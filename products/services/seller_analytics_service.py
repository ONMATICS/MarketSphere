import csv
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Max, Prefetch, Sum, QuerySet
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import Seller
from notifications.models import ActivityLog
from orders.models import Order, OrderItem
from products.models import Product
from promotions.models import PromotionProduct


ALLOWED_RANGES = (7, 30, 90)
DEFAULT_RANGE = 30

RESERVING_STATUSES = (
    Order.Status.PENDING,
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
)

STATUS_META = [
    (Order.Status.PENDING, "Pending", "#b7802b"),
    (Order.Status.CONFIRMED, "Confirmed", "#9D6638"),
    (Order.Status.PROCESSING, "Processing", "#6b7458"),
    (Order.Status.SHIPPED, "Shipped", "#3f6fa8"),
    (Order.Status.DELIVERED, "Delivered", "#4f7d54"),
    (Order.Status.CANCELLED, "Cancelled", "#b54b3b"),
]


def export_products_csv(seller: Seller) -> HttpResponse:
    """Generate a CSV export containing the seller's complete catalog inventory."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{seller.store_name}_products.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "ID", "Name", "Slug", "SKU", "Barcode", "Category", "Brand",
        "Seller", "Price", "Discount Price", "Discount %", "Stock",
        "Minimum Stock", "Weight", "Status", "Featured", "Primary Image",
        "Created", "Updated",
    ])

    products = seller.products.select_related("category", "brand").prefetch_related("images")

    for product in products:
        image = product.primary_image
        writer.writerow([
            product.id, product.name, product.slug, product.sku, product.barcode,
            product.category.name if product.category else "", product.brand.name if product.brand else "",
            seller.store_name, product.price, product.discount_price, product.discount_percentage,
            product.stock_quantity, product.min_stock_level, product.weight, product.get_status_display(),
            "Yes" if product.is_featured else "No", image.image if image else "",
            product.created_at.strftime("%Y-%m-%d %H:%M"), product.updated_at.strftime("%Y-%m-%d %H:%M"),
        ])

    return response


def export_product_orders(product: Product) -> HttpResponse:
    """Generate a CSV export containing all historical orders traversing a product."""
    order_items = (
        OrderItem.objects.filter(product=product)
        .select_related("order", "order__seller", "product")
        .order_by("-created_at")
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"{product.slug}-orders-{timezone.now().strftime('%Y-%m-%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Order Number", "Order Date", "Order Status", "Payment Status", "Customer",
        "Customer Phone", "Shipping Address", "Shipping City", "Product", "SKU",
        "Quantity", "Unit Price", "Product Total", "Seller", "Order Subtotal",
        "Order Shipping", "Order Discount", "Order Tax", "Order Total",
        "Tracking Number", "Courier", "Shipped At", "Delivered At",
    ])

    for item in order_items:
        order = item.order
        seller = order.seller

        writer.writerow([
            order.order_number, order.created_at.strftime("%Y-%m-%d %H:%M"), order.get_status_display(),
            order.get_payment_status_display(), order.shipping_name, order.shipping_phone or "",
            order.shipping_address, order.shipping_city, product.name, product.sku or "",
            item.quantity, item.price, item.total, seller.store_name, order.subtotal,
            order.shipping_cost, order.discount, order.tax, order.total, order.tracking_number, order.courier,
            order.shipped_at.strftime("%Y-%m-%d %H:%M") if order.shipped_at else "",
            order.delivered_at.strftime("%Y-%m-%d %H:%M") if order.delivered_at else "",
        ])

    return response


def _flag(obj: Any, name: str) -> bool:
    """Evaluate a dynamic boolean flag property or method on an object."""
    value = getattr(obj, name, False)
    return bool(value() if callable(value) else value)


def _delta(current: float | Decimal | int | None, previous: float | Decimal | int | None) -> dict[str, Any] | None:
    """Calculate the direction and percentage variation of two metrics."""
    current, previous = float(current or 0), float(previous or 0)
    if not previous:
        return None
    pct = round((current - previous) / previous * 100, 1)
    return {"pct": abs(pct), "dir": "up" if pct > 0 else "down" if pct < 0 else "flat"}


def _sales_items(product: Product, seller: Seller) -> QuerySet[OrderItem]:
    """Retrieve only finalized (delivered) sale items for performance context."""
    return OrderItem.objects.filter(
        product=product, order__seller=seller, order__status=Order.Status.DELIVERED,
    ).annotate(sold_at=Coalesce("order__delivered_at", "order__created_at"))


def _month_bounds() -> tuple[datetime, datetime]:
    """Determine the accurate start datetime boundary for the current and prior month."""
    now = timezone.now()
    current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous = (current - timedelta(days=1)).replace(day=1)
    return current, previous


def _agg(queryset: QuerySet) -> dict[str, Any]:
    """Derive foundational metrics against a subset of order items."""
    data = queryset.order_by().aggregate(units=Sum("quantity"), revenue=Sum("total"), orders=Count("order", distinct=True))
    units = data["units"] or 0
    revenue = data["revenue"] or Decimal("0.00")
    orders = data["orders"] or 0
    return {
        "units": units, "revenue": revenue, "orders": orders,
        "aov": (revenue / orders) if orders else Decimal("0.00"),
    }


def _inventory(product: Product, seller: Seller) -> dict[str, Any]:
    """Evaluate deep stock reserves and health levels."""
    reserved = (
        OrderItem.objects.filter(
            product=product, order__seller=seller, order__status__in=RESERVING_STATUSES,
        ).aggregate(total=Sum("quantity"))["total"] or 0
    )
    if product.stock_quantity <= 0:
        state, label = "out", "Out of stock"
    elif product.stock_quantity <= product.min_stock_level:
        state, label = "low", "Low stock"
    else:
        state, label = "healthy", "In stock"
        
    address = seller.business_address
    return {
        "state": state, "label": label, "stock": product.stock_quantity,
        "min_level": product.min_stock_level, "reserved": reserved,
        "available": max(product.stock_quantity - reserved, 0),
        "warehouse": address.city if address else "",
    }


def _summary(items: QuerySet[OrderItem]) -> dict[str, Any]:
    """Calculate the global sales summary block for product dashboard."""
    total = _agg(items)
    last_sold = items.aggregate(last=Max("sold_at"))["last"]
    current_start, previous_start = _month_bounds()
    current = _agg(items.filter(sold_at__gte=current_start))
    previous = _agg(items.filter(sold_at__gte=previous_start, sold_at__lt=current_start))
    return {
        **total,
        "last_sold": last_sold,
        "avg_price": (total["revenue"] / total["units"]) if total["units"] else None,
        "units_per_order": round(total["units"] / total["orders"], 1) if total["orders"] else None,
        "has_sales": total["units"] > 0,
        "revenue_delta": _delta(current["revenue"], previous["revenue"]),
        "units_delta": _delta(current["units"], previous["units"]),
        "orders_delta": _delta(current["orders"], previous["orders"]),
        "aov_delta": _delta(current["aov"], previous["aov"]),
    }


def _trend(items: QuerySet[OrderItem], days: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Construct a trailing daily dataset for chart rendering over N days."""
    today = timezone.localdate()
    start_day = today - timedelta(days=days - 1)
    start = timezone.make_aware(datetime.combine(start_day, time.min))
    current = items.filter(sold_at__gte=start)

    rows = (
        current.annotate(day=TruncDate("sold_at"))
        .values("day").order_by()
        .annotate(units=Sum("quantity"), revenue=Sum("total"), orders=Count("order", distinct=True))
    )
    by_day = {row["day"]: row for row in rows}

    series, chart = [], []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        row = by_day.get(day)
        units = (row["units"] or 0) if row else 0
        revenue = (row["revenue"] or Decimal("0")) if row else Decimal("0")
        orders = row["orders"] if row else 0
        label = day.strftime("%b %d")
        series.append({"label": label, "units": units, "revenue": revenue, "orders": orders})
        chart.append({"label": label, "units": units, "revenue": float(revenue), "orders": orders})

    period = _agg(current)
    previous = _agg(items.filter(sold_at__gte=start - timedelta(days=days), sold_at__lt=start))
    peak = max(series, key=lambda d: d["units"]) if period["units"] else None

    return {
        "days": series, "range": days, "units": period["units"],
        "revenue": period["revenue"], "orders": period["orders"],
        "units_delta": _delta(period["units"], previous["units"]),
        "revenue_delta": _delta(period["revenue"], previous["revenue"]),
        "peak": peak, "has_data": period["units"] > 0,
    }, chart


def _status_mix(product: Product, seller: Seller) -> dict[str, Any]:
    """Assess the dispersion of order fulfillment statuses dynamically."""
    rows = (
        OrderItem.objects.filter(product=product, order__seller=seller)
        .values("order__status").order_by()
        .annotate(total=Count("order", distinct=True))
    )
    counts = {row["order__status"]: row["total"] for row in rows}
    total = sum(counts.values())

    segments, stops, cursor = [], [], 0.0
    for key, label, color in STATUS_META:
        count = counts.get(key, 0)
        pct = (count * 100 / total) if total else 0
        segments.append({"key": key, "label": label, "color": color, "count": count, "pct": round(pct, 1)})
        if count:
            stops.append(f"{color} {cursor:.2f}% {cursor + pct:.2f}%")
            cursor += pct

    delivered = next((s for s in segments if s["key"] == Order.Status.DELIVERED), None)
    return {
        "total": total, "segments": segments,
        "conic": f"conic-gradient({', '.join(stops)})" if stops else "",
        "delivered_pct": delivered["pct"] if delivered else 0,
    }


def _locations(product: Product, seller: Seller, limit: int = 5) -> list[dict[str, Any]]:
    """Determine top geographic destinations for the product."""
    base = Order.objects.filter(seller=seller, items__product=product)
    total = base.values("id").distinct().count()
    rows = (
        base.exclude(shipping_city__isnull=True).exclude(shipping_city="")
        .values("shipping_city").order_by()
        .annotate(orders=Count("id", distinct=True))
        .order_by("-orders", "shipping_city")[:limit]
    )
    return [
        {"name": row["shipping_city"], "orders": row["orders"], "pct": round(row["orders"] * 100 / total, 1) if total else 0}
        for row in rows
    ]


def _kpis(product: Product, summary: dict[str, Any]) -> dict[str, Any]:
    """Retrieve macro KPIs extending beyond sales figures."""
    current_start, previous_start = _month_bounds()
    wishlist = product.wishlisted_by
    return {
        "wishlist_total": wishlist.count(),
        "wishlist_delta": _delta(
            wishlist.filter(created_at__gte=current_start).count(),
            wishlist.filter(created_at__gte=previous_start, created_at__lt=current_start).count(),
        ),
        "aov": summary["aov"],
        "aov_delta": summary["aov_delta"],
        "units_per_order": summary["units_per_order"],
        "last_sold": summary["last_sold"],
    }


def _promotions(product: Product) -> list[PromotionProduct]:
    """Check attached promotional activities against execution dates."""
    promos = list(
        PromotionProduct.objects.filter(product=product)
        .select_related("promotion").order_by("-promotion__start_at")
    )
    for pp in promos:
        pp.running = _flag(pp.promotion, "is_running")
        pp.upcoming = _flag(pp.promotion, "is_upcoming")
    return promos


def _recent_orders(product: Product, seller: Seller, limit: int = 25) -> list[Order]:
    """Retrieve quick-glance recent orders spanning this product."""
    return list(
        Order.objects.filter(seller=seller, items__product=product)
        .select_related("user")
        .prefetch_related(Prefetch("items", queryset=OrderItem.objects.filter(product=product), to_attr="product_items"))
        .distinct().order_by("-created_at")[:limit]
    )


def _listing_health(product: Product, image_count: int) -> dict[str, Any]:
    """Score the merchandising quality of a seller's listing."""
    desc_len = len((product.description or "").strip())
    price_valid = product.price is not None and product.price > 0 and (product.discount_price is None or 0 < product.discount_price < product.price)
    
    checks = [
        ("Product information", "Name and description provided", bool(product.name and product.description)),
        ("Images", f"{image_count} image{'' if image_count == 1 else 's'} uploaded", image_count > 0),
        ("Category", product.category.name if product.category else "No category assigned", bool(product.category)),
        ("Brand", product.brand.name if product.brand else "No brand assigned", bool(product.brand)),
        ("Pricing", "Regular and discount price are valid" if price_valid else "Check regular and discount price", price_valid),
        ("Stock available", f"{product.stock_quantity} units in stock", product.stock_quantity > 0),
        ("SKU and barcode", "Both provided" if product.sku and product.barcode else "SKU or barcode is missing", bool(product.sku and product.barcode)),
        ("Short description", "Shown on product cards" if product.short_description else "Add one for cards and search results", bool(product.short_description)),
        ("Detailed description", "Good length" if desc_len >= 100 else "100+ characters recommended", desc_len >= 100),
    ]
    done = sum(1 for _, _, ok in checks if ok)
    return {
        "score": round(done * 100 / len(checks)),
        "done": done,
        "total": len(checks),
        "items": [{"title": t, "description": d, "complete": ok} for t, d, ok in checks],
    }


def _activity(product: Product) -> list[ActivityLog]:
    """List recent systemic adjustments and seller actions matching the product."""
    return list(
        ActivityLog.objects.select_related("actor").filter(
            target_content_type=ContentType.objects.get_for_model(Product),
            target_object_id=product.pk,
        )[:30]
    )


def get_seller_product(seller: Seller, product_slug: str) -> Product:
    """Retrieve a product bounded explicitly to the active seller."""
    queryset = (
        Product.objects.filter(seller=seller)
        .select_related("category", "category__parent", "brand")
        .prefetch_related("images")
    )
    return get_object_or_404(queryset, slug=product_slug)


def normalize_range(raw: Any) -> int:
    """Clamp a requested date range to standard dashboard increments."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_RANGE
    return value if value in ALLOWED_RANGES else DEFAULT_RANGE


def get_seller_product_detail_context(seller: Seller, product_slug: str, raw_range: Any = None) -> dict[str, Any]:
    """Orchestrate the holistic dashboard payload for a seller reviewing one of their products."""
    product = get_seller_product(seller, product_slug)
    days = normalize_range(raw_range)

    images = list(product.images.all())
    primary = next((i for i in images if i.is_primary), images[0] if images else None)

    items = _sales_items(product, seller)
    summary = _summary(items)
    trends, chart_data = _trend(items, days)
    promotions = _promotions(product)
    status_mix = _status_mix(product, seller)

    return {
        "product": product,
        "product_images": images,
        "primary_image": primary,
        "inventory": _inventory(product, seller),
        "performance": summary,
        "sales_trends": trends,
        "chart_data": chart_data,
        "range_options": ALLOWED_RANGES,
        "status_mix": status_mix,
        "order_counts": status_mix["segments"],
        "locations": _locations(product, seller),
        "kpis": _kpis(product, summary),
        "promotions": promotions,
        "active_promotions": sum(1 for p in promotions if p.running),
        "recent_orders": _recent_orders(product, seller),
        "listing_health": _listing_health(product, len(images)),
        "activity_logs": _activity(product),
    }