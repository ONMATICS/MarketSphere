import csv
import io
import json
from typing import Any, BinaryIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.text import slugify

from products.models import Brand, Product
from services.cloudinary_service import store_catalog_image

BRAND_WRITE_FIELDS = (
    "name", "slug", "description", "country_of_origin", "founded_year",
    "website", "official_email", "official_phone", "facebook", "instagram",
    "linkedin", "is_active", "is_featured", "display_order",
)


def get_brands_data() -> dict[str, Any]:
    """Retrieve broad aggregates regarding registered active and inactive brands."""
    now = timezone.now()
    brands = Brand.objects.annotate(
        products_count=Count("products", distinct=True),
        categories_count=Count("products__category", distinct=True),
        orders_count=Count("products__order_items__order", distinct=True),
    ).order_by("name")

    total_brands = brands.count()
    return {
        "brands": brands,
        "total_brands": total_brands,
        "brands_added_this_month": brands.filter(created_at__year=now.year, created_at__month=now.month).count(),
        "active_brands": brands.filter(is_active=True).count(),
        "percentage_active": (brands.filter(is_active=True).count() / total_brands) * 100 if total_brands else 0,
        "inactive_brands": brands.filter(is_active=False).count(),
        "inactive_brands_added_this_month": brands.filter(is_active=False, created_at__year=now.year, created_at__month=now.month).count(),
        "featured_brands": brands.filter(is_featured=True).count(),
        "empty_brands": brands.filter(products_count=0).count(),
        "products_assigned": Product.objects.filter(brand__isnull=False).count(),
        "products_assigned_this_month": Product.objects.filter(brand__isnull=False, created_at__year=now.year, created_at__month=now.month).count(),
    }


def brand_payload(brand: Brand) -> dict[str, Any]:
    """Generates a base JSON-friendly dictionary mapping brand fields."""
    return {
        "id": brand.id, "name": brand.name, "slug": brand.slug,
        "description": brand.description, "country_of_origin": brand.country_of_origin,
        "founded_year": brand.founded_year, "website": brand.website,
        "official_email": brand.official_email, "official_phone": brand.official_phone,
        "facebook": brand.facebook, "instagram": brand.instagram, "linkedin": brand.linkedin,
        "is_active": brand.is_active, "is_featured": brand.is_featured, "display_order": brand.display_order,
        "logo_url": brand.logo if brand.logo else "", "cover_image_url": brand.cover_image if brand.cover_image else "",
        "products_count": brand.products.count(),
        "categories_count": brand.products.values("category_id").distinct().count(),
        "created_at": brand.created_at.isoformat(), "updated_at": brand.updated_at.isoformat(),
    }


def get_brands_api_data() -> dict[str, list[dict[str, Any]]]:
    """Expose brand metadata mapping for frontend consumption."""
    return {"brands": [brand_payload(b) for b in Brand.objects.all()]}


