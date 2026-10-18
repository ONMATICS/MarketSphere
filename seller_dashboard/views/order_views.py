from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import verified_seller
from notifications.models import ActivityLog
from orders.export_orders_csv import generate_seller_orders_csv
from orders.models import Order
from orders.services import get_seller_orders, get_user_order_for_seller, update_order_status


@login_required
@verified_seller
def orders(request: HttpRequest) -> HttpResponse:
    """Display a paginated list of orders placed with this seller."""
    seller_orders = get_seller_orders(request.user.seller_profile)
    paginator = Paginator(seller_orders, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    
    query_params = request.GET.copy()
    query_params.pop("page", None)
    
    return render(request, "orders/list.html", {
        "dashboard_seller_orders": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })


@login_required
@verified_seller
def order_detail(request: HttpRequest, order_no: str) -> HttpResponse:
    """View details and activity logs for a specific seller order."""
    order = get_user_order_for_seller(request.user.seller_profile, order_no)

    return render(request, "orders/detail.html", {
        "order": order,
        "order_activity_logs": ActivityLog.objects.select_related("actor").filter(
            target_content_type=ContentType.objects.get_for_model(Order),
            target_object_id=order.pk,
        )[:20],
    })


@login_required
@verified_seller
def update_user_order_status(request: HttpRequest, order_no: str, status: str) -> JsonResponse:
    """Update the fulfillment status of an order."""
    update_order_status(
        request.user.seller_profile,
        order_no,
        status,
    )
    return JsonResponse({"success": True, "status": status})


@login_required
def export_seller_orders_csv_view(request: HttpRequest) -> HttpResponse:
    """Generate and download a CSV of the authenticated seller's orders."""
    # Ensure they have a seller profile (redundant check left as defensive design)
    if not hasattr(request.user, 'seller_profile'):
        return HttpResponseForbidden("You are not registered as a seller.")
        
    seller = request.user.seller_profile
    
    if not seller.can_access_dashboard:
        return HttpResponseForbidden("You do not have permission to access the dashboard.")

    csv_content = generate_seller_orders_csv(seller)
    current_date = timezone.now().strftime("%Y-%m-%d")
    filename = f"marketsphere_orders_{current_date}.csv"

    response = HttpResponse(csv_content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    
    return response