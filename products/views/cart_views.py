import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from products import services

logger = logging.getLogger(__name__)


@login_required
def cart(request: HttpRequest) -> HttpResponse:
    """Render the shopping cart page."""
    cart_obj = services.get_user_cart(request.user)
    totals = services.get_cart_totals(request.user)
    pricing_by_id = {item.id: pricing for item, pricing in totals["pricing"]}
    
    for item in cart_obj.items.all():
        item.pricing = pricing_by_id.get(item.id)

    context = {
        "cart": cart_obj,
        "cart_count": services.cart_count(request.user),
        "subtotal": totals["subtotal"],
        "total": totals["total"],
        "original_subtotal": totals["original_subtotal"],
        "shipping_cost": totals["shipping_fee"],
        "discount": totals["discount"],
        "cart_pricing": totals["pricing"],
        "promotion_ended": totals["promotion_ended"],
    }
    return render(request, "cart.html", context)


@login_required
def add_to_cart(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Add a product to the cart (handles GET and POST data parameters)."""
    try:
        cart_item = services.add_to_cart(
            request.user,
            product_slug,
            request.GET.get("promotion_product_id") or request.POST.get("promotion_product_id"),
            request.GET.get("quantity") or request.POST.get("quantity") or 1,
        )
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
        
    totals = services.get_cart_totals(request.user)

    return JsonResponse({
        "success": True,
        "quantity": cart_item.quantity,
        "cart_item_id": cart_item.id,
        "cart_count": services.cart_count(request.user),
        "subtotal": str(totals["subtotal"]),
        "discount": str(totals["discount"]),
        "total": str(totals["total"]),
    })


@login_required
@require_POST
def add_frequently_bought_products_view(request: HttpRequest) -> JsonResponse:
    """Add a set of frequently bought products to the cart."""
    try:
        services.add_frequently_bought_products(request.user, request.body)
        return JsonResponse({
            "success": True,
            "cart_count": services.cart_count(request.user),
        })
    except Exception as e:
        logger.exception("Failed to add frequently bought products.")
        return JsonResponse({"success": False, "message": "Failed to add products."}, status=400)


@login_required
@require_POST
def remove_from_cart(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Remove a specific product from the cart completely."""
    success = services.remove_from_cart(request.user, product_slug)
    return JsonResponse({
        "success": success,
        "cart_count": services.cart_count(request.user),
        "subtotal": str(services.cart_subtotal(request.user)),
        "total": str(services.cart_total(request.user)),
    })


@login_required
@require_POST
def increment_quantity(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Increase the quantity of a specific cart item by one."""
    cart_item = services.increment_quantity(request.user, product_slug)
    return JsonResponse({
        "success": True,
        "quantity": cart_item.quantity,
        "item_subtotal": str(services.get_cart_item_pricing(cart_item)["line_subtotal"]),
        "cart_count": services.cart_count(request.user),
        "subtotal": str(services.cart_subtotal(request.user)),
        "total": str(services.cart_total(request.user)),
    })


@login_required
@require_POST
def decrement_quantity(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Decrease the quantity of a specific cart item by one."""
    cart_item = services.decrement_quantity(request.user, product_slug)

    if cart_item is None:
        return JsonResponse({
            "success": True,
            "removed": True,
            "cart_count": services.cart_count(request.user),
            "subtotal": str(services.cart_subtotal(request.user)),
            "total": str(services.cart_total(request.user)),
        })

    return JsonResponse({
        "success": True,
        "removed": False,
        "quantity": cart_item.quantity,
        "item_subtotal": str(services.get_cart_item_pricing(cart_item)["line_subtotal"]),
        "cart_count": services.cart_count(request.user),
        "subtotal": str(services.cart_subtotal(request.user)),
        "total": str(services.cart_total(request.user)),
    })


@login_required
@require_POST
def update_quantity(request: HttpRequest, product_slug: str) -> JsonResponse:
    """Update a cart item's quantity to a specific numeric value."""
    try:
        data = json.loads(request.body or "{}")
        quantity = data.get("quantity")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid data format."}, status=400)
        
    cart_item = services.update_quantity(request.user, product_slug, quantity)

    if cart_item is None:
        return JsonResponse({
            "success": True,
            "removed": True,
            "cart_count": services.cart_count(request.user),
            "subtotal": str(services.cart_subtotal(request.user)),
            "total": str(services.cart_total(request.user)),
        })

    return JsonResponse({
        "success": True,
        "removed": False,
        "quantity": cart_item.quantity,
        "item_subtotal": str(services.get_cart_item_pricing(cart_item)["line_subtotal"]),
        "cart_count": services.cart_count(request.user),
        "subtotal": str(services.cart_subtotal(request.user)),
        "total": str(services.cart_total(request.user)),
    })


@login_required
@require_POST
def clear_cart(request: HttpRequest) -> JsonResponse:
    """Empty the current user's cart."""
    services.clear_cart(request.user)
    return JsonResponse({
        "success": True,
        "cart_count": 0,
        "subtotal": "0.00",
        "total": "0.00",
    })


@login_required
def cart_data(request: HttpRequest) -> JsonResponse:
    """Retrieve raw cart overview totals as JSON."""
    cart_obj = services.get_user_cart(request.user)
    totals = services.get_cart_totals(request.user)

    return JsonResponse({
        "cart": cart_obj,
        "cart_count": services.cart_count(request.user),
        "subtotal": str(totals["subtotal"]),
        "discount": str(totals["discount"]),
        "total": str(totals["total"]),
    })