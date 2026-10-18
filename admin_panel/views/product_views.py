import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from admin_panel import services
from products import services as product_services
from products.models import Brand, Category, Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# PRODUCT MODERATION (Admin)
# ---------------------------------------------------------

@staff_member_required
def catalog_products(request: HttpRequest) -> HttpResponse:
    context = services.get_products_catalog()
    paginator = Paginator(context["products"].order_by("-created_at"), 6)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    
    query_params = request.GET.copy()
    query_params.pop("page", None)
    context.update({
        "products": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })
    return render(request, "catalog/products_management/products.html", context=context)

@staff_member_required
def catalog_product(request: HttpRequest, product_slug: str) -> HttpResponse:
    context = services.get_product_detail(product_slug)
    return render(request, "catalog/products_management/admin_product_detail.html", context=context)

@staff_member_required
@require_POST
def approve_product_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    publish_immediately = data.get("publish_immediately", False)

    if not product_slug:
        return JsonResponse({"success": False, "message": "Product slug is required."}, status=400)

    try:
        product = product_services.approve_product(product_slug=product_slug, publish_immediately=publish_immediately)
        if not product:
            return JsonResponse({"success": False, "message": "Unable to approve product."}, status=400)

        return JsonResponse({
            "success": True,
            "message": "Product approved and published successfully." if publish_immediately else "Product approved successfully.",
            "product": {
                "slug": product.slug,
                "is_approved": product.is_approved,
                "status": product.status,
                "status_display": product.get_status_display(),
            },
        })
    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found."}, status=404)

@staff_member_required
@require_POST
def hide_product_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    reason = data.get("reason", "")
    if not product_slug:
        return JsonResponse({"success": False, "message": "Product slug is required."}, status=400)

    try:
        product_services.hide_product_by_slug(product_slug, reason)
        return JsonResponse({"success": True, "message": "Product hidden from storefront."})
    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found."}, status=404)

@staff_member_required
@require_POST
def unhide_product_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        product_services.unhide_product_by_slug(product_slug)
        return JsonResponse({"success": True, "message": "Product unhidden successfully."})
    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found."}, status=404)

@staff_member_required
@require_POST
def reject_product_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    reason = data.get("reason", "")
    admin_note = data.get("admin_note", "")

    if not reason:
        return JsonResponse({"success": False, "message": "Rejection reason is required."}, status=400)

    try:
        product = product_services.reject_product(product_slug=product_slug, admin_note=admin_note)
        return JsonResponse({
            "success": True,
            "message": "Product rejected successfully.",
            "product": {
                "slug": product.slug,
                "is_approved": product.is_approved,
                "admin_note": product.admin_notes,
            },
        })
    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found."}, status=404)

@staff_member_required
@require_POST
def admin_toggle_product_featured_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    action = data.get("action")
    if action not in {"feature", "unfeature"}:
        return JsonResponse({"success": False, "message": "Invalid featured action."}, status=400)

    result = product_services.toggle_product_featured(product_slug=product_slug, action=action)
    if not result["success"]:
        status_code = 404 if result.get("error") == "not_found" else 400
        return JsonResponse({"success": False, "message": result["message"]}, status=status_code)

    return JsonResponse(result)


# ---------------------------------------------------------
# PRODUCT MANAGEMENT (Seller Operations via Admin Panel)
# ---------------------------------------------------------

@login_required
@require_POST
def publish_product_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    publish_immediately = data.get("publish_immediately", True)
    feature_homepage = data.get("feature_homepage", False)

    if not publish_immediately:
        return JsonResponse({"success": False, "message": "Product must be published immediately."}, status=400)

    result = product_services.publish_product(product_slug=product_slug, feature_homepage=feature_homepage)
    if not result["success"]:
        return JsonResponse({"success": False, "message": result["message"]}, status=404)
    return JsonResponse(result)

@login_required
@require_POST
def upload_product_image_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    image_file = request.FILES.get("image")
    if not image_file:
        return JsonResponse({"success": False, "message": "Image is required."}, status=400)

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)

    result = product_services.upload_product_image(product_slug=product_slug, image_file=image_file, seller=seller)
    return JsonResponse(result, status=200 if result["success"] else 404)

@login_required
@require_POST
def delete_product_image_view(request: HttpRequest, product_slug: str, image_id: int) -> JsonResponse:
    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)

    result = product_services.delete_product_image(product_slug=product_slug, image_id=image_id, seller=seller)
    return JsonResponse(result, status=200 if result["success"] else 404)

@login_required
@require_POST
def reorder_product_images_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    image_ids = data.get("image_ids")
    if not isinstance(image_ids, list) or not image_ids:
        return JsonResponse({"success": False, "message": "Image order is required."}, status=400)

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)

    result = product_services.reorder_product_images(product_slug=product_slug, image_ids=image_ids, seller=seller)
    return JsonResponse(result, status=200 if result["success"] else 400)

