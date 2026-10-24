import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from services.decorators.decorators import verified_seller
from admin_panel.settings_data import get_admin_setting
from products import services as product_services
from products.models import Product
from products.services import (
    create_product,
    delete_product_by_slug,
    edit_product,
    get_edit_product_by_slug,
    get_seller_product_detail_context,
    hide_product_by_slug,
    save_draft,
    toggle_product_archive,
    toggle_product_featured,
    unhide_product_by_slug,
)
from promotions.services import get_available_promotions_for_seller

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# PRODUCT MANAGEMENT (Pages)
# ---------------------------------------------------------

@verified_seller
def products(request: HttpRequest) -> HttpResponse:
    """Display a paginated list of the seller's products."""
    seller = request.user.seller_profile
    products_qs = Product.objects.filter(seller=seller).select_related(
        "category", "brand"
    ).prefetch_related("images").order_by("-created_at")
    
    paginator = Paginator(products_qs, 8)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    
    query_params = request.GET.copy()
    query_params.pop("page", None)
    
    return render(request, "products/list.html", {
        "dashboard_seller_products": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })


@verified_seller
def add_product(request: HttpRequest) -> HttpResponse:
    """Handle rendering the product creation form and processing new product submissions."""
    if request.method == "POST":
        try:
            product = create_product(
                request.user,
                request.POST,
                request.FILES,
            )
            return JsonResponse({
                "success": True,
                "message": "Product created successfully.",
                "product_id": product.id,
            })
        except ValueError as error:
            return JsonResponse({"success": False, "message": str(error)}, status=400)

    return render(request, "products/create.html", {
        "available_promotions": get_available_promotions_for_seller(request.user.seller_profile),
        "selected_promotion_ids": [],
    })


@verified_seller
def draft_product(request: HttpRequest) -> HttpResponse:
    """Save a product as a draft without publishing it."""
    if not get_admin_setting("catalog", "allow_seller_drafts", True):
        return JsonResponse({"success": False, "message": "Seller drafts are currently disabled."}, status=403)

    if request.method == "POST":
        try:
            product = save_draft(
                request.user,
                request.POST,
                request.FILES,
            )
            return JsonResponse({
                "success": True,
                "message": "Product drafted successfully.",
                "product_id": product.id,
            })
        except ValueError as error:
            return JsonResponse({"success": False, "message": str(error)}, status=400)

    return render(request, "products/create.html", {
        "available_promotions": get_available_promotions_for_seller(request.user.seller_profile),
        "selected_promotion_ids": [],
    })


@verified_seller
def edit_products(request: HttpRequest, product_slug: str) -> HttpResponse:
    """Render the edit form for an existing product and process updates."""
    product = get_edit_product_by_slug(product_slug, request.user.seller_profile)

    if request.method == "POST":
        try:
            updated_product = edit_product(
                request.user.seller_profile,
                product,
                request.POST,
                request.FILES,
            )
            return JsonResponse({
                "success": True,
                "message": "Product updated successfully.",
                "product_id": updated_product.id,
            })
        except ValueError as error:
            return JsonResponse({"success": False, "message": str(error)}, status=400)

    available_promotions = get_available_promotions_for_seller(request.user.seller_profile)
    selected_promotion_prices = {
        relation.promotion_id: relation.promotion_price
        for relation in product.promotion_products.all()
    }
    
    for promotion in available_promotions:
        promotion.selected_promotion_price = selected_promotion_prices.get(promotion.id)

    context = {
        "product": product,
        "available_promotions": available_promotions,
        "selected_promotion_ids": list(product.promotion_products.values_list("promotion_id", flat=True)),
    }

    return render(request, "products/edit.html", context)


@verified_seller
def product_detail(request: HttpRequest, product_slug: str) -> HttpResponse:
    """View the details of a product from the seller's perspective."""
    seller = request.user.seller_profile
    context = get_seller_product_detail_context(
        seller, product_slug, request.GET.get("range")
    )
    return render(request, "products/detail.html", context)


# ---------------------------------------------------------
# PRODUCT ACTIONS (AJAX)
# ---------------------------------------------------------

