import logging
from decimal import Decimal

from allauth.account.forms import ResetPasswordForm

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts import services as account_services
from accounts.buyer_pdf import generate_buyer_profile_pdf
from admin_panel import services
from orders.models import Order

User = get_user_model()
logger = logging.getLogger(__name__)

@staff_member_required
def user_management(request: HttpRequest) -> HttpResponse:
    """Render the user management overview."""
    return render(request, "user_management/overview.html")


@staff_member_required
def user_buyers(request: HttpRequest) -> HttpResponse:
    """Render the paginated list of all registered buyers."""
    total_buyers = account_services.get_all_buyers().annotate(
        total_spent=Coalesce(
            Sum("orders__total", filter=Q(orders__payment_status=Order.PaymentStatus.PAID)),
            Decimal("0.00"),
        )
    )
    paginator = Paginator(total_buyers.order_by("-date_joined"), 8)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    
    query_params = request.GET.copy()
    query_params.pop("page", None)
    
    return render(request, "user_management/buyer/buyers.html", {
        "buyers": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })


@staff_member_required
def user_buyer(request: HttpRequest, userId: int) -> HttpResponse:
    """Render the detail view for a specific buyer."""
    context = services.get_buyer_details(userId)
    return render(request, "user_management/buyer/buyer_detail.html", context)


@staff_member_required
@require_POST
def update_buyer_profile_view(request: HttpRequest, buyer_id: int) -> JsonResponse:
    """Admin endpoint to update buyer profile information."""
    try:
        buyer = User.objects.get(pk=buyer_id)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "Buyer not found."}, status=404)

    success, message, buyer, email_changed, errors = account_services.update_buyer_profile(
        user=buyer,
        first_name=request.POST.get("first_name"),
        last_name=request.POST.get("last_name"),
        username=request.POST.get("username"),
        email=request.POST.get("email"),
        contact=request.POST.get("contact"),
        account_status=request.POST.get("account_status"),
        allow_status_change=True,
        request=request,
    )

    if not success:
        return JsonResponse({"success": False, "message": message, "errors": errors}, status=400)

    return JsonResponse({
        "success": True,
        "message": message,
        "email_changed": email_changed,
        "buyer": {
            "id": buyer.id,
            "first_name": buyer.first_name,
            "last_name": buyer.last_name,
            "username": buyer.username,
            "email": buyer.email,
            "contact": buyer.contact,
            "account_status": buyer.account_status,
        },
    })


@staff_member_required
@require_POST
def change_state(request: HttpRequest) -> JsonResponse:
    """Change the state of a user's account."""
    user_id = request.POST.get("userId")
    state = request.POST.get("state")
    account_services.change_account_state(user_id, state)
    return JsonResponse({"status": "success"})


@staff_member_required
@require_POST
def admin_reset_password(request: HttpRequest, user_id: int) -> JsonResponse:
    """Trigger a password reset email for a user."""
    buyer = get_object_or_404(User, id=user_id)
    form = ResetPasswordForm(data={"email": buyer.email})

    if form.is_valid():
        form.save(request)
        return JsonResponse({"success": True, "message": f"Password reset email sent to {buyer.email}."})

    return JsonResponse({"success": False, "error": form.errors.get_json_data()}, status=400)


@staff_member_required
@require_POST
def send_user_email(request: HttpRequest, user_id: int) -> JsonResponse:
    """Send a custom administrative email to a specific user."""
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": "User not found."}, status=404)

    subject = request.POST.get("subject", "").strip()
    message = request.POST.get("message", "").strip()
    button_text = request.POST.get("buttonText", "").strip()
    button_url = request.POST.get("buttonUrl", "").strip()

    if not subject or not message:
        return JsonResponse({"success": False, "message": "Subject and message are required."}, status=400)

    attachments = request.FILES.getlist("attachments")

    try:
        services.send_admin_email(
            user=user,
            subject=subject,
            message=message,
            button_text=button_text or None,
            button_url=button_url or None,
            attachments=attachments,
        )
        return JsonResponse({"success": True, "message": "Email sent successfully."})
    except Exception as e:
        logger.exception("Failed to send administrative email.")
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@staff_member_required
def export_buyer_profile(request: HttpRequest, user_id: int) -> HttpResponse:
    """Export a comprehensive buyer profile as a PDF."""
    prefetch_fields = [
        "order_set", "orders", "address_set", "addresses",
        "useraddress_set", "review_set", "reviews", "wishlist_set", "wishlists",
    ]
    valid_prefetches = [f for f in prefetch_fields if hasattr(User, f) or hasattr(User, f.replace("_set", ""))]
    buyer = get_object_or_404(User.objects.prefetch_related(*valid_prefetches), pk=user_id)

    pdf_buffer = generate_buyer_profile_pdf(buyer, request.user)
    date_str = timezone.now().strftime("%Y-%m-%d")
    identifier = getattr(buyer, "username", getattr(buyer, "first_name", str(buyer.id)))
    safe_name = str(identifier).replace(" ", "_").replace(".", "_").lower()
    filename = f"buyer_{safe_name}_{date_str}.pdf"

    response = HttpResponse(pdf_buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@staff_member_required
def export_order_history(request: HttpRequest, user_id: int) -> HttpResponse:
    """Export order history for a specific buyer."""
    return services.export_order_history(user_id)