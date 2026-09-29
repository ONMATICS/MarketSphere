import csv
import json
import logging
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Sum, Q, IntegerField
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import Seller
from admin_panel.marketplace import get_marketplace_settings
from admin_panel.catalog import get_catalog_settings
from admin_panel.settings_data import get_admin_setting
from orders.models import Order, OrderItem
from notifications.services.notifications import schedule_low_stock_event
from .models import Category, Brand, Product, WishlistItem, Cart, CartItem, ProductImage
from promotions.services import sync_product_promotions
from promotions.models import Promotion, PromotionProduct
from services.cloudinary_service import store_product_media

logger = logging.getLogger(__name__)


def _upload_product_image(image_file, product_id):
    result = store_product_media(image_file, product_id=str(product_id), media_type="image")
    return result.get("secure_url") or result.get("url")


# ==============================================================================
# CATEGORY & BRAND SERVICES
# ==============================================================================

def get_all_categories():
    categories = Category.objects.filter(parent=None, is_active=True).prefetch_related(
        Prefetch(
            "children",
            queryset=Category.objects.filter(is_active=True).prefetch_related(
                Prefetch(
                    "children",
                    queryset=Category.objects.filter(is_active=True),
                )
            ),
        )
    )
    return categories


def get_all_brands():
    brands = Brand.objects.filter(is_active=True).all()
    return brands


# ==============================================================================
# PRODUCT RETRIEVAL SERVICES
# ==============================================================================

def get_featured_products():
    return (
        Product.objects.select_related("category", "brand")
        .prefetch_related("images")
        .annotate(
            total_sold=Coalesce(
                Sum(
                    "order_items__quantity",
                    filter=Q(
                        order_items__order__status=Order.Status.DELIVERED
                    ),
                ),
                0,
                output_field=IntegerField(),
            )
        )
        .filter(
            status=Product.Status.PUBLISHED,
            is_featured=True,
            seller__status=Seller.Status.VERIFIED,
        )
    )


def get_new_products(limit=8):
    return (
        Product.objects.select_related("category", "brand", "seller")
        .prefetch_related("images")
        .annotate(
            total_sold=Coalesce(
                Sum(
                    "order_items__quantity",
                    filter=Q(
                        order_items__order__status=Order.Status.DELIVERED
                    ),
                ),
                0,
                output_field=IntegerField(),
            )
        )
        .filter(
            status=Product.Status.PUBLISHED,
            seller__status=Seller.Status.VERIFIED,
        )
        .order_by("-created_at")[:limit]
    )


def get_frequent_products(product):
    return Product.objects.filter(
        category=product.category,
        seller=product.seller,
        status=Product.Status.PUBLISHED,
    ).exclude(id=product.id)[:2]


def get_related_products(product):
    return Product.objects.filter(
        category=product.category,
        seller=product.seller,
        status=Product.Status.PUBLISHED,
    ).exclude(id=product.id)


def get_product_by_slug(product_slug):
    return get_object_or_404(
        Product.objects.select_related("category", "brand").prefetch_related("images"),
        slug=product_slug,
        status=Product.Status.PUBLISHED,
    )


def get_edit_product_by_slug(product_slug, seller):
    return get_object_or_404(
        Product.objects.select_related("category", "brand").prefetch_related("images"),
        slug=product_slug,
        seller=seller,
    )


def get_brand_products(brand_slug):
    return (
        Product.objects.select_related("brand", "category")
        .prefetch_related("images")
        .filter(brand__slug=brand_slug, status=Product.Status.PUBLISHED)
    )


def get_category_products(category_slug):
    return (
        Product.objects.select_related("brand", "category")
        .prefetch_related("images")
        .filter(category__slug=category_slug, status=Product.Status.PUBLISHED)
    )


def get_recently_viewed_products(request, current_product, limit=8):
    recently_viewed_ids = request.session.get("recently_viewed", [])

    products = list(
        Product.objects.select_related("category", "brand", "seller")
        .prefetch_related("images")
        .filter(
            id__in=recently_viewed_ids,
            status=Product.Status.PUBLISHED,
            seller__status=Seller.Status.VERIFIED,
        )
        .exclude(id=current_product.id)
    )

    products.sort(
        key=lambda product: recently_viewed_ids.index(product.id)
    )

    return products[:limit]