@verified_seller
@require_POST
def hide_product(request: HttpRequest) -> JsonResponse:
    """Visually hide a product from the public storefront."""
    try:
        data = json.loads(request.body)
        product_slug = data.get("productSlug")
        hide_product_by_slug(product_slug)
        return JsonResponse({"status": "success", "message": "The product has been hidden successfully."})
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid request payload."}, status=400)
    except Exception:
        logger.exception("Failed to hide product.")
        return JsonResponse({"status": "error", "message": "Something went wrong."}, status=500)


@verified_seller
@require_POST
def unhide_product(request: HttpRequest) -> JsonResponse:
    """Restore visibility of a hidden product to the public storefront."""
    try:
        data = json.loads(request.body)
        product_slug = data.get("productSlug")
        unhide_product_by_slug(product_slug)
        return JsonResponse({"status": "success", "message": "The product has been unhidden successfully."})
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid request payload."}, status=400)
    except Exception:
        logger.exception("Failed to unhide product.")
        return JsonResponse({"status": "error", "message": "Something went wrong."}, status=500)


@verified_seller
@require_POST
def delete_product(request: HttpRequest) -> JsonResponse:
    """Delete a product, or archive it if it has attached historical orders."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid request payload."}, status=400)

    product_slug = data.get("productSlug")
    result = delete_product_by_slug(product_slug)

    if result.get("success"):
        message = "Product has previous orders, so it was archived instead." if result.get("archived") else "Product deleted successfully."
        return JsonResponse({
            "status": "success",
            "archived": result.get("archived"),
            "message": message,
        })

    return JsonResponse({"status": "error", "message": "Product not found."}, status=404)


@verified_seller
@require_POST
def toggle_product_featured_view(request: HttpRequest) -> JsonResponse:
    """Toggle a seller's product featured status."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid request data."}, status=400)

    product_slug = data.get("productSlug")
    action = data.get("action")

    if not product_slug:
        return JsonResponse({"status": "error", "message": "Product slug is required."}, status=400)

    if action not in {"feature", "unfeature"}:
        return JsonResponse({"status": "error", "message": "Invalid featured action."}, status=400)

    result = toggle_product_featured(product_slug=product_slug, action=action)

    if not result.get("success"):
        status_code = 404 if result.get("error") == "not_found" else 400
        return JsonResponse({"status": "error", "message": result.get("message", "Action failed.")}, status=status_code)

    return JsonResponse({
        "status": "success",
        "featured": result.get("featured"),
        "changed": result.get("changed"),
        "message": result.get("message"),
    })


@verified_seller
@require_POST
def toggle_product_archive_view(request: HttpRequest) -> JsonResponse:
    """Toggle the archived state of a product."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid request data."}, status=400)

    product_slug = data.get("productSlug")
    action = data.get("action")

    if not product_slug:
        return JsonResponse({"status": "error", "message": "Product slug is required."}, status=400)

    if action not in {"archive", "unarchive"}:
        return JsonResponse({"status": "error", "message": "Invalid archive action."}, status=400)

    result = toggle_product_archive(
        product_slug=product_slug,
        seller=request.user.seller_profile,
        action=action,
    )

    if not result.get("success"):
        status_code = 404 if result.get("error") == "not_found" else 400
        return JsonResponse({"status": "error", "message": result.get("message", "Action failed.")}, status=status_code)

    return JsonResponse({
        "status": "success",
        "archived": result.get("archived"),
        "changed": result.get("changed"),
        "message": result.get("message"),
    })


# ---------------------------------------------------------
# PRODUCT QUICK ACTIONS (JSON)
# ---------------------------------------------------------

def _owned_product(request: HttpRequest, product_slug: str) -> Tuple[Any, Optional[Product], Optional[JsonResponse]]:
    """Helper to verify and retrieve a product strictly owned by the requesting seller."""
    seller = getattr(request.user, "seller_profile", None) if request.user.is_authenticated else None
    if seller is None:
        return None, None, JsonResponse({"success": False, "message": "Seller profile not found."}, status=403)
        
    product = Product.objects.filter(seller=seller, slug=product_slug).first()
    if product is None:
        return seller, None, JsonResponse({"success": False, "message": "Product not found."}, status=404)
        
    return seller, product, None


def _json_body(request: HttpRequest) -> Optional[Dict[str, Any]]:
    """Helper to parse JSON payloads safely."""
    try:
        return json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        return None


def _service_response(result: Dict[str, Any], success_message: str) -> JsonResponse:
    """Helper to standardize JSON responses for service layer interactions."""
    if result.get("success"):
        return JsonResponse({**result, "message": result.get("message") or success_message})
    return JsonResponse({"success": False, "message": result.get("message", "Action failed.")}, status=400)


@verified_seller
@require_POST
def product_update_pricing(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Update a product's base price and discount price."""
    seller, product, error = _owned_product(request, product_slug)
    if error:
        return error
        
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    try:
        price = Decimal(str(data.get("price")))
        raw_discount = data.get("discount_price")
        discount = None if raw_discount in (None, "") else Decimal(str(raw_discount))
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid price configuration."}, status=400)

    if price < 0:
        return JsonResponse({"success": False, "message": "Price cannot be negative."}, status=400)
        
    if discount is not None and (discount < 0 or discount >= price):
        return JsonResponse({"success": False, "message": "Discount price must be strictly lower than the base price."}, status=400)

    result = product_services.update_product_pricing(
        product_slug=product.slug, seller=seller, price=price, discount_price=discount
    )
    return _service_response(result, "Pricing updated successfully.")


