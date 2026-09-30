import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse, FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from accounts import services as account_service
from accounts.models import Seller
from products import services as cart_service

from . import services as order_service
from .invoice import generate_invoice
from .models import Order
from admin_panel.checkout import get_checkout_settings
from django.contrib.contenttypes.models import ContentType
from notifications.models import ActivityLog
from .packing_slip import generate_packing_slip
from .shipping_label import generate_shipping_label

logger = logging.getLogger(__name__)


def orders(request):
    orders = order_service.get_user_orders(request.user)
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    query_params = request.GET.copy()
    query_params.pop("page", None)
    context = {
        "orders": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    }
    return render(request, "orders.html", context)


def order(request, order_number):
    order = order_service.get_user_order(request.user, order_number)
    context = {
        "order": order,
        "order_activity_logs": ActivityLog.objects.select_related("actor").filter(
            target_content_type=ContentType.objects.get_for_model(Order),
            target_object_id=order.pk,
        )[:20],
    }
    return render(request, "order_detail.html", context)


def checkout(request, cart_item_id=None):
    if not request.user.is_authenticated:
        if not get_checkout_settings().guest_checkout:
            messages.info(request, "Please sign in before checking out.")
            return redirect("login")

        messages.info(
            request,
            "Guest checkout is not available until an account is created."
        )
        return redirect("signup")

    addresses = account_service.get_user_addresses(request.user)
    cart = cart_service.get_user_cart(request.user)

    if cart_item_id is not None:
        selected_item = cart.items.select_related(
            "product",
            "product__seller",
            "promotion_product__promotion",
        ).filter(
            id=cart_item_id
        ).first()

        if not selected_item:
            messages.error(request, "The selected cart item could not be found.")
            return redirect("cart")
        
        # Calculate pricing for the selected item only.
        totals = cart_service.get_cart_totals(
            request.user,
            cart_items=[selected_item],
        )

        checkout_items = [selected_item]

    else:
        totals = cart_service.get_cart_totals(request.user)
        checkout_items = list(cart.items.all())


    pricing_by_id = {
        item.id: pricing
        for item, pricing in totals["pricing"]
    }

    for item in checkout_items:
        item.pricing = pricing_by_id[item.id]

    if totals["promotion_ended"]:
        messages.warning(
            request,
            "A promotion in your cart ended, so its price was updated."
        )

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
import json
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)
@login_required
def place_new_order(request):

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=400,
        )

    try:
        data = json.loads(request.body)

        cart_item_id = data.get("cartItemId")

        if cart_item_id is not None:
            try:
                cart_item_id = int(cart_item_id)
            except (TypeError, ValueError):
                raise ValueError("Invalid cart item.")

        created_orders = order_service.place_order(
            user=request.user,
            address_id=data["addressId"],
            full_name=data.get("fullName"),
            email=data.get("email"),
            phone=data.get("phone"),
            notes=data.get("notes", ""),
            cart_item_id=cart_item_id,
        )

        if not created_orders:
            raise ValueError("No orders were created.")

        primary_order_number = created_orders[0].order_number

        request.session[
            f"checkout_batch_{primary_order_number}"
        ] = [
            order.order_number
            for order in created_orders
        ]

        return JsonResponse(
            {
                "success": True,
                "status": "success",
                "orderNumber": primary_order_number,
            }
        )

    except Exception as e:
        logger.exception("Order placement failed")

        return JsonResponse(
            {
                "success": False,
                "message": str(e),
            },
            status=400,
        )

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from support import services as support_services
@login_required
def submit_review_api(request):
    if request.method == 'POST':
        # Extract data from the FormData object sent by JavaScript
        order_item_id = request.POST.get('order_item_id')
        rating = request.POST.get('rating')
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        # Files are handled in request.FILES
        image = request.FILES.get('image')

        # Pass to service layer
        success, message = support_services.process_product_review(
            user=request.user,
            order_item_id=order_item_id,
            rating=rating,
            title=title,
            description=description,
            image=image
        )

        if success:
            return JsonResponse({'status': 'success', 'message': message})
        else:
            return JsonResponse({'status': 'error', 'message': message}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
    
@login_required
def order_confirmation(request, order_number):
    # 1. Check if this order number acts as a key for a multi-seller batch
    batch_key = f'checkout_batch_{order_number}'
    batch_numbers = request.session.get(batch_key)

    orders = []
    if batch_numbers:
        # Fetch all orders generated during that specific checkout session
        for num in batch_numbers:
            try:
                order = order_service.get_user_order(request.user, num)
                if order:
                    orders.append(order)
            except Exception:
                logger.error(f"Could not retrieve order {num} for confirmation page.")
    else:
        # Fallback: If session expired or accessed directly via a single order link,
        # just fetch the single order natively.
        order = order_service.get_user_order(request.user, order_number)
        if order:
            orders.append(order)

    # 2. Calculate the grand total across all seller orders for the sidebar
    # (Assuming order.total is a numeric type; convert to float/Decimal if necessary)
    checkout_total = sum(order.total for order in orders if hasattr(order, 'total'))

    return render(
        request,
        "confirmation.html",
        {
            "orders": orders,               # Passes the iterable list to your new HTML loop
            "checkout_total": checkout_total, # Passes the sum to the new HTML sidebar
        },
    )
@login_required
def update_shipping(request, order_number):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request."
            },
            status=405
        )

    order = get_object_or_404(
        Order,
        order_number=order_number,
        seller=request.user.seller_profile,
    )

    order_service.update_shipping_information(
        order,
        request.POST,
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Shipping information updated successfully.",
            "courier": order.courier,
            "tracking_number": order.tracking_number,
            "estimated_delivery": order.estimated_delivery,
            "shipping_notes": order.shipping_notes,
        }
    )


