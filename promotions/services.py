import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import Promotion, PromotionProduct
from services.cloudinary_service import store_promotion_image


def get_available_promotions_for_seller(seller):
    now = timezone.now()

    return (
        Promotion.objects
        .filter(
            status=Promotion.Status.ACTIVE,
            end_at__gte=now,
        )
        .order_by("start_at", "-homepage_priority", "name")
    )

def sync_product_promotions(seller, product, promotion_data):
    """Synchronize a seller product's selected promotion relationships."""
    if product.seller_id != seller.id:
        raise ValueError("You cannot add promotions to this product.")

    if isinstance(promotion_data, str):
        try:
            promotion_data = json.loads(promotion_data or "[]")
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid promotion data.") from exc

    if promotion_data is None:
        promotion_data = []
    if not isinstance(promotion_data, list):
        raise ValueError("Invalid promotion data.")

    now = timezone.now()
    selected = {}
    for item in promotion_data:
        if not isinstance(item, dict) or not item.get("id"):
            raise ValueError("A selected promotion is invalid.")

        try:
            promotion_id = int(item["id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("A selected promotion is invalid.") from exc

        if promotion_id in selected:
            raise ValueError("A promotion cannot be selected more than once.")

        try:
            price = Decimal(str(item.get("price", "")).strip())
        except (InvalidOperation, ValueError):
            raise ValueError("Promotion price must be greater than zero.")

        if price <= 0:
            raise ValueError("Promotion price must be greater than zero.")
        selected[promotion_id] = price

    promotions = {
        promotion.id: promotion
        for promotion in Promotion.objects.filter(id__in=selected)
    }
    if len(promotions) != len(selected):
        raise ValueError("Promotion does not exist.")

    if product.price is None or product.price <= 0:
        raise ValueError("A valid product price is required for promotions.")

    for promotion_id, promotion_price in selected.items():
        promotion = promotions[promotion_id]
        if promotion.status != Promotion.Status.ACTIVE or promotion.end_at < now:
            raise ValueError(f"Promotion '{promotion.name}' is no longer available.")
        if promotion_price >= product.price:
            raise ValueError(
                f"Promotion price must be lower than the product price for {promotion.name}."
            )

        discount_percentage = (
            (product.price - promotion_price) / product.price
        ) * Decimal("100")
        if (
            promotion.maximum_discount_percentage is not None
            and discount_percentage > Decimal(promotion.maximum_discount_percentage)
        ):
            raise ValueError(
                f"The selected promotion allows a maximum discount of "
                f"{promotion.maximum_discount_percentage}%."
            )

    with transaction.atomic():
        PromotionProduct.objects.filter(product=product).exclude(
            promotion_id__in=selected
        ).delete()
        for promotion_id, promotion_price in selected.items():
            PromotionProduct.objects.update_or_create(
                product=product,
                promotion_id=promotion_id,
                defaults={"promotion_price": promotion_price},
            )

def get_current_homepage_promotion():
    now = timezone.now()

    return (
        Promotion.objects
        .filter(
            status=Promotion.Status.ACTIVE,
            display_on_homepage=True,
            start_at__lte=now,
            end_at__gt=now,
        )
        .order_by("-homepage_priority", "-start_at")
        .first()
    )

# =============================================================================
# ADMIN — ALL PROMOTIONS LIST
# =============================================================================
from django.db.models import Count


def get_admin_promotions_queryset(search=None, status=None):
    """Base queryset for the Admin > Promotions > All Promotions page.

    Annotates the participating product count so the template never has
    to call `promotion.product_count` per-row (which would issue one
    query per promotion).
    """
    queryset = Promotion.objects.annotate(
        products_count=Count("promotion_products", distinct=True)
    ).order_by("-created_at")

    if search:
        queryset = queryset.filter(name__icontains=search)

    if status:
        queryset = queryset.filter(status=status)

    return queryset


def get_admin_promotion_summary(queryset=None):
    """Compact summary metrics for the promotions list header cards."""
    now = timezone.now()
    base = queryset if queryset is not None else Promotion.objects.all()

    return {
        "total_promotions": base.count(),
        "active_promotions": base.filter(
            status=Promotion.Status.ACTIVE,
            start_at__lte=now,
            end_at__gt=now,
        ).count(),
        "scheduled_promotions": base.filter(
            status=Promotion.Status.ACTIVE,
            start_at__gt=now,
        ).count(),
        "expired_promotions": base.filter(
            end_at__lt=now,
        ).count(),
    }


def annotate_promotion_display_status(promotions):
    """Attaches `display_status` / `display_status_class` to each promotion
    in an already-paginated iterable, so the template can render a single
    clear badge without re-deriving state logic itself."""
    now = timezone.now()

    for promotion in promotions:
        if promotion.status == Promotion.Status.DRAFT:
            promotion.display_status, promotion.display_status_class = "Draft", "muted"
        elif promotion.status == Promotion.Status.PAUSED:
            promotion.display_status, promotion.display_status_class = "Paused", "warning"
        elif promotion.status == Promotion.Status.ARCHIVED:
            promotion.display_status, promotion.display_status_class = "Archived", "muted"
        elif promotion.end_at < now:
            promotion.display_status, promotion.display_status_class = "Ended", "danger"
        elif promotion.start_at > now:
            promotion.display_status, promotion.display_status_class = "Scheduled", "info"
        else:
            promotion.display_status, promotion.display_status_class = "Live", "success"

    return promotions


# =============================================================================
# ADMIN — CREATE PROMOTION
# =============================================================================
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.dateparse import parse_datetime

from products.models import Category


def _parse_promotion_datetime(raw_value, field_name, errors):
    """Parses a `datetime-local` input value into an aware datetime,
    recording a field-scoped error message on failure."""
    if not raw_value:
        errors.setdefault(field_name, []).append("This field is required.")
        return None

    parsed = parse_datetime(raw_value)
    if parsed is None:
        errors.setdefault(field_name, []).append("Enter a valid date and time.")
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())

    return parsed


def create_promotion_service(data, files):
    """Validates and creates a new marketplace Promotion.

    Mirrors the manual-validation + full_clean() pattern used by
    admin_panel.services.save_brand: plain field assignment inside
    transaction.atomic(), no Django Form class. Returns
    (success, message, promotion, errors) so the view can re-render the
    form with inline messages and preserved input on failure.

    New promotions are always created with the model's default status
    (Draft) — this form does not expose a status selector, matching the
    Promotion model's own `default=Status.DRAFT`.
    """
    errors = {}

    name = (data.get("name") or "").strip()
    if not name:
        errors.setdefault("name", []).append("Promotion name is required.")
    elif len(name) > 150:
        errors.setdefault("name", []).append("Promotion name is too long.")

    badge_text = (data.get("badge_text") or "").strip()
    short_description = (data.get("short_description") or "").strip()
    description = (data.get("description") or "").strip()

    start_at = _parse_promotion_datetime(data.get("start_at"), "start_at", errors)
    end_at = _parse_promotion_datetime(data.get("end_at"), "end_at", errors)

    if start_at and end_at and end_at <= start_at:
        errors.setdefault("end_at", []).append("End date must be after the start date.")

    maximum_discount_percentage = None
    raw_discount = (data.get("maximum_discount_percentage") or "").strip()
    if raw_discount:
        try:
            maximum_discount_percentage = int(raw_discount)
        except ValueError:
            errors.setdefault("maximum_discount_percentage", []).append(
                "Enter a whole number between 1 and 100."
            )
        else:
            if not (1 <= maximum_discount_percentage <= 100):
                errors.setdefault("maximum_discount_percentage", []).append(
                    "Maximum discount must be between 1 and 100."
                )

    display_on_homepage = str(data.get("display_on_homepage", "")).lower() in (
        "1", "true", "on", "yes",
    )

    homepage_priority = 0
    if display_on_homepage:
        raw_priority = (data.get("homepage_priority") or "0").strip() or "0"
        try:
            homepage_priority = int(raw_priority)
        except ValueError:
            errors.setdefault("homepage_priority", []).append(
                "Homepage priority must be a whole number."
            )
        else:
            if homepage_priority < 0:
                errors.setdefault("homepage_priority", []).append(
                    "Homepage priority cannot be negative."
                )

    category_ids = (
        data.getlist("categories") if hasattr(data, "getlist") else (data.get("categories") or [])
    )
    categories_qs = Category.objects.filter(id__in=category_ids) if category_ids else Category.objects.none()

    if errors:
        return False, "Please correct the errors below.", None, errors

    with transaction.atomic():
        promotion = Promotion(
            name=name,
            badge_text=badge_text,
            short_description=short_description,
            description=description,
            start_at=start_at,
            end_at=end_at,
            maximum_discount_percentage=maximum_discount_percentage,
            display_on_homepage=display_on_homepage,
            homepage_priority=homepage_priority,
        )

        banner = files.get("banner")
        thumbnail = files.get("thumbnail")

        try:
            promotion.full_clean(exclude=["slug"])
        except DjangoValidationError as exc:
            for field, field_messages in exc.message_dict.items():
                errors.setdefault(field, []).extend(field_messages)
            return False, "Please correct the errors below.", None, errors

        promotion.save()

        media_updates = {}
        if banner:
            result = store_promotion_image(banner, str(promotion.id), "banner")
            media_updates["banner"] = result.get("secure_url") or result.get("url")
        if thumbnail:
            result = store_promotion_image(thumbnail, str(promotion.id), "thumbnail")
            media_updates["thumbnail"] = result.get("secure_url") or result.get("url")
        if media_updates:
            for field, url in media_updates.items():
                setattr(promotion, field, url)
            promotion.save(update_fields=[*media_updates, "updated_at"])

        if categories_qs.exists():
            promotion.categories.set(categories_qs)

    return True, f'Promotion "{promotion.name}" was created as a draft.', promotion, {}

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

def update_promotion_service(data, files, promotion_slug):
    """Validates and updates an existing marketplace Promotion.

    Mirrors the create_promotion_service pattern. Extracts the instance 
    via the provided slug, runs manual validation, updates fields, 
    calls full_clean(), and saves inside an atomic transaction.
    Returns (success, message, promotion, errors).
    """
    # 1. Fetch the existing promotion
    promotion = get_object_or_404(Promotion, slug=promotion_slug)
    
    errors = {}

    # 2. Extract and validate basic text fields
    name = (data.get("name") or "").strip()
    if not name:
        errors.setdefault("name", []).append("Promotion name is required.")
    elif len(name) > 150:
        errors.setdefault("name", []).append("Promotion name is too long.")

    badge_text = (data.get("badge_text") or "").strip()
    short_description = (data.get("short_description") or "").strip()
    description = (data.get("description") or "").strip()
    status = (data.get("status") or "").strip()
    print(status)
    # 3. Parse Dates (Assumes _parse_promotion_datetime is available in the module)
    start_at = _parse_promotion_datetime(data.get("start_at"), "start_at", errors)
    end_at = _parse_promotion_datetime(data.get("end_at"), "end_at", errors)

    if start_at and end_at and end_at <= start_at:
        errors.setdefault("end_at", []).append("End date must be after the start date.")

    # 4. Parse and validate discount
    maximum_discount_percentage = None
    raw_discount = (data.get("maximum_discount_percentage") or "").strip()
    if raw_discount:
        try:
            maximum_discount_percentage = int(raw_discount)
        except ValueError:
            errors.setdefault("maximum_discount_percentage", []).append(
                "Enter a whole number between 1 and 100."
            )
        else:
            if not (1 <= maximum_discount_percentage <= 100):
                errors.setdefault("maximum_discount_percentage", []).append(
                    "Maximum discount must be between 1 and 100."
                )

    # 5. Homepage display & Priority
    display_on_homepage = str(data.get("display_on_homepage", "")).lower() in (
        "1", "true", "on", "yes",
    )

    homepage_priority = 0
    if display_on_homepage:
        raw_priority = (data.get("homepage_priority") or "0").strip() or "0"
        try:
            homepage_priority = int(raw_priority)
        except ValueError:
            errors.setdefault("homepage_priority", []).append(
                "Homepage priority must be a whole number."
            )
        else:
            if homepage_priority < 0:
                errors.setdefault("homepage_priority", []).append(
                    "Homepage priority cannot be negative."
                )

    # 6. Categories Many-to-Many
    category_ids = (
        data.getlist("categories") if hasattr(data, "getlist") else (data.get("categories") or [])
    )
    # We always build the queryset. If category_ids is empty, it returns an empty queryset.
    categories_qs = Category.objects.filter(id__in=category_ids)

    # If manual validation caught any issues, return early before hitting the DB
    if errors:
        return False, "Please correct the errors below.", promotion, errors

    # 7. Apply updates inside a transaction
    with transaction.atomic():
        promotion.name = name
        promotion.badge_text = badge_text
        promotion.short_description = short_description
        promotion.description = description
        promotion.status = status.lower()
        # Only overwrite dates if parsing succeeded
        if start_at:
            promotion.start_at = start_at
        if end_at:
            promotion.end_at = end_at
            
        promotion.maximum_discount_percentage = maximum_discount_percentage
        promotion.display_on_homepage = display_on_homepage
        promotion.homepage_priority = homepage_priority

        # 8. Handle file uploads (only overwrite if a new file was actually submitted)
        banner = files.get("banner")
        thumbnail = files.get("thumbnail")

        if banner:
            result = store_promotion_image(banner, str(promotion.id), "banner")
            promotion.banner = result.get("secure_url") or result.get("url")
        if thumbnail:
            result = store_promotion_image(thumbnail, str(promotion.id), "thumbnail")
            promotion.thumbnail = result.get("secure_url") or result.get("url")

        # 9. Final Model Validation
        try:
            # We exclude 'slug' because the model's custom save() method handles it
            promotion.full_clean(exclude=["slug"])
        except DjangoValidationError as exc:
            for field, field_messages in exc.message_dict.items():
                errors.setdefault(field, []).extend(field_messages)
            return False, "Please correct the errors below.", promotion, errors

        # 10. Save and Update Relations
        promotion.save()

        # Crucial Difference from Create: We do NOT use `if categories_qs.exists():` here.
        # If the user unchecked all categories, we want `set()` to clear them out.
        promotion.categories.set(categories_qs)

    return True, f'Promotion "{promotion.name}" was successfully updated.', promotion, {}
# =============================================================================
# ADMIN — PROMOTION DETAILS
# =============================================================================
from django.shortcuts import get_object_or_404


def get_admin_promotion_detail(promotion_slug):
    """Gathers everything the Promotion Details page needs in a handful of
    efficient queries: the promotion itself, its curated/derived display
    categories, the total participating-product count, and a small
    preview of participating products with seller/category preloaded so
    the template never triggers an N+1 query."""
    promotion = get_object_or_404(
        Promotion.objects.prefetch_related("categories"),
        slug=promotion_slug,
    )

    promotion_products_qs = (
        PromotionProduct.objects.filter(promotion=promotion)
        .select_related("product", "product__seller", "product__category")
        .order_by("-is_featured", "display_order", "-created_at")
    )

    return {
        "promotion": promotion,
        "display_categories": promotion.get_display_categories(),
        "products_count": promotion_products_qs.count(),
        "product_preview": list(promotion_products_qs[:6]),
    }

# =============================================================================
# ADMIN — MANAGE PROMOTION PRODUCTS
# =============================================================================
from decimal import Decimal, InvalidOperation
from django.db.models import Q

from accounts.models import Seller
from products.models import Category


def get_admin_promotion_products_queryset(promotion, search=None, seller_id=None,
                                            category_id=None, featured=None, sort=None):
    """Base queryset for Manage Promotion Products. select_related covers
    everything the row needs (product, its seller, its category) so the
    template never issues a per-row query."""
    queryset = (
        PromotionProduct.objects.filter(promotion=promotion)
        .select_related("product", "product__seller", "product__category")
        .prefetch_related("product__images")
    )

    if search:
        queryset = queryset.filter(
            Q(product__name__icontains=search) | Q(product__sku__icontains=search)
        )

    if seller_id:
        queryset = queryset.filter(product__seller_id=seller_id)

    if category_id:
        queryset = queryset.filter(product__category_id=category_id)

    if featured == "featured":
        queryset = queryset.filter(is_featured=True)
    elif featured == "not_featured":
        queryset = queryset.filter(is_featured=False)

    sort_map = {
        "name": "product__name",
        "-name": "-product__name",
        "promo_price": "promotion_price",
        "-promo_price": "-promotion_price",
        "regular_price": "product__price",
        "-regular_price": "-product__price",
        "newest": "-created_at",
        "oldest": "created_at",
    }

    if sort in sort_map:
        queryset = queryset.order_by(sort_map[sort])
    else:
        queryset = queryset.order_by("-is_featured", "display_order", "-created_at")

    return queryset


def get_promotion_product_filters(promotion):
    """Sellers/categories actually represented among this promotion's
    products — not every seller/category in the marketplace."""
    return {
        "sellers": Seller.objects.filter(
            products__promotion_products__promotion=promotion
        ).distinct().order_by("store_name"),
        "categories": Category.objects.filter(
            products__promotion_products__promotion=promotion
        ).distinct().order_by("name"),
    }


def get_promotion_products_summary(promotion):
    base = PromotionProduct.objects.filter(promotion=promotion)
    return {
        "total_products": base.count(),
        "featured_products": base.filter(is_featured=True).count(),
    }


def update_promotion_product_price_service(promotion_product_id, new_price_raw):
    """Updates PromotionProduct.promotion_price only — Product.price is
    never touched. Reuses the same validation rules already enforced by
    sync_product_promotions for the seller-side bulk flow: price > 0,
    price below the product's regular price, and within the promotion's
    maximum_discount_percentage."""
    try:
        promotion_product = PromotionProduct.objects.select_related(
            "product", "promotion"
        ).get(pk=promotion_product_id)
    except PromotionProduct.DoesNotExist:
        raise ValueError("This product is no longer part of the promotion.")

    try:
        new_price = Decimal(str(new_price_raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Enter a valid promotion price.")

    if new_price <= 0:
        raise ValueError("Promotion price must be greater than zero.")

    product = promotion_product.product
    if product.price is None or product.price <= 0:
        raise ValueError("This product does not have a valid regular price.")

    if new_price >= product.price:
        raise ValueError("Promotion price must be lower than the regular price.")

    promotion = promotion_product.promotion
    if promotion.maximum_discount_percentage is not None:
        discount_percentage = ((product.price - new_price) / product.price) * Decimal("100")
        if discount_percentage > Decimal(promotion.maximum_discount_percentage):
            raise ValueError(
                f"This promotion allows a maximum discount of "
                f"{promotion.maximum_discount_percentage}%."
            )

    promotion_product.promotion_price = new_price
    promotion_product.full_clean()
    promotion_product.save(update_fields=["promotion_price", "updated_at"])

    return promotion_product


def toggle_promotion_product_featured_service(promotion_product_id):
    promotion_product = get_object_or_404(PromotionProduct, pk=promotion_product_id)
    promotion_product.is_featured = not promotion_product.is_featured
    promotion_product.save(update_fields=["is_featured", "updated_at"])
    return promotion_product


def remove_promotion_product_service(promotion_product_id):
    """Deletes the PromotionProduct relation row only. The Product itself
    is never deleted or otherwise modified."""
    promotion_product = get_object_or_404(PromotionProduct, pk=promotion_product_id)
    promotion_product.delete()
    return True