@login_required
@require_POST
def set_primary_product_image_view(request: HttpRequest, product_slug: str, image_id: int) -> JsonResponse:
    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)

    result = product_services.set_primary_product_image(product_slug=product_slug, image_id=image_id, seller=seller)
    return JsonResponse(result, status=200 if result["success"] else 404)

@login_required
@require_POST
def update_product_pricing_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    price_value = data.get("price")
    discount_value = data.get("discount_price")

    if price_value in (None, ""):
        return JsonResponse({"success": False, "message": "Price is required."}, status=400)

    try:
        price = Decimal(str(price_value))
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid price."}, status=400)

    if price < 0:
        return JsonResponse({"success": False, "message": "Price cannot be negative."}, status=400)

    discount_price = None
    if discount_value not in (None, ""):
        try:
            discount_price = Decimal(str(discount_value))
        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse({"success": False, "message": "Invalid discount price."}, status=400)
        
        if discount_price < 0:
            return JsonResponse({"success": False, "message": "Discount price cannot be negative."}, status=400)
        if discount_price >= price:
            return JsonResponse({"success": False, "message": "Discount price must be lower than the current price."}, status=400)

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)

    result = product_services.update_product_pricing(
        product_slug=product_slug, seller=seller, price=price, discount_price=discount_price
    )
    return JsonResponse(result, status=200 if result["success"] else 404)

@login_required
@require_POST
def remove_product_discount_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    result = product_services.remove_product_discount(product_slug=product_slug)
    return JsonResponse(result, status=200 if result["success"] else 404)

@login_required
@require_POST
def adjust_product_stock_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    adjustment_type = data.get("adjustment_type")
    quantity = data.get("quantity")
    reason = data.get("reason", "")
    note = data.get("note", "")

    if adjustment_type not in {"increase", "decrease", "set"}:
        return JsonResponse({"success": False, "message": "Invalid adjustment type."}, status=400)

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "message": "Invalid quantity."}, status=400)

    if quantity < 0:
        return JsonResponse({"success": False, "message": "Quantity cannot be negative."}, status=400)

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)

    result = product_services.adjust_product_stock(
        product_slug=product_slug, seller=seller, adjustment_type=adjustment_type,
        quantity=quantity, reason=reason, note=note
    )
    return JsonResponse(result, status=200 if result["success"] else 400)

@login_required
@require_POST
def mark_product_out_of_stock_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)

    result = product_services.mark_product_out_of_stock(product_slug=product_slug, seller=seller)
    return JsonResponse(result, status=200 if result["success"] else 404)

@login_required
@require_POST
def restore_product_stock_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)

    result = product_services.restore_product_stock(product_slug=product_slug, seller=seller)
    return JsonResponse(result, status=200 if result["success"] else 400)

@login_required
@require_POST
def edit_product_view(request: HttpRequest, product_slug: str) -> JsonResponse:
    try:
        product = Product.objects.select_related("seller", "category", "brand").get(slug=product_slug)
    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found."}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    category = None
    category_id = data.get("category_id")
    if category_id:
        category = Category.objects.filter(id=category_id).first()
        if not category:
            return JsonResponse({"success": False, "message": "Selected category not found."}, status=400)

    brand = None
    brand_id = data.get("brand_id")
    if brand_id:
        brand = Brand.objects.filter(id=brand_id).first()
        if not brand:
            return JsonResponse({"success": False, "message": "Selected brand not found."}, status=400)

    post_data = {
        "name": data.get("name", product.name).strip(),
        "slug": data.get("slug", product.slug).strip(),
        "short_description": data.get("short_description", product.short_description or ""),
        "description": data.get("description", product.description or ""),
        "sku": data.get("sku", product.sku or ""),
        "barcode": data.get("barcode", product.barcode or ""),
        "category": category.slug if category else "",
        "brand": brand.slug if brand else "",
        "price": product.price,
        "discount_price": product.discount_price,
        "stock_quantity": product.stock_quantity,
        "min_stock_level": product.min_stock_level,
        "weight": product.weight,
        "is_featured": "true" if product.is_featured else "false",
        "visibility": product.status,
        "tags": json.dumps([]),
        "collections": json.dumps([]),
        "dimensions": json.dumps({}),
        "deleted_images": json.dumps([]),
    }

    try:
        updated_product = product_services.edit_product(
            seller=product.seller, product=product, post_data=post_data, files=request.FILES,
        )
        return JsonResponse({
            "success": True,
            "message": "Product information updated successfully.",
            "product": {
                "id": updated_product.id,
                "name": updated_product.name,
                "slug": updated_product.slug,
            },
        })
    except Exception as exc:
        logger.exception("Failed to update product.")
        return JsonResponse({"success": False, "message": str(exc)}, status=400)