def update_recently_viewed_products(request, product):
    recently_viewed = request.session.get("recently_viewed", [])

    if product.id in recently_viewed:
        recently_viewed.remove(product.id)

    recently_viewed.insert(0, product.id)
    recently_viewed = recently_viewed[:10]

    request.session["recently_viewed"] = recently_viewed
    request.session.modified = True


# ==============================================================================
# PRODUCT CREATION & MANAGEMENT SERVICES
# ==============================================================================

def nullable(value):
    """
    Converts empty or invalid values to None.
    """
    if value in ("", "null", "undefined", None):
        return None
    return value


def _validate_product_images(images, existing_count=0):
    catalog_settings = get_catalog_settings()
    maximum_images = catalog_settings.maximum_product_images
    maximum_size = catalog_settings.maximum_image_size_mb * 1024 * 1024
    allowed_types = {
        value.strip().lower().lstrip(".")
        for value in str(get_admin_setting("catalog", "allowed_file_types", "jpg, jpeg, png, webp")).split(",")
        if value.strip()
    }

    if existing_count + len(images) > maximum_images:
        raise ValueError(
            f"A product can have at most {maximum_images} images."
        )

    for image in images:
        extension = image.name.rsplit(".", 1)[-1].lower() if "." in image.name else ""
        if allowed_types and extension not in allowed_types:
            raise ValueError("This image file type is not allowed.")
        if image.size > maximum_size:
            raise ValueError(
                f"Each product image must be {catalog_settings.maximum_image_size_mb} MB or smaller."
            )


@transaction.atomic
def create_product(user, post_data, files):
    required_fields = {
        "name": "Product name",
        "slug": "Slug",
        "category": "Category",
        "price": "Price",
        "stock_quantity": "Stock quantity",
        "min_stock_level": "Minimum stock level",
        "sku": "SKU",
        "short_description": "Short description",
        "description": "Description",
    }

    missing_fields = []
    for field, label in required_fields.items():
        value = nullable(post_data.get(field))
        if value is None:
            missing_fields.append(label)

    images = files.getlist("images")
    if not images:
        missing_fields.append("At least one product image")

    _validate_product_images(images)

    if missing_fields:
        raise ValueError(
            "The following fields are required: " + ", ".join(missing_fields)
        )

    seller = Seller.objects.get(user=user)
    category = Category.objects.get(slug=nullable(post_data.get("category")))
    brand_slug = nullable(post_data.get("brand"))
    brand = Brand.objects.filter(slug=brand_slug).first() if brand_slug else None

    # Future implementation
    tags = json.loads(post_data.get("tags", "[]"))
    dimensions = json.loads(post_data.get("dimensions", "{}"))

    marketplace_settings = get_marketplace_settings()
    product = Product.objects.create(
        seller=seller,
        category=category,
        brand=brand,
        name=post_data["name"],
        slug=post_data["slug"],
        short_description=post_data["short_description"],
        description=post_data["description"],
        sku=post_data["sku"],
        barcode=nullable(post_data.get("barcode")),
        price=post_data["price"],
        discount_price=nullable(post_data.get("discount_price")),
        stock_quantity=post_data["stock_quantity"],
        min_stock_level=post_data["min_stock_level"],
        weight=nullable(post_data.get("weight")),
        status=(
            Product.Status.PENDING
            if marketplace_settings.product_approval_required
            else Product.Status.PUBLISHED
        ),
        is_approved=not marketplace_settings.product_approval_required,
        is_featured=post_data.get("is_featured") == "true",
    )

    for index, image in enumerate(images):
        ProductImage.objects.create(
            product=product,
            image=_upload_product_image(image, product.id),
            is_primary=(index == 0),
            display_order=index + 1,
            alt_text=product.name,
        )

    sync_product_promotions(seller, product, post_data.get("promotions", "[]"))

    return product


