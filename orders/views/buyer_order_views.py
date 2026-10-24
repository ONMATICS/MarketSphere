import logging

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from notifications.models import ActivityLog
from orders import services as order_service
from orders.models import Order
from support import services as support_services
from services.decorators.decorators import buyer_required

logger = logging.getLogger(__name__)


@buyer_required
def orders(request: HttpRequest) -> HttpResponse:
    """Display a paginated list of the current user's orders."""
    user_orders = order_service.get_user_orders(request.user)
    paginator = Paginator(user_orders, 10)
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


@buyer_required
def order(request: HttpRequest, order_number: str) -> HttpResponse:
    """Display details and activity logs for a specific user order."""
    user_order = order_service.get_user_order(request.user, order_number)
    
    context = {
        "order": user_order,
        "order_activity_logs": ActivityLog.objects.select_related("actor").filter(
            target_content_type=ContentType.objects.get_for_model(Order),
            target_object_id=user_order.pk,
        )[:20],
    }
    return render(request, "order_detail.html", context)


@buyer_required
def order_cancelation(request: HttpRequest, order_number: str) -> JsonResponse:
    """Attempt to cancel an order and return the result."""
    is_canceled = order_service.cancel_user_order(request.user, order_number)
    if is_canceled:
        return JsonResponse({
            "status": "success",
            "message": "Your order has been successfully canceled.",
        })
        
    return JsonResponse({
        "status": "error",
        "message": "The order cannot be canceled at this stage.",
    }, status=400)


@buyer_required
def reorder(request: HttpRequest, order_number: str) -> JsonResponse:
    """Recreate a previous order and add its items to the cart."""
    reordered_cart = order_service.reorder_user_order(request.user, order_number)
    if reordered_cart:
        return JsonResponse({
            "status": "success",
            "message": "Order items have been successfully added to your cart.",
        })
        
    return JsonResponse({
        "status": "error",
        "message": "We encountered a problem while reordering these items.",
    }, status=400)


@buyer_required
@require_POST
def submit_review_api(request: HttpRequest) -> JsonResponse:
    """Process a user's product review submission via AJAX."""
    order_item_id = request.POST.get('order_item_id')
    rating = request.POST.get('rating')
    title = request.POST.get('title')
    description = request.POST.get('description')
    image = request.FILES.get('image')

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
        
    return JsonResponse({'status': 'error', 'message': message}, status=400)