def brand_detail_payload(brand: Brand) -> dict[str, Any]:
    """Compile brand-level revenue trends, product listings, and general analytics."""
    products = brand.products.select_related("category", "seller").annotate(
        order_count=Count("order_items__order", distinct=True),
        units_sold=Sum("order_items__quantity"),
        revenue_total=Sum("order_items__total"),
    ).order_by("-created_at")

    product_rows = [{
        "id": p.id, "name": p.name, "sku": p.sku or "—", "seller": p.seller.store_name if p.seller else "—",
        "category": p.category.name if p.category else "Uncategorized", "price": float(p.discount_price or p.price or 0),
        "stock": p.stock_quantity, "orders": p.order_count, "units_sold": p.units_sold or 0,
        "revenue": float(p.revenue_total or 0), "status": p.status, "slug": p.slug if p.slug else "undefined",
        "image_url": p.primary_image.image if p.primary_image else "",
    } for p in products[:20]]

    category_rows = list(brand.products.values("category__id", "category__name").annotate(
        product_count=Count("id", distinct=True), units_sold=Sum("order_items__quantity"), revenue=Sum("order_items__total")
    ).order_by("-product_count", "category__name"))

    categories = [{
        "id": r["category__id"], "name": r["category__name"] or "Uncategorized", 
        "products": r["product_count"], "units_sold": r["units_sold"] or 0, "revenue": float(r["revenue"] or 0)
    } for r in category_rows]

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_start = (month_start - timedelta(days=1)).replace(day=1)
    
    def month_metrics(start, end):
        scoped = brand.products.filter(order_items__order__created_at__gte=start, order_items__order__created_at__lt=end)
        return {
            "products": brand.products.filter(created_at__gte=start, created_at__lt=end).count(),
            "orders": scoped.aggregate(val=Count("order_items__order", distinct=True))["val"] or 0,
            "units": scoped.aggregate(val=Sum("order_items__quantity"))["val"] or 0,
            "revenue": float(scoped.aggregate(val=Sum("order_items__total"))["val"] or 0),
        }

    current_month = month_metrics(month_start, now)
    previous_month = month_metrics(previous_month_start, month_start)

    def change(curr, prev):
        return round(((curr - prev) / prev) * 100, 1) if prev else (100 if curr else 0)

    weekly = []
    from datetime import timedelta
    for index in range(7, -1, -1):
        start = now - timedelta(days=(index + 1) * 7)
        end = now - timedelta(days=index * 7)
        weekly.append({
            "label": start.strftime("%b %-d") if not __import__("sys").platform.startswith("win") else start.strftime("%b %#d"), 
            "revenue": float(brand.products.filter(order_items__order__created_at__gte=start, order_items__order__created_at__lt=end).aggregate(tot=Sum("order_items__total"))["tot"] or 0)
        })

    monthly = []
    cursor = (month_start - timedelta(days=330)).replace(day=1)
    for _ in range(12):
        next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        scoped = brand.products.filter(order_items__order__created_at__gte=cursor, order_items__order__created_at__lt=next_month)
        monthly.append({
            "label": cursor.strftime("%b"), "orders": scoped.aggregate(val=Count("order_items__order", distinct=True))["val"] or 0,
            "units": scoped.aggregate(val=Sum("order_items__quantity"))["val"] or 0,
        })
        cursor = next_month

    payload = brand_payload(brand)
    payload.update({
        "products": product_rows, "categories": categories, 
        "revenue": float(brand.products.aggregate(total=Sum("order_items__total"))["total"] or 0), 
        "orders": brand.products.aggregate(total=Count("order_items__order", distinct=True))["total"] or 0,
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
            {"type": "brand", "title": "Brand created", "description": f"{brand.name} was added.", "time": brand.created_at.isoformat()}, 
            {"type": "brand", "title": "Brand updated", "description": "Brand information updated.", "time": brand.updated_at.isoformat()}
        ],
    })
    return payload


def save_brand(data: dict[str, Any], files: dict[str, Any] | None = None, brand: Brand | None = None) -> Brand:
    """Create or modify a brand, automatically assigning defaults and uploading assets."""
    files = files or {}
    with transaction.atomic():
        brand = brand or Brand()
        for field in BRAND_WRITE_FIELDS:
            if field not in data: continue
            value = data.get(field)
            if field in ("is_active", "is_featured"): value = str(value).lower() in ("1", "true", "yes", "on")
            elif field in ("founded_year", "display_order"): value = int(value) if str(value or "").strip() else (None if field == "founded_year" else 0)
            elif field == "slug": value = str(value or "").strip() or slugify(data.get("name", brand.name))
            else: value = str(value or "").strip()
            setattr(brand, field, value)
            
        if not brand.name: raise ValidationError("Brand name is required.")
        if not brand.slug: brand.slug = slugify(brand.name)
        
        uploaded_logo = files.get("logo")
        uploaded_cover = files.get("cover_image")
        if str(data.get("remove_logo", "")).lower() == "true" and brand.logo: brand.logo = None
        if str(data.get("remove_cover_image", "")).lower() == "true" and brand.cover_image: brand.cover_image = None
            
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


def delete_brand(brand: Brand, remove_products: bool = False) -> None:
    """Hard-delete a brand, optionally stripping it from active products first."""
    if remove_products:
        brand.products.update(brand=None)
    elif brand.products.exists():
        raise ValidationError("Brands with products cannot be deleted. Remove the brand from products first.")
    brand.delete()


def import_brands(upload: BinaryIO) -> int:
    """Import a mass JSON or CSV payload to bootstrap multiple brands."""
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
            if not record.get("name"): raise ValidationError("Every imported brand must have a name.")
            save_brand(record)
            created += 1
    return created