def save_draft(user, post_data, files):
    required_fields = {
        "name": "Product name",
        "slug": "Slug",
    }

    missing_fields = []
    for field, label in required_fields.items():
        if not post_data.get(field):
            missing_fields.append(label)

    if missing_fields:
        raise ValueError(
            "The following fields are required: " + ", ".join(missing_fields)
        )

    seller = Seller.objects.get(user=user)
    category_slug = nullable(post_data.get("category"))
    category = Category.objects.filter(slug=category_slug).first() if category_slug else None

    brand_slug = nullable(post_data.get("brand"))
    brand = Brand.objects.filter(slug=brand_slug).first() if brand_slug else None

    # Future implementation
    tags = json.loads(post_data.get("tags", "[]"))
    dimensions = json.loads(post_data.get("dimensions", "{}"))

    product = Product.objects.create(
        seller=seller,
        category=category,
        brand=brand,
        name=post_data["name"],
        slug=post_data["slug"],
        short_description=nullable(post_data.get("short_description")) or "",
        description=nullable(post_data.get("description")) or "",
        sku=nullable(post_data.get("sku")),
        barcode=nullable(post_data.get("barcode")),
        price=nullable(post_data.get("price")),
        discount_price=nullable(post_data.get("discount_price")),
        stock_quantity=nullable(post_data.get("stock_quantity")),
        min_stock_level=nullable(post_data.get("min_stock_level")),
        weight=nullable(post_data.get("weight")),
        status=Product.Status.DRAFT,
        is_featured=post_data.get("is_featured") == "true",
    )

    images = files.getlist("images")
    _validate_product_images(images)
    for index, image in enumerate(images):
        ProductImage.objects.create(
            product=product,
            image=_upload_product_image(image, product.id),
            is_primary=(index == 0),
            display_order=index + 1,
            alt_text=product.name,
        )

    return product


@transaction.atomic
def edit_product(seller, product, post_data, files):
    previous_stock = Product.objects.only("stock_quantity").get(pk=product.pk).stock_quantity
    previous_stock = int(previous_stock or 0)
    category_slug = nullable(post_data.get("category"))
    category = Category.objects.filter(slug=category_slug).first() if category_slug else None

    brand_slug = nullable(post_data.get("brand"))
    brand = Brand.objects.filter(slug=brand_slug).first() if brand_slug else None

    # Future implementation
    tags = json.loads(post_data.get("tags", "[]"))
    dimensions = json.loads(post_data.get("dimensions", "{}"))

    product.category = category
    product.brand = brand
    product.name = post_data["name"]
    product.slug = post_data["slug"]
    product.short_description = nullable(post_data.get("short_description")) or ""
    product.description = nullable(post_data.get("description")) or ""
    product.sku = nullable(post_data.get("sku"))
    product.barcode = nullable(post_data.get("barcode"))
    price = nullable(post_data.get("price"))
    discount_price = nullable(post_data.get("discount_price"))
    product.price = Decimal(str(price)) if price is not None else None
    product.discount_price = (
        Decimal(str(discount_price)) if discount_price is not None else None
    )
    product.stock_quantity = int(nullable(post_data.get("stock_quantity")) or 0)
    product.min_stock_level = int(nullable(post_data.get("min_stock_level")) or 5)
    product.weight = nullable(post_data.get("weight"))
    product.is_featured = post_data.get("is_featured") == "true"
    product.status = post_data.get("visibility")
    if (
        get_marketplace_settings().product_approval_required
        and product.status == Product.Status.PUBLISHED
    ):
        product.status = Product.Status.PENDING
        product.is_approved = False

    product.save()
    schedule_low_stock_event(product, previous_stock, product.stock_quantity)

    # Delete existing images selected by the user
    deleted_images = json.loads(post_data.get("deleted_images", "[]"))
    if deleted_images:
        ProductImage.objects.filter(
            id__in=deleted_images,
            product=product,
        ).delete()

    # Add newly uploaded images
    images = files.getlist("images")
    current_count = product.images.exclude(id__in=deleted_images).count()
    _validate_product_images(images, existing_count=current_count)

    for index, image in enumerate(images):
        ProductImage.objects.create(
            product=product,
            image=_upload_product_image(image, product.id),
            is_primary=(current_count == 0 and index == 0),
            display_order=current_count + index + 1,
            alt_text=product.name,
        )

    # Ensure exactly one primary image exists
    primary = product.images.filter(is_primary=True).first()
    if not primary:
        first_image = product.images.order_by("display_order", "id").first()
        if first_image:
            first_image.is_primary = True
            first_image.save(update_fields=["is_primary"])

    sync_product_promotions(
        seller,
        product,
        post_data.get("promotions", "[]")
        if product.status != Product.Status.DRAFT
        else [],
    )

    return product


def hide_product_by_slug(product_slug, reason=None):
    product = Product.objects.get(slug=product_slug)
    product.status = Product.Status.HIDDEN
    if reason:
        product.admin_notes = reason
    product.save(update_fields=["status", "admin_notes"])


def unhide_product_by_slug(product_slug):
    product = Product.objects.get(slug=product_slug)
    product.status = Product.Status.PUBLISHED
    product.save(update_fields=["status"])


