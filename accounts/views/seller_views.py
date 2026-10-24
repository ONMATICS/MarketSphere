import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts import services
from admin_panel.marketplace import get_marketplace_settings
from services.decorators.decorators import seller_required, verified_user

logger = logging.getLogger(__name__)


@verified_user
def seller_signup_view(request: HttpRequest) -> HttpResponse:
    """Process a user's application to become a registered seller."""
    marketplace_settings = get_marketplace_settings()
    if not marketplace_settings.seller_registration:
        messages.info(request, "Seller registration is currently unavailable.")
        return redirect("home")

    if request.method == "POST":
        seller = services.create_seller_application(
            request.user,
            request.POST,
            request.FILES,
        )
        if not marketplace_settings.seller_approval_required:
            seller.status = seller.Status.VERIFIED
            seller.save(update_fields=["status"])
            seller.application.status = seller.application.Status.APPROVED
            seller.application.reviewed_at = timezone.now()
            seller.application.save(update_fields=["status", "reviewed_at"])
            
        messages.success(request, "Your seller application has been submitted successfully.")
        return redirect("seller-account")
        
    return render(request, "seller_signup.html")


@seller_required
def seller_account(request: HttpRequest) -> HttpResponse:
    """Render the seller's main dashboard and account management page."""
    seller = request.user.seller_profile
    business_address = services.get_bussiness_address(seller)
    documents = services.get_seller_application_documents(seller)
    application_progress = services.calculate_application_progress(seller)

    context = {
        "seller": seller,
        "business_address": business_address,
        "documents": documents,
        "application_progress": application_progress,
    }
    return render(request, "seller_account.html", context)


@seller_required
def update_seller_info(request: HttpRequest) -> JsonResponse:
    """Update general seller store information."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        services.update_seller_information(request.user, request.POST, request.FILES)
        return JsonResponse({"success": True, "message": "Store information updated successfully."})
    except Exception as e:
        logger.exception("Failed to update seller information for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": str(e)}, status=400)


@seller_required
def update_seller_address(request: HttpRequest) -> JsonResponse:
    """Update a seller's registered business address."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        services.update_seller_address(request.user, request.POST)
        return JsonResponse({"success": True, "message": "Business address updated successfully."})
    except Exception as e:
        logger.exception("Failed to update seller address for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": str(e)}, status=400)


@seller_required
def update_seller_profile(request: HttpRequest) -> JsonResponse:
    """Update a seller's profile details."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        success, message = services.update_seller_profile_service(request.user, request.POST)
        return JsonResponse({"success": success, "message": message})
    except Exception:
        logger.exception("Failed to update seller profile for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Unable to update profile at this time."}, status=500)


@seller_required
def update_seller_document(request: HttpRequest) -> JsonResponse:
    """Handle upload and updates to seller registration documents."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        success, message, document = services.update_seller_document_service(
            user=request.user,
            data=request.POST,
            files=request.FILES,
        )

        response = {"success": success, "message": message}
        if success and document:
            response["document_url"] = document.file
            response["uploaded_at"] = document.uploaded_at.strftime("%b %d, %Y")

        return JsonResponse(response)
    except Exception:
        logger.exception("Failed to update seller document for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Unable to upload document at this time."}, status=500)


@seller_required
def update_shipping_preferences_view(request: HttpRequest) -> JsonResponse:
    """Update fulfillment and shipping settings for the seller."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        services.update_shipping_preferences(request.user.seller_profile, request.POST)
        return JsonResponse({"success": True, "message": "Shipping preferences updated successfully."})
    except Exception:
        logger.exception("Failed to update shipping preferences for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Unable to update shipping preferences."}, status=500)


@seller_required
def update_notification_preferences_view(request: HttpRequest) -> JsonResponse:
    """Update a seller's notification dispatch rules."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        services.update_notification_preferences(request.user.seller_profile, request.POST)
        return JsonResponse({"success": True, "message": "Notification preferences updated successfully."})
    except Exception:
        logger.exception("Failed to update notification preferences for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Unable to update notification preferences."}, status=500)


@seller_required
def deactivate_seller_account(request: HttpRequest) -> JsonResponse:
    """Deactivate a seller's active storefront."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request."}, status=405)

    try:
        services.deactivate_seller_account(request.user.seller_profile)
        return JsonResponse({"status": "success", "message": "Seller account deactivated successfully."})
    except Exception:
        logger.exception("Failed to deactivate seller account for user_id: %s", request.user.id)
        return JsonResponse({"status": "error", "message": "Unable to deactivate account at this time."}, status=500)


@seller_required
def reactivate_seller_account(request: HttpRequest) -> JsonResponse:
    """Reactivate a previously deactivated seller storefront."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request."}, status=405)

    try:
        services.reactivate_seller_account(request.user.seller_profile)
        return JsonResponse({"status": "success", "message": "Seller account activated successfully."})
    except Exception:
        logger.exception("Failed to reactivate seller account for user_id: %s", request.user.id)
        return JsonResponse({"status": "error", "message": "Unable to reactivate account at this time."}, status=500)