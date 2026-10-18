import json
import logging
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models.deletion import ProtectedError

from accounts.models import Seller
from admin_panel.catalog import get_catalog_settings
from admin_panel.marketplace import get_marketplace_settings
from admin_panel.settings_data import get_admin_setting
from notifications.services.notifications import schedule_low_stock_event
from products.models import Brand, Category, Product, ProductImage
from promotions.services import sync_product_promotions
from services.cloudinary_service import store_product_media

from .catalog_service import get_product_by_slug

logger = logging.getLogger(__name__)


def _upload_product_image(image_file: Any, product_id: int | str) -> str | None:
    """Upload a product image file to Cloudinary and return its URL."""
    result = store_product_media(image_file, product_id=str(product_id), media_type="image")
    return result.get("secure_url") or result.get("url")


def nullable(value: Any) -> Any | None:
    """Convert empty or invalid frontend string values to None."""
    if value in ("", "null", "undefined", None):
        return None
    return value


def _validate_product_images(images: list[Any], existing_count: int = 0) -> None:
    """Validate uploaded images against catalog size and type constraints."""
    catalog_settings = get_catalog_settings()
    maximum_images = catalog_settings.maximum_product_images
    maximum_size = catalog_settings.maximum_image_size_mb * 1024 * 1024
    allowed_types = {
        value.strip().lower().lstrip(".")
        for value in str(get_admin_setting("catalog", "allowed_file_types", "jpg, jpeg, png, webp")).split(",")
        if value.strip()
    }

    if existing_count + len(images) > maximum_images:
        raise ValueError(f"A product can have at most {maximum_images} images.")

    for image in images:
        extension = image.name.rsplit(".", 1)[-1].lower() if "." in image.name else ""
        if allowed_types and extension not in allowed_types:
            raise ValueError("This image file type is not allowed.")
        if image.size > maximum_size:
            raise ValueError(f"Each product image must be {catalog_settings.maximum_image_size_mb} MB or smaller.")


@transaction.atomic
def create_product(user: Any, post_data: dict[str, Any], files: Any) -> Product:
    """Create a new product listing, assigning its images and promotions."""
    required_fields = {
        "name": "Product name", "slug": "Slug", "category": "Category", "price": "Price",
        "stock_quantity": "Stock quantity", "min_stock_level": "Minimum stock level",
        "sku": "SKU", "short_description": "Short description", "description": "Description",
    }

    missing_fields = [label for field, label in required_fields.items() if nullable(post_data.get(field)) is None]
    images = files.getlist("images")
    
    if not images:
        missing_fields.append("At least one product image")

    _validate_product_images(images)

    if missing_fields:
        raise ValueError("The following fields are required: " + ", ".join(missing_fields))

    seller = Seller.objects.get(user=user)
    category = Category.objects.get(slug=nullable(post_data.get("category")))
    brand_slug = nullable(post_data.get("brand"))
    brand = Brand.objects.filter(slug=brand_slug).first() if brand_slug else None

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
        status=Product.Status.PENDING if marketplace_settings.product_approval_required else Product.Status.PUBLISHED,
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


def save_draft(user: Any, post_data: dict[str, Any], files: Any) -> Product:
    """Save a partially completed product listing as a draft."""
    required_fields = {"name": "Product name", "slug": "Slug"}
    missing_fields = [label for field, label in required_fields.items() if not post_data.get(field)]

    if missing_fields:
        raise ValueError("The following fields are required: " + ", ".join(missing_fields))

    seller = Seller.objects.get(user=user)
    category_slug = nullable(post_data.get("category"))
    category = Category.objects.filter(slug=category_slug).first() if category_slug else None
    brand_slug = nullable(post_data.get("brand"))
    brand = Brand.objects.filter(slug=brand_slug).first() if brand_slug else None

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
def edit_product(seller: Seller, product: Product, post_data: dict[str, Any], files: Any) -> Product:
    """Update an existing product listing and manage its image gallery."""
    previous_stock = int(Product.objects.only("stock_quantity").get(pk=product.pk).stock_quantity or 0)
    category_slug = nullable(post_data.get("category"))
    category = Category.objects.filter(slug=category_slug).first() if category_slug else None
    brand_slug = nullable(post_data.get("brand"))
    brand = Brand.objects.filter(slug=brand_slug).first() if brand_slug else None

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
    product.discount_price = Decimal(str(discount_price)) if discount_price is not None else None
    
    product.stock_quantity = int(nullable(post_data.get("stock_quantity")) or 0)
    product.min_stock_level = int(nullable(post_data.get("min_stock_level")) or 5)
    product.weight = nullable(post_data.get("weight"))
    product.is_featured = post_data.get("is_featured") == "true"
    product.status = post_data.get("visibility")

    if get_marketplace_settings().product_approval_required and product.status == Product.Status.PUBLISHED:
        product.status = Product.Status.PENDING
        product.is_approved = False

    product.save()
    schedule_low_stock_event(product, previous_stock, product.stock_quantity)

    deleted_images = json.loads(post_data.get("deleted_images", "[]"))
    if deleted_images:
        ProductImage.objects.filter(id__in=deleted_images, product=product).delete()

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

    primary = product.images.filter(is_primary=True).first()
    if not primary:
        first_image = product.images.order_by("display_order", "id").first()
        if first_image:
            first_image.is_primary = True
            first_image.save(update_fields=["is_primary"])

    sync_product_promotions(seller, product, post_data.get("promotions", "[]") if product.status != Product.Status.DRAFT else [])
    return product


