import json
import logging

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from accounts import services as account_services
from accounts.models import Seller
from accounts.seller_pdf import export_seller_profile_snapshot
from admin_panel import services
from admin_panel.revenue_report import export_revenue_report
from services.decorators.decorators import permission_required

logger = logging.getLogger(__name__)


@permission_required("accounts.change_seller")
def user_sellers(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of all sellers."""
    total_sellers = account_services.get_all_sellers()
    paginator = Paginator(total_sellers.order_by("-created_at"), 8)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "user_management/seller/seller.html", {
        "sellers": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })


@permission_required("accounts.change_seller")
def user_seller(request: HttpRequest, sellerId: int) -> HttpResponse:
    """Render the detail view for a specific seller."""
    context = services.get_seller_detail(sellerId)
    return render(request, "user_management/seller/detail.html", context)


@permission_required("accounts.change_seller")
def seller_application(request: HttpRequest, sellerId: int) -> HttpResponse:
    """View a specific seller's pending application."""
    context = services.get_pending_seller(sellerId)
    return render(request, "user_management/seller/application.html", context)


@permission_required("accounts.change_seller")
@require_POST
def reject_seller_application(request: HttpRequest, application_id: int) -> JsonResponse:
    """Reject a pending seller application."""
    try:
        payload = json.loads(request.body)
        account_services.reject_seller_application_service(
            application_id=application_id,
            reason=payload.get("reason"),
            notes=payload.get("notes"),
        )
        return JsonResponse({"success": True, "message": "Application rejected successfully."})
    except Exception as exc:
        logger.exception("Failed to reject seller application.")
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@permission_required("accounts.change_seller")
@require_POST
def request_application_changes(request: HttpRequest, application_id: int) -> JsonResponse:
    """Request corrections to a seller's application."""
    try:
        payload = json.loads(request.body)
        account_services.request_application_changes_service(
            application_id=application_id,
            requested_changes=payload.get("requested_changes", []),
            notes=payload.get("notes", ""),
        )
        return JsonResponse({"success": True, "message": "Change request sent successfully."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@permission_required("accounts.change_seller")
@require_POST
def approve_seller_application(request: HttpRequest, application_id: int) -> JsonResponse:
    """Approve a pending seller application."""
    try:
        account_services.approve_seller_application_service(application_id=application_id)
        return JsonResponse({"success": True, "message": "Seller application approved successfully."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@permission_required("accounts.change_seller")
@require_POST
def delete_seller_application(request: HttpRequest, seller_id: int) -> JsonResponse:
    """Delete a seller account entirely."""
    try:
        account_services.delete_seller_account_service(seller_id)
        return JsonResponse({"success": True, "message": "Seller account deleted successfully."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@permission_required("accounts.change_seller")
@require_POST
def flag_seller_document(request: HttpRequest, document_id: int) -> JsonResponse:
    """Flag a specific document uploaded by a seller for review."""
    try:
        payload = json.loads(request.body)
        account_services.flag_seller_document_service(
            document_id=document_id,
            issue=payload.get("issue"),
            note=payload.get("note"),
        )
        return JsonResponse({"success": True, "message": "Document has been flagged successfully."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@permission_required("accounts.change_seller")
@require_POST
def verify_seller_document(request: HttpRequest, document_id: int) -> JsonResponse:
    """Verify a specific seller document."""
    try:
        payload = json.loads(request.body)
        account_services.verify_seller_document_service(
            document_id=document_id,
            document_type=payload.get("document_type"),
        )
        return JsonResponse({"success": True, "message": "Document verified successfully."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@permission_required("accounts.change_seller")
@require_POST
def request_missing_document(request: HttpRequest) -> JsonResponse:
    """Request a missing document from a seller."""
    try:
        payload = json.loads(request.body)
        account_services.request_missing_document_service(
            application_id=payload.get("application_id"),
            document_type=payload.get("document_type"),
            reason=payload.get("reason"),
            note=payload.get("note"),
        )
        return JsonResponse({"success": True, "message": "Document request sent successfully."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@permission_required("accounts.change_seller")
@require_POST
def save_application_notes(request: HttpRequest) -> JsonResponse:
    """Save administrative notes to a seller application."""
    try:
        payload = json.loads(request.body)
        account_services.save_application_notes_service(
            application_id=payload.get("application_id"),
            notes=payload.get("notes", ""),
        )
        return JsonResponse({"success": True, "message": "Notes saved successfully."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)


@permission_required("accounts.change_seller")
def export_seller_orders(request: HttpRequest, seller_id: int) -> HttpResponse:
    """Export orders for a specific seller."""
    seller = get_object_or_404(Seller, id=seller_id)
    return services.export_seller_orders(seller)


@permission_required("accounts.change_seller")
def export_revenue_report_view(request: HttpRequest, seller_id: int) -> HttpResponse:
    """Admin-only endpoint to export a seller's complete revenue report as a PDF."""
    seller = get_object_or_404(Seller, pk=seller_id)
    return export_revenue_report(seller)


@permission_required("accounts.change_seller")
def export_seller_profile(request: HttpRequest, seller_id: int) -> HttpResponse:
    """Admin-only endpoint to export a seller's complete profile snapshot as a PDF."""
    seller = get_object_or_404(
        Seller.objects.select_related("user", "profile", "settings"),
        pk=seller_id,
    )
    return export_seller_profile_snapshot(seller)