def reject_product(product_slug, admin_note=""):
    product = get_product_by_slug(product_slug)
    product.is_approved = False
    product.status = Product.Status.REJECTED
    product.admin_notes = admin_note
    product.save(update_fields=["is_approved", "admin_notes", "status"])
    return product


def delete_product_by_slug(product_slug):
    try:
        product = Product.objects.get(slug=product_slug)
        try:
            product.delete()
            return {"success": True, "archived": False}
        except ProtectedError:
            product.status = Product.Status.ARCHIVED
            product.save(update_fields=["status"])
            return {"success": True, "archived": True}
    except Product.DoesNotExist:
        return {"success": False, "archived": False}


@transaction.atomic
def approve_product(product_slug, publish_immediately=False):
    product = get_product_by_slug(product_slug)
    product.is_approved = True
    update_fields = ["is_approved"]

    if publish_immediately:
        product.status = Product.Status.PUBLISHED
        update_fields.append("status")

    product.save(update_fields=update_fields)
    return product


def publish_product(product_slug, feature_homepage=False):
    try:
        product = Product.objects.get(slug=product_slug)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    if product.status == Product.Status.PUBLISHED:
        return {"success": True, "changed": False, "message": "Product is already published."}

    product.status = Product.Status.PUBLISHED
    update_fields = ["status"]

    product.save(update_fields=update_fields)

    return {"success": True, "changed": True, "message": "Product published successfully."}


@transaction.atomic
def toggle_product_featured(product_slug, action):
    try:
        product = Product.objects.select_for_update().get(slug=product_slug)
    except Product.DoesNotExist:
        return {"success": False, "error": "not_found", "message": "Product not found."}

    if action == "feature":
        if product.is_featured:
            return {"success": True, "featured": True, "changed": False, "message": "Product is already featured."}
        product.is_featured = True
        product.save(update_fields=["is_featured"])
        return {"success": True, "featured": True, "changed": True, "message": "Product featured successfully."}

    if action == "unfeature":
        if not product.is_featured:
            return {"success": True, "featured": False, "changed": False, "message": "Product is already unfeatured."}
        product.is_featured = False
        product.save(update_fields=["is_featured"])
        return {"success": True, "featured": False, "changed": True, "message": "Product unfeatured successfully."}

    return {"success": False, "error": "invalid_action", "message": "Invalid featured action."}


@transaction.atomic
def toggle_product_archive(product_slug, seller, action):
    try:
        product = Product.objects.select_for_update().get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "error": "not_found", "message": "Product not found."}

    if action == "archive":
        if product.status == Product.Status.ARCHIVED:
            return {"success": True, "archived": True, "changed": False, "message": "Product is already archived."}
        product.status = Product.Status.ARCHIVED
        product.save(update_fields=["status"])
        return {"success": True, "archived": True, "changed": True, "message": "Product archived successfully."}

    if action == "unarchive":
        if product.status != Product.Status.ARCHIVED:
            return {"success": True, "archived": False, "changed": False, "message": "Product is already active."}
        product.status = Product.Status.PUBLISHED
        product.save(update_fields=["status"])
        return {"success": True, "archived": False, "changed": True, "message": "Product restored successfully."}

    return {"success": False, "error": "invalid_action", "message": "Invalid archive action."}


@transaction.atomic
def update_product_pricing(product_slug, seller, price, discount_price=None):
    try:
        product = Product.objects.get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    product.price = price
    product.discount_price = discount_price
    product.save(update_fields=["price", "discount_price"])

    return {
        "success": True,
        "message": "Product pricing updated successfully.",
        "price": product.price,
        "discount_price": product.discount_price,
    }


@transaction.atomic
def remove_product_discount(product_slug):
    try:
        product = Product.objects.get(slug=product_slug)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    if product.discount_price is None:
        return {"success": False, "message": "This product does not have a discount."}

    product.discount_price = None
    product.save(update_fields=["discount_price"])
    return {"success": True, "message": "Discount removed successfully."}