def hide_product_by_slug(product_slug: str, reason: str | None = None) -> None:
    """Hide a product from the storefront catalog."""
    product = Product.objects.get(slug=product_slug)
    product.status = Product.Status.HIDDEN
    if reason:
        product.admin_notes = reason
    product.save(update_fields=["status", "admin_notes"])


def unhide_product_by_slug(product_slug: str) -> None:
    """Restore a hidden product back to published status."""
    product = Product.objects.get(slug=product_slug)
    product.status = Product.Status.PUBLISHED
    product.save(update_fields=["status"])


def reject_product(product_slug: str, admin_note: str = "") -> Product:
    """Reject a pending product listing."""
    product = get_product_by_slug(product_slug)
    product.is_approved = False
    product.status = Product.Status.REJECTED
    product.admin_notes = admin_note
    product.save(update_fields=["is_approved", "admin_notes", "status"])
    return product


def delete_product_by_slug(product_slug: str) -> dict[str, bool]:
    """Delete a product, or archive it if protected foreign keys exist."""
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
def approve_product(product_slug: str, publish_immediately: bool = False) -> Product:
    """Approve a pending product for marketplace display."""
    product = get_product_by_slug(product_slug)
    product.is_approved = True
    update_fields = ["is_approved"]

    if publish_immediately:
        product.status = Product.Status.PUBLISHED
        update_fields.append("status")

    product.save(update_fields=update_fields)
    return product


def publish_product(product_slug: str, feature_homepage: bool = False) -> dict[str, Any]:
    """Publish an approved product."""
    try:
        product = Product.objects.get(slug=product_slug)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    if product.status == Product.Status.PUBLISHED:
        return {"success": True, "changed": False, "message": "Product is already published."}

    product.status = Product.Status.PUBLISHED
    product.save(update_fields=["status"])
    return {"success": True, "changed": True, "message": "Product published successfully."}


@transaction.atomic
def toggle_product_featured(product_slug: str, action: str) -> dict[str, Any]:
    """Toggle a product's featured status on the storefront."""
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
def toggle_product_archive(product_slug: str, seller: Seller, action: str) -> dict[str, Any]:
    """Archive or restore a seller's product listing."""
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
def update_product_pricing(product_slug: str, seller: Seller, price: Decimal, discount_price: Decimal | None = None) -> dict[str, Any]:
    """Update a product's base pricing and discount."""
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
def remove_product_discount(product_slug: str) -> dict[str, Any]:
    """Strip an active discount from a product."""
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
def adjust_product_stock(product_slug: str, seller: Seller, adjustment_type: str, quantity: int, reason: str = "", note: str = "") -> dict[str, Any]:
    """Increase, decrease, or directly set a product's available stock."""
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
def mark_product_out_of_stock(product_slug: str, seller: Seller) -> dict[str, Any]:
    """Instantly mark a product as out of stock, setting its inventory to zero."""
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
def restore_product_stock(product_slug: str, seller: Seller) -> dict[str, Any]:
    """Republish a product if it has available stock."""
    try:
        product = Product.objects.select_for_update().get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    if product.stock_quantity <= 0:
        return {"success": False, "message": "Cannot restore product because its stock quantity is zero."}

    product.status = Product.Status.PUBLISHED
    product.save(update_fields=["status"])

    return {"success": True, "message": "Product stock restored successfully.", "stock_quantity": product.stock_quantity}


def upload_product_image(product_slug: str, image_file: Any, seller: Seller) -> dict[str, Any]:
    """Append a new image to a specific product's gallery."""
    try:
        product = Product.objects.get(slug=product_slug, seller=seller)
    except Product.DoesNotExist:
        return {"success": False, "message": "Product not found."}

    last_order = ProductImage.objects.filter(product=product).order_by("-display_order").values_list("display_order", flat=True).first()
    next_order = (last_order + 1) if last_order is not None else 0

    _validate_product_images([image_file], existing_count=product.images.count())

    try:
        image_url = _upload_product_image(image_file, product.id)
    except ValueError as error:
        return {"success": False, "message": str(error)}

    product_image = ProductImage.objects.create(
        product=product, image=image_url, display_order=next_order,
    )

    return {"success": True, "message": "Product image added successfully.", "image_id": product_image.id}


@transaction.atomic
def delete_product_image(product_slug: str, image_id: int | str, seller: Seller) -> dict[str, Any]:
    """Delete an image, rotating a new primary image if required."""
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
        replacement = ProductImage.objects.filter(product=product).exclude(id=product_image.id).order_by("display_order", "id").first()
        if replacement:
            replacement.is_primary = True
            replacement.save(update_fields=["is_primary"])

    product_image.delete()
    return {"success": True, "message": "Product image deleted successfully.", "replacement_primary": was_primary and replacement is not None}


@transaction.atomic
def reorder_product_images(product_slug: str, image_ids: list[int | str], seller: Seller) -> dict[str, Any]:
    """Reassign sorting indexes to a product's gallery images."""
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
def set_primary_product_image(product_slug: str, image_id: int | str, seller: Seller) -> dict[str, Any]:
    """Rotate the designated primary display image for a product."""
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