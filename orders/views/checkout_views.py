import json
import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts import services as account_service
from admin_panel.checkout import get_checkout_settings
from orders import services as order_service
from products import services as cart_service
from services.decorators.decorators import buyer_required, verified_buyer_required

logger = logging.getLogger(__name__)


def checkout(request: HttpRequest, cart_item_id: int = None) -> HttpResponse:
    """Render the checkout page, handling multi-item or single-item ('Buy Now') paths."""
    if not request.user.is_authenticated:
        if not get_checkout_settings().guest_checkout:
            messages.info(request, "Please sign in before checking out.")
            return redirect("login")

        messages.info(request, "Guest checkout is not available until an account is created.")
        return redirect("signup")

    addresses = account_service.get_user_addresses(request.user)
    cart = cart_service.get_user_cart(request.user)

    if cart_item_id is not None:
        selected_item = cart.items.select_related(
            "product",
            "product__seller",
            "promotion_product__promotion",
        ).filter(id=cart_item_id).first()

        if not selected_item:
            messages.error(request, "The selected cart item could not be found.")
            return redirect("cart")
        
        totals = cart_service.get_cart_totals(request.user, cart_items=[selected_item])
        checkout_items = [selected_item]
    else:
        totals = cart_service.get_cart_totals(request.user)
        checkout_items = list(cart.items.all())

    pricing_by_id = {item.id: pricing for item, pricing in totals["pricing"]}
    for item in checkout_items:
        item.pricing = pricing_by_id.get(item.id)

    if totals.get("promotion_ended"):
        messages.warning(request, "A promotion in your cart has ended, so the price was updated.")

    context = {
        "addresses": addresses,
        "cart": cart,
        "checkout_items": checkout_items,
        "subtotal": totals["original_subtotal"],
        "shipping_cost": totals["shipping_fee"],
        "discount": totals["discount"],
        "total": totals["total"],
        "cart_pricing": totals["pricing"],
        "buy_now": cart_item_id is not None,
        "selected_cart_item_id": cart_item_id,
    }
    return render(request, "checkout.html", context)


@verified_buyer_required
@require_POST
def place_new_order(request: HttpRequest) -> JsonResponse:
    """Process an AJAX checkout submission and convert cart items to official Orders."""
    try:
        data = json.loads(request.body)
        cart_item_id = data.get("cartItemId")

        if cart_item_id is not None:
            try:
                cart_item_id = int(cart_item_id)
            except (TypeError, ValueError):
                return JsonResponse({"success": False, "message": "Invalid cart item specified."}, status=400)

        created_orders = order_service.place_order(
            user=request.user,
            address_id=data.get("addressId"),
            full_name=data.get("fullName"),
            email=data.get("email"),
            phone=data.get("phone"),
            notes=data.get("notes", ""),
            cart_item_id=cart_item_id,
        )

        if not created_orders:
            return JsonResponse({"success": False, "message": "No orders were created. Please check your cart."}, status=400)

        primary_order_number = created_orders[0].order_number
        request.session[f"checkout_batch_{primary_order_number}"] = [
            order.order_number for order in created_orders
        ]

        return JsonResponse({
            "success": True,
            "status": "success",
            "orderNumber": primary_order_number,
        })

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request payload."}, status=400)
    except Exception:
        logger.exception("Order placement failed for user: %s", request.user.id)
        return JsonResponse({"success": False, "message": "An unexpected error occurred while placing your order."}, status=500)


@buyer_required
def order_confirmation(request: HttpRequest, order_number: str) -> HttpResponse:
    """Render the post-checkout success page, gathering all orders from a multi-seller checkout."""
    batch_key = f'checkout_batch_{order_number}'
    batch_numbers = request.session.get(batch_key)
    orders_list = []

    if batch_numbers:
        for num in batch_numbers:
            try:
                user_order = order_service.get_user_order(request.user, num)
                if user_order:
                    orders_list.append(user_order)
            except Exception:
                logger.error("Could not retrieve order %s for confirmation page.", num)
    else:
        user_order = order_service.get_user_order(request.user, order_number)
        if user_order:
            orders_list.append(user_order)

    checkout_total = sum(o.total for o in orders_list if hasattr(o, 'total'))

    return render(request, "confirmation.html", {
        "orders": orders_list,
        "checkout_total": checkout_total,
    })