@transaction.atomic
def adjust_product_stock(product_slug, seller, adjustment_type, quantity, reason="", note=""):
    try:
        product = Product.objects.select_for_update().get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    current_stock = product.stock_quantity or 0

    if adjustment_type == "increase":
        new_stock = current_stock + quantity
    elif adjustment_type == "decrease":
        if quantity > current_stock:
            return {"success": False, "message": "Stock cannot be reduced below zero."}
        new_stock = current_stock - quantity
    elif adjustment_type == "set":
        new_stock = quantity
    else:
        return {"success": False, "message": "Invalid adjustment type."}

    product.stock_quantity = new_stock
    product.save(update_fields=["stock_quantity"])
    schedule_low_stock_event(product, current_stock, new_stock)

    return {
        "success": True,
        "message": "Stock adjustment applied successfully.",
        "previous_stock": current_stock,
        "new_stock": new_stock,
        "adjustment_type": adjustment_type,
        "quantity": quantity,
        "reason": reason,
        "note": note,
    }


@transaction.atomic
def mark_product_out_of_stock(product_slug, seller):
    try:
        product = Product.objects.select_for_update().get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    previous_stock = product.stock_quantity
    product.stock_quantity = 0
    product.status = Product.Status.OUT_OF_STOCK
    product.save(update_fields=["stock_quantity", "status"])
    schedule_low_stock_event(product, previous_stock, 0)

    return {"success": True, "message": "Product marked as out of stock.", "stock_quantity": 0}


@transaction.atomic
def restore_product_stock(product_slug, seller):
    try:
        product = Product.objects.select_for_update().get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    if product.stock_quantity <= 0:
        return {"success": False, "message": "Cannot restore product because its stock quantity is zero."}

    product.status = Product.Status.PUBLISHED
    product.save(update_fields=["status"])

    return {"success": True, "message": "Product stock restored successfully.", "stock_quantity": product.stock_quantity}


# ==============================================================================
# SEARCH, FILTER & PAGINATION SERVICES
# ==============================================================================

def get_search_products(q):
    if not q:
        return Product.objects.all()

    return (
        Product.objects.select_related("category", "brand")
        .prefetch_related("images")
        .filter(
            Q(name__icontains=q)
            | Q(short_description__icontains=q)
            | Q(description__icontains=q),
            status=Product.Status.PUBLISHED,
        )
    )


def filter_products(products, category_slugs=None, brand_slugs=None, max_price=None, availability=None, discount_only=False):
    if category_slugs:
        products = products.filter(category__slug__in=category_slugs)

    if brand_slugs:
        products = products.filter(brand__slug__in=brand_slugs)

    if max_price:
        try:
            max_price = Decimal(max_price)
            products = products.filter(
                Q(discount_price__isnull=False, discount_price__lte=max_price)
                | Q(discount_price__isnull=True, price__lte=max_price)
            )
        except (InvalidOperation, TypeError):
            pass

    if availability:
        avail_q = Q()
        if "in_stock" in availability:
            avail_q |= Q(stock_quantity__gt=0)
        if "out_of_stock" in availability:
            avail_q |= Q(stock_quantity=0)
        if avail_q:
            products = products.filter(avail_q)

    if discount_only:
        products = products.filter(discount_price__isnull=False)

    return products


def sort_products(products, sort_value):
    return sort_products_by_price(products, sort_value)


def sort_products_by_price(products, sort_value, price_field=None):
    effective_price = (
        Coalesce(price_field, "discount_price", "price")
        if price_field
        else Coalesce("discount_price", "price")
    )

    if sort_value == "price_low_high":
        return products.order_by(effective_price)
    if sort_value == "price_high_low":
        return products.order_by(effective_price.desc())
    if sort_value == "popularity":
        return products.order_by("-created_at")

    return products.order_by("-created_at")


def paginate_products(products, page_number, per_page=12):
    paginator = Paginator(products, per_page)
    return paginator, paginator.get_page(page_number)


def get_search_categories(products):
    return Category.objects.filter(products__in=products, is_active=True).distinct()[:5]


def get_search_brands(products):
    if not get_catalog_settings().brand_visibility:
        return Brand.objects.none()
    return Brand.objects.filter(products__in=products, is_active=True).distinct()[:5]


# ==============================================================================
# WISHLIST SERVICES
# ==============================================================================

def add_to_wishlist(user, product_slug):
    product = get_object_or_404(Product, slug=product_slug, status=Product.Status.PUBLISHED)
    wishlist_item, created = WishlistItem.objects.get_or_create(user=user, product=product)
    return wishlist_item


def remove_from_wishlist(user, product_slug):
    wishlist_item = WishlistItem.objects.filter(user=user, product__slug=product_slug).first()
    if wishlist_item:
        wishlist_item.delete()
        return True
    return False


