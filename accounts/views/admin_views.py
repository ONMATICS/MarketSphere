import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from accounts import services
from accounts.models import Seller

logger = logging.getLogger(__name__)


@staff_member_required
@require_POST
def update_store_information(request: HttpRequest, seller_id: int) -> JsonResponse:
    """Staff endpoint to administratively update a specific seller's store data."""
    seller = get_object_or_404(Seller, id=seller_id)
    try:
        data = json.loads(request.body)
        services.update_store_information(seller, data)
        return JsonResponse({"success": True, "message": "Store information updated successfully."})
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request payload."}, status=400)
    except Exception:
        logger.exception("Failed admin store update for seller_id: %s", seller_id)
        return JsonResponse({"success": False, "message": "An unexpected error occurred."}, status=500)


@login_required
def change_store_banner(request: HttpRequest) -> JsonResponse:
    """Change a specific seller's storefront banner."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    seller_id = request.POST.get("seller_id")
    banner = request.FILES.get("banner")

    try:
        banner_url = services.change_store_banner(seller_id=seller_id, banner=banner)
        if banner_url:
            return JsonResponse({"success": True, "banner_url": banner_url})
        return JsonResponse({"success": False, "message": "Unable to update banner."})
    except Exception:
        logger.exception("Failed to change store banner for seller_id: %s", seller_id)
        return JsonResponse({"success": False, "message": "An unexpected error occurred while updating the banner."}, status=500)


@staff_member_required
def change_seller_status(request: HttpRequest) -> JsonResponse:
    """Staff endpoint to administratively alter a seller's active/verified status."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    seller_id = request.POST.get("seller_id")
    seller = Seller.objects.filter(id=seller_id).first()

    if not seller:
        return JsonResponse({"success": False, "message": "Seller not found."})

    try:
        services.update_seller_status(seller, str(request.POST.get("status")))
        return JsonResponse({"success": True, "message": "Seller status updated successfully."})
    except Exception:
        logger.exception("Failed to update seller status for seller_id: %s", seller_id)
        return JsonResponse({"success": False, "message": "An unexpected error occurred while updating seller status."}, status=500)