@verified_seller
@require_POST
def product_remove_discount(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Remove any active discount from a product."""
    seller, product, error = _owned_product(request, product_slug)
    if error:
        return error
        
    result = product_services.remove_product_discount(product_slug=product.slug)
    return _service_response(result, "Discount removed.")


@verified_seller
@require_POST
def product_adjust_stock(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Adjust the available stock inventory for a product."""
    seller, product, error = _owned_product(request, product_slug)
    if error:
        return error
        
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    adjustment_type = data.get("adjustment_type")
    if adjustment_type not in {"increase", "decrease", "set"}:
        return JsonResponse({"success": False, "message": "Invalid adjustment type."}, status=400)
        
    try:
        quantity = int(data.get("quantity"))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "message": "Invalid quantity specified."}, status=400)
        
    if quantity < 0:
        return JsonResponse({"success": False, "message": "Quantity cannot be negative."}, status=400)

    result = product_services.adjust_product_stock(
        product_slug=product.slug,
        seller=seller,
        adjustment_type=adjustment_type,
        quantity=quantity,
        reason=data.get("reason", ""),
        note=data.get("note", ""),
    )
    return _service_response(result, "Stock adjusted.")


@verified_seller
@require_POST
def product_mark_out_of_stock(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Manually flag a product as out of stock."""
    seller, product, error = _owned_product(request, product_slug)
    if error:
        return error
        
    result = product_services.mark_product_out_of_stock(product_slug=product.slug, seller=seller)
    return _service_response(result, "Product marked as out of stock.")


@verified_seller
@require_POST
def product_restore_stock(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Restore a product's stock levels from an out-of-stock state."""
    seller, product, error = _owned_product(request, product_slug)
    if error:
        return error
        
    result = product_services.restore_product_stock(product_slug=product.slug, seller=seller)
    return _service_response(result, "Stock restored.")


@verified_seller
@require_POST
def product_visibility(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Manage public visibility state of a product (Hide/Unhide)."""
    seller, product, error = _owned_product(request, product_slug)
    if error:
        return error
        
    data = _json_body(request) or {}
    action = data.get("action")
    
    try:
        if action == "hide":
            hide_product_by_slug(product.slug)
            message = "Product hidden from storefront."
        elif action == "unhide":
            unhide_product_by_slug(product.slug)
            message = "Product is visible again."
        else:
            return JsonResponse({"success": False, "message": "Invalid action specified."}, status=400)
    except Product.DoesNotExist:
        return JsonResponse({"success": False, "message": "Product not found."}, status=404)
        
    return JsonResponse({"success": True, "message": message})