def toggle_wishlist(user, product_slug):
    if is_in_wishlist(user, product_slug):
        remove_from_wishlist(user, product_slug)
        return False
    add_to_wishlist(user, product_slug)
    return True


def is_in_wishlist(user, product_slug):
    if not getattr(user, "is_authenticated", False):
        return False
    return WishlistItem.objects.filter(user=user, product__slug=product_slug).exists()


def get_wishlist_ids(user):
    if user.is_authenticated:
        return set(WishlistItem.objects.filter(user=user).values_list("product_id", flat=True))
    return set()


def get_user_wishlist(user):
    if not getattr(user, "is_authenticated", False):
        return WishlistItem.objects.none()
    return WishlistItem.objects.filter(user=user).select_related("product", "product__brand", "product__category")


def wishlist_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    return WishlistItem.objects.filter(user=user).count()


# ==============================================================================
# CART SERVICES
# ==============================================================================

def get_or_create_cart(user):
    cart, created = Cart.objects.get_or_create(user=user)
    return cart


def _promotion_product_for_purchase(product, promotion_product_id=None):
    if not promotion_product_id:
        return None
    try:
        promotion_product_id = int(promotion_product_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid promotion context.")
    try:
        promotion_product = PromotionProduct.objects.select_related(
            "promotion", "product", "product__seller"
        ).get(id=promotion_product_id, product=product)
    except PromotionProduct.DoesNotExist:
        raise ValueError("This product is not part of the selected promotion.")

    now = timezone.now()
    promotion = promotion_product.promotion
    if not (
        promotion.status == Promotion.Status.ACTIVE
        and promotion.start_at <= now < promotion.end_at
    ):
        raise ValueError("This promotion is no longer available.")
    if product.status != Product.Status.PUBLISHED:
        raise ValueError("This product is no longer available.")
    if not product.seller or product.seller.status != Seller.Status.VERIFIED:
        raise ValueError("This seller is not currently verified.")
    if not product.price or promotion_product.promotion_price >= product.price:
        raise ValueError("This promotion price is no longer valid.")
    return promotion_product


def get_promotion_product_for_purchase(product, promotion_product_id):
    return _promotion_product_for_purchase(product, promotion_product_id)


def get_cart_item_pricing(cart_item, refresh_promotion=True):
    """Return authoritative money values for one cart line."""
    product = cart_item.product
    original_price = Decimal(product.price or "0.00")
    promotion_ended = False
    promotion_product = cart_item.promotion_product

    if promotion_product:
        try:
            promotion_product = _promotion_product_for_purchase(
                product, promotion_product.id
            )
        except ValueError:
            promotion_product = None
            promotion_ended = True
            if refresh_promotion:
                cart_item.promotion_product = None
                cart_item.save(update_fields=["promotion_product", "updated_at"])

    effective_price = (
        Decimal(promotion_product.promotion_price)
        if promotion_product
        else Decimal(product.discount_price or product.price or "0.00")
    )
    quantity = int(cart_item.quantity or 0)
    discount_per_unit = (
        max(Decimal("0.00"), original_price - effective_price)
        if promotion_product
        else Decimal("0.00")
    )
    return {
        "original_price": original_price,
        "effective_price": effective_price,
        "discount_per_unit": discount_per_unit,
        "discount_amount": discount_per_unit * quantity,
        "quantity": quantity,
        "line_subtotal": effective_price * quantity,
        "promotion_ended": promotion_ended,
        "promotion_product": promotion_product,
        "is_promotion": bool(promotion_product),
    }

def get_cart_totals(user, cart_items=None):
    cart = get_or_create_cart(user)

    if cart_items is None:
        items = cart.items.select_related(
            "product",
            "product__seller",
            "product__seller__settings",
            "promotion_product__promotion",
        )
    else:
        items = cart_items

    original_subtotal = Decimal("0.00")
    discount = Decimal("0.00")
    shipping_fee = Decimal("0.00")
    payable_subtotal = Decimal("0.00")

    pricing = []
    promotion_ended = False
    shipping_sellers = set()

    for item in items:
        line = get_cart_item_pricing(item)
        item.pricing = line

        original_subtotal += (
            line["original_price"]
            if line["is_promotion"]
            else line["effective_price"]
        ) * line["quantity"]

        discount += line["discount_amount"]
        payable_subtotal += line["line_subtotal"]

        promotion_ended = promotion_ended or line["promotion_ended"]

        seller = item.product.seller

        if seller and seller.id not in shipping_sellers:
            shipping_fee += seller.settings.shipping_fee
            shipping_sellers.add(seller.id)

        pricing.append((item, line))

    print(shipping_fee)
    total = payable_subtotal + shipping_fee

    return {
        "original_subtotal": original_subtotal,
        "discount": discount,
        "subtotal": payable_subtotal,
        "shipping_fee": shipping_fee,
        "total": total,
        "pricing": pricing,
        "promotion_ended": promotion_ended,
    }

def add_to_cart(user, product_slug, promotion_product_id=None, quantity=1):
    product = get_object_or_404(
        Product.objects.select_related("seller"),
        slug=product_slug,
        status=Product.Status.PUBLISHED,
    )
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a positive number.")
    if quantity < 1:
        raise ValueError("Quantity must be a positive number.")
    promotion_product = _promotion_product_for_purchase(product, promotion_product_id)
    if product.stock_quantity < quantity:
        raise ValueError(f"Only {product.stock_quantity} units of '{product.name}' are available.")
    cart = get_or_create_cart(user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        promotion_product=promotion_product,
        defaults={"quantity": quantity},
    )

    if not created:
        next_quantity = (cart_item.quantity or 0) + quantity
        if product.stock_quantity < next_quantity:
            raise ValueError(f"Only {product.stock_quantity} units of '{product.name}' are available.")
        cart_item.quantity = next_quantity
        cart_item.save()
    return cart_item


def add_frequently_bought_products(user, body):
    data = json.loads(body)
    product_ids = data.get("products", [])
    cart, _ = Cart.objects.get_or_create(user=user)

    for product_id in product_ids:
        try:
            product = Product.objects.get(id=int(product_id), status=Product.Status.PUBLISHED)
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart, product=product, defaults={"quantity": 1}
            )
            if not created:
                cart_item.quantity += 1
                cart_item.save(update_fields=["quantity", "updated_at"])
        except (Product.DoesNotExist, ValueError, TypeError):
            continue

    return cart