@login_required
def order_cancelation(request, order_number):
    is_canceled = order_service.cancel_user_order(request.user, order_number)
    if is_canceled:
        return JsonResponse(
            {
                "status": "success",
                "message": "Your order has been successfully Canceled.",
            }
        )
    return JsonResponse(
        {
            "status": "error",
            "message": "The order can't be canceled due to a hard reason.",
        }
    )


@login_required
def download_invoice(request, order_number):
    seller = get_object_or_404(Seller, user=request.user)

    order = get_object_or_404(
        Order.objects.select_related("user", "seller").prefetch_related(
            "items__product"
        ),
        order_number=order_number,
        seller=seller,
    )

    pdf_buffer = generate_invoice(order)

    return FileResponse(
        pdf_buffer,
        as_attachment=False,
        filename=f"invoice-{order.order_number}.pdf",
        content_type="application/pdf",
    )


def update_seller_note_view(request, order_number):
    try:
        data = json.loads(request.body)
        note = data.get("note", "").strip()
        seller = request.user.seller_profile

        success = order_service.update_seller_note(
            seller=seller, 
            order_number=order_number, 
            note=note
        )

        if success:
            return JsonResponse({
                "success": True, 
                "message": "Seller note updated successfully."
            })
        else:
            return JsonResponse({
                "success": False, 
                "message": "Order not found or you do not have permission to modify it."
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False, 
            "message": "Invalid JSON data provided."
        }, status=400)
    except AttributeError:
        return JsonResponse({
            "success": False, 
            "message": "User does not have an associated seller profile."
        }, status=403)
    except Exception as e:
        return JsonResponse({
            "success": False, 
            "message": "An unexpected error occurred."
        }, status=500)
    

@login_required
def download_shipping_label(request, order_number):
    seller = get_object_or_404(Seller, user=request.user)

    order = get_object_or_404(
        Order.objects.select_related("user", "seller").prefetch_related(
            "items__product"
        ),
        order_number=order_number,
        seller=seller,
    )

    pdf_buffer = generate_shipping_label(order)

    return FileResponse(
        pdf_buffer,
        as_attachment=False,
        filename=f"shipping-label-{order.order_number}.pdf",
        content_type="application/pdf",
    )


@login_required
def download_packing_slip(request, order_number):
    seller = get_object_or_404(Seller, user=request.user)

    order = get_object_or_404(
        Order.objects.select_related("user", "seller").prefetch_related(
            "items__product"
        ),
        order_number=order_number,
        seller=seller,
    )

    pdf_buffer = generate_packing_slip(order)

    return FileResponse(
        pdf_buffer,
        as_attachment=False,
        filename=f"packing-slip-{order.order_number}.pdf",
        content_type="application/pdf",
    )


@login_required
def reorder(request, order_number):
    order = order_service.reorder_user_order(request.user, order_number)
    if order:
        return JsonResponse(
            {
                "status": "success",
                "message": "order has successfully added to cart. See your cart",
            }
        )
    return JsonResponse(
        {
            "status": "error",
            "message": "There is a problem while reordering your order.",
        }
    )
