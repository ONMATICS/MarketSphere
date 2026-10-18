import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from accounts.models import Seller
from orders import services as order_service
from orders.invoice import generate_invoice
from orders.models import Order
from orders.packing_slip import generate_packing_slip
from orders.shipping_label import generate_shipping_label

logger = logging.getLogger(__name__)


@login_required
@require_POST
def update_shipping(request: HttpRequest, order_number: str) -> JsonResponse:
    """Update shipping status and tracking for a seller's order."""
    try:
        seller_profile = request.user.seller_profile
    except AttributeError:
        return JsonResponse({"success": False, "message": "Only registered sellers can update shipping."}, status=403)

    order_instance = get_object_or_404(Order, order_number=order_number, seller=seller_profile)
    order_service.update_shipping_information(order_instance, request.POST)

    return JsonResponse({
        "success": True,
        "message": "Shipping information updated successfully.",
        "courier": order_instance.courier,
        "tracking_number": order_instance.tracking_number,
        "estimated_delivery": order_instance.estimated_delivery,
        "shipping_notes": order_instance.shipping_notes,
    })


@login_required
@require_POST
def update_seller_note_view(request: HttpRequest, order_number: str) -> JsonResponse:
    """Update the internal memo/note for an order attached to the seller."""
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
            return JsonResponse({"success": True, "message": "Seller note updated successfully."})
            
        return JsonResponse({"success": False, "message": "Order not found or you do not have permission to modify it."}, status=404)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON data provided."}, status=400)
    except AttributeError:
        return JsonResponse({"success": False, "message": "User does not have an associated seller profile."}, status=403)
    except Exception:
        logger.exception("Failed to update seller note for order: %s", order_number)
        return JsonResponse({"success": False, "message": "An unexpected error occurred."}, status=500)


@login_required
def download_invoice(request: HttpRequest, order_number: str) -> FileResponse:
    """Generate and download a PDF invoice for a specific seller order."""
    seller = get_object_or_404(Seller, user=request.user)
    order_instance = get_object_or_404(
        Order.objects.select_related("user", "seller").prefetch_related("items__product"),
        order_number=order_number,
        seller=seller,
    )
    pdf_buffer = generate_invoice(order_instance)

    return FileResponse(
        pdf_buffer,
        as_attachment=False,
        filename=f"invoice-{order_instance.order_number}.pdf",
        content_type="application/pdf",
    )


@login_required
def download_shipping_label(request: HttpRequest, order_number: str) -> FileResponse:
    """Generate and download a PDF shipping label for a specific seller order."""
    seller = get_object_or_404(Seller, user=request.user)
    order_instance = get_object_or_404(
        Order.objects.select_related("user", "seller").prefetch_related("items__product"),
        order_number=order_number,
        seller=seller,
    )
    pdf_buffer = generate_shipping_label(order_instance)

    return FileResponse(
        pdf_buffer,
        as_attachment=False,
        filename=f"shipping-label-{order_instance.order_number}.pdf",
        content_type="application/pdf",
    )


@login_required
def download_packing_slip(request: HttpRequest, order_number: str) -> FileResponse:
    """Generate and download a PDF packing slip for a specific seller order."""
    seller = get_object_or_404(Seller, user=request.user)
    order_instance = get_object_or_404(
        Order.objects.select_related("user", "seller").prefetch_related("items__product"),
        order_number=order_number,
        seller=seller,
    )
    pdf_buffer = generate_packing_slip(order_instance)

    return FileResponse(
        pdf_buffer,
        as_attachment=False,
        filename=f"packing-slip-{order_instance.order_number}.pdf",
        content_type="application/pdf",
    )