def remove_from_cart(user, product_slug):
    cart = get_or_create_cart(user)
    cart_item = CartItem.objects.filter(cart=cart, product__slug=product_slug).first()
    if cart_item:
        cart_item.delete()
        return True
    return False


def update_quantity(user, product_slug, quantity):
    cart = get_or_create_cart(user)
    cart_item = CartItem.objects.filter(cart=cart, product__slug=product_slug).first()
    if not cart_item:
        return None

    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        return None

    if qty <= 0:
        cart_item.delete()
        return None

    cart_item.quantity = qty
    cart_item.save()
    return cart_item


def increment_quantity(user, product_slug):
    cart = get_or_create_cart(user)
    cart_item = CartItem.objects.filter(cart=cart, product__slug=product_slug).first()
    if not cart_item:
        return add_to_cart(user, product_slug)
    if cart_item.product.stock_quantity < (cart_item.quantity or 0) + 1:
        raise ValueError(f"Only {cart_item.product.stock_quantity} units of '{cart_item.product.name}' are available.")
    cart_item.quantity = (cart_item.quantity or 0) + 1
    cart_item.save(update_fields=["quantity", "updated_at"])
    return cart_item


def decrement_quantity(user, product_slug):
    cart = get_or_create_cart(user)
    cart_item = CartItem.objects.filter(cart=cart, product__slug=product_slug).first()
    if not cart_item:
        return None

    if (cart_item.quantity or 0) <= 1:
        cart_item.delete()
        return None

    cart_item.quantity = cart_item.quantity - 1
    cart_item.save()
    return cart_item


def clear_cart(user):
    cart = get_or_create_cart(user)
    CartItem.objects.filter(cart=cart).delete()
    return True


def cart_total(user):
    return get_cart_totals(user)["total"]


def cart_subtotal(user):
    return get_cart_totals(user)["original_subtotal"]


def cart_count(user):
    cart = get_or_create_cart(user)
    return CartItem.objects.filter(cart=cart).aggregate(total_quantity=Sum("quantity"))["total_quantity"] or 0


def get_user_cart(user):
    if not getattr(user, "is_authenticated", False):
        return None
    cart = Cart.objects.filter(user=user).prefetch_related(
        "items__product", "items__promotion_product__promotion"
    ).first()
    return cart


# ==============================================================================
# IMAGE MANAGEMENT SERVICES
# ==============================================================================

