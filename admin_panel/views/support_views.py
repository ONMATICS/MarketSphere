from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from admin_panel.services import support_service
from services.decorators.decorators import permission_required


@permission_required("support.view_supportrequest")
@require_GET
def support_requests(request: HttpRequest) -> HttpResponse:
    return render(request, "support/support_list.html",
                  support_service.get_support_list_context(request.GET))


@permission_required("support.view_supportrequest")
@require_GET
def support_request_detail(request: HttpRequest, request_id: int) -> HttpResponse:
    return render(request, "support/support_detail.html",
                  support_service.get_support_detail_context(request_id))


@permission_required("support.change_supportrequest")
@require_POST
def support_request_reply(request: HttpRequest, request_id: int) -> HttpResponse:
    try:
        support_service.submit_admin_response(
            request_id=request_id, admin=request.user, message=request.POST.get("message", ""),
        )
        messages.success(request, "Your response was sent to the buyer.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("admin-support-detail", request_id=request_id)


@permission_required("support.change_supportrequest")
@require_POST
def support_request_status(request: HttpRequest, request_id: int) -> HttpResponse:
    try:
        support_service.change_request_status(
            request_id=request_id, admin=request.user, new_status=request.POST.get("status", ""),
        )
        messages.success(request, "Request status updated.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("admin-support-detail", request_id=request_id)