def upload_product_image(product_slug, image_file, seller):
    try:
        product = Product.objects.get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    last_order = (
        ProductImage.objects.filter(product=product)
        .order_by("-display_order")
        .values_list("display_order", flat=True)
        .first()
    )

    next_order = (last_order + 1) if last_order is not None else 0

    _validate_product_images([image_file], existing_count=product.images.count())

    try:
        image_url = _upload_product_image(image_file, product.id)
    except ValueError as error:
        return {"success": False, "message": str(error)}

    product_image = ProductImage.objects.create(
        product=product,
        image=image_url,
        display_order=next_order,
    )

    return {"success": True, "message": "Product image added successfully.", "image_id": product_image.id}


@transaction.atomic
def delete_product_image(product_slug, image_id, seller):
    try:
        product_image = ProductImage.objects.select_related("product").get(
            id=image_id, product__slug=product_slug, product__seller=seller
        )
    except ProductImage.DoesNotExist:
        return {"success": False, "message": "Product image not found."}

    product = product_image.product
    was_primary = product_image.is_primary
    replacement = None

    if was_primary:
        replacement = (
            ProductImage.objects.filter(product=product)
            .exclude(id=product_image.id)
            .order_by("display_order", "id")
            .first()
        )
        if replacement:
            replacement.is_primary = True
            replacement.save(update_fields=["is_primary"])

    product_image.delete()
    return {"success": True, "message": "Product image deleted successfully.", "replacement_primary": was_primary and replacement is not None}


@transaction.atomic
def reorder_product_images(product_slug, image_ids, seller):
    try:
        product = Product.objects.get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    images = list(ProductImage.objects.filter(product=product, id__in=image_ids))
    image_map = {str(image.id): image for image in images}

    if len(images) != len(image_ids):
        return {"success": False, "message": "Invalid product image list."}

    for index, image_id in enumerate(image_ids):
        image = image_map.get(str(image_id))
        if image:
            image.display_order = index
            image.save(update_fields=["display_order"])

    return {"success": True, "message": "Media order updated successfully."}


@transaction.atomic
def set_primary_product_image(product_slug, image_id, seller):
    try:
        product_image = ProductImage.objects.select_related("product").get(
            id=image_id, product__slug=product_slug, product__seller=seller
        )
    except ProductImage.DoesNotExist:
        return {"success": False, "message": "Product image not found."}

    ProductImage.objects.filter(product=product_image.product, is_primary=True).exclude(id=product_image.id).update(is_primary=False)

    if not product_image.is_primary:
        product_image.is_primary = True
        product_image.save(update_fields=["is_primary"])

    return {"success": True, "message": "Primary image updated successfully."}


# ==============================================================================
# EXPORT SERVICES
# ==============================================================================

def export_products_csv(seller):
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
            product.id,
            product.name,
            product.slug,
            product.sku,
            product.barcode,
            product.category.name if product.category else "",
            product.brand.name if product.brand else "",
            seller.store_name,
            product.price,
            product.discount_price,
            product.discount_percentage,
            product.stock_quantity,
            product.min_stock_level,
            product.weight,
            product.get_status_display(),
            "Yes" if product.is_featured else "No",
            image.image if image else "",
            product.created_at.strftime("%Y-%m-%d %H:%M"),
            product.updated_at.strftime("%Y-%m-%d %H:%M"),
        ])

    return response


def export_product_orders(product):
    order_items = (
        OrderItem.objects.filter(product=product)
        .select_related(
            "order",
            "order__seller",
            "product",
        )
        .order_by("-created_at")
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"{product.slug}-orders-{timezone.now().strftime('%Y-%m-%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Order Number",
        "Order Date",
        "Order Status",
        "Payment Status",
        "Customer",
        "Customer Phone",
        "Shipping Address",
        "Shipping City",
        "Product",
        "SKU",
        "Quantity",
        "Unit Price",
        "Product Total",
        "Seller",
        "Order Subtotal",
        "Order Shipping",
        "Order Discount",
        "Order Tax",
        "Order Total",
        "Tracking Number",
        "Courier",
        "Shipped At",
        "Delivered At",
    ])

    for item in order_items:
        order = item.order
        seller = order.seller

        writer.writerow([
            order.order_number,
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            order.get_status_display(),
            order.get_payment_status_display(),
            order.shipping_name,
            order.shipping_phone or "",
            order.shipping_address,
            order.shipping_city,
            product.name,
            product.sku or "",
            item.quantity,
            item.price,
            item.total,
            seller.store_name,
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
