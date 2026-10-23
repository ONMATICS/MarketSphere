from typing import Any

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.urls import NoReverseMatch, reverse
from django.utils.dateparse import parse_date

from notifications.models import ActivityLog, Notification
from notifications.services.notifications import schedule_notification
from support.models.support_models import SupportMessage, SupportRequest
from support.services import add_support_message

S = SupportRequest.Status

PAGE_SIZE = 10
MAX_RESPONSE_LENGTH = 2000

# Admin-allowed status transitions (uses the existing status values only).
ALLOWED_TRANSITIONS = {
    S.OPEN: {S.IN_PROGRESS, S.WAITING_FOR_USER, S.RESOLVED, S.CLOSED},
    S.IN_PROGRESS: {S.WAITING_FOR_USER, S.RESOLVED, S.CLOSED},
    S.WAITING_FOR_USER: {S.IN_PROGRESS, S.RESOLVED, S.CLOSED},
    S.RESOLVED: {S.OPEN, S.IN_PROGRESS, S.CLOSED},
    S.CLOSED: {S.OPEN},
}


def display_id(request_id: int) -> str:
    return f"SR-{request_id:05d}"


def available_transitions(current_status: str) -> list[tuple[str, str]]:
    labels = dict(SupportRequest.Status.choices)
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    return [(value, labels[value]) for value, _ in SupportRequest.Status.choices if value in allowed]


def _parse_request_id(term: str) -> int | None:
    cleaned = term.upper().replace("SR-", "").lstrip("#").strip()
    return int(cleaned) if cleaned.isdigit() else None


# ---------------------------------------------------------
# LIST
# ---------------------------------------------------------

def get_support_summary() -> dict[str, int]:
    return SupportRequest.objects.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status=S.OPEN)),
        in_progress=Count("id", filter=Q(status=S.IN_PROGRESS)),
        waiting=Count("id", filter=Q(status=S.WAITING_FOR_USER)),
        resolved=Count("id", filter=Q(status__in=[S.RESOLVED, S.CLOSED])),
    )


def get_support_requests_queryset(filters: dict[str, str]):
    qs = SupportRequest.objects.select_related("user", "related_order")

    search = (filters.get("q") or "").strip()
    if search:
        query = (
            Q(subject__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(related_order__order_number__icontains=search)
        )
        pk = _parse_request_id(search)
        if pk is not None:
            query |= Q(pk=pk)
        qs = qs.filter(query)

    if filters.get("status") in dict(SupportRequest.Status.choices):
        qs = qs.filter(status=filters["status"])
    if filters.get("category") in dict(SupportRequest.Category.choices):
        qs = qs.filter(category=filters["category"])
    if filters.get("request_type") in dict(SupportRequest.RequestType.choices):
        qs = qs.filter(request_type=filters["request_type"])
    if filters.get("contact_method") in dict(SupportRequest.ContactMethod.choices):
        qs = qs.filter(preferred_contact_method=filters["contact_method"])

    date_from = parse_date(filters.get("date_from") or "")
    date_to = parse_date(filters.get("date_to") or "")
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    return qs.order_by("-updated_at", "-created_at")


def get_support_list_context(params) -> dict[str, Any]:
    filters = {key: (params.get(key) or "").strip() for key in
               ("q", "status", "category", "request_type", "contact_method", "date_from", "date_to")}

    paginator = Paginator(get_support_requests_queryset(filters), PAGE_SIZE)
    page_obj = paginator.get_page(params.get("page", 1))

    query_params = params.copy()
    query_params.pop("page", None)

    return {
        "support_requests": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
        "summary": get_support_summary(),
        "filters": filters,
        "has_filters": any(filters.values()),
        "status_choices": SupportRequest.Status.choices,
        "category_choices": SupportRequest.Category.choices,
        "type_choices": SupportRequest.RequestType.choices,
        "contact_choices": SupportRequest.ContactMethod.choices,
    }


# ---------------------------------------------------------
# DETAIL
# ---------------------------------------------------------

def get_support_request_or_404(request_id: int) -> SupportRequest:
    return get_object_or_404(
        SupportRequest.objects.select_related("user", "related_order")
        .prefetch_related("messages__sender"),
        pk=request_id,
    )


def get_support_detail_context(request_id: int) -> dict[str, Any]:
    support_request = get_support_request_or_404(request_id)

    buyer_url = order_url = None
    try:
        buyer_url = reverse("user-buyer", kwargs={"userId": support_request.user_id})
        if support_request.related_order_id:
            order_url = reverse(
                "sales-order", kwargs={"order_number": support_request.related_order.order_number}
            )
    except NoReverseMatch:
        pass

    return {
        "support_request": support_request,
        "display_id": display_id(support_request.pk),
        "thread": list(support_request.messages.all()),  # prefetched, ordered by created_at
        "transitions": available_transitions(support_request.status),
        "can_reply": support_request.status != S.CLOSED,
        "buyer_url": buyer_url,
        "order_url": order_url,
        "max_response_length": MAX_RESPONSE_LENGTH,
    }


# ---------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------

def _buyer_target_url(support_request: SupportRequest) -> str:
    return f"{reverse('help-support')}?request={support_request.pk}"


def _notify_buyer(support_request, admin, *, title, message, action) -> None:
    schedule_notification(
        user_id=support_request.user_id,
        notification_type=Notification.NotificationType.SYSTEM,
        title=title,
        message=message,
        icon="bi-headset",
        target_url=_buyer_target_url(support_request),
        audience=Notification.Audience.BUYER,
        data={"support_request_id": support_request.pk, "action": action},
        activity=True,
        activity_category=ActivityLog.Category.SUPPORT,
        activity_action=action,
        activity_title=title,
        activity_description=message,
        activity_actor=admin,
        activity_actor_type=ActivityLog.ActorType.ADMIN,
        activity_target=support_request,
        activity_metadata={"support_request_id": support_request.pk},
    )


# ---------------------------------------------------------
# ACTIONS
# ---------------------------------------------------------

@transaction.atomic
def submit_admin_response(*, request_id: int, admin: Any, message: str) -> SupportMessage:
    message = (message or "").strip()
    if not message:
        raise ValidationError("Response cannot be empty.")
    if len(message) > MAX_RESPONSE_LENGTH:
        raise ValidationError(f"Response cannot exceed {MAX_RESPONSE_LENGTH} characters.")

    support_request = get_object_or_404(
        SupportRequest.objects.select_for_update().select_related("user"), pk=request_id
    )
    if support_request.status == S.CLOSED:
        raise ValidationError("This request is closed. Reopen it before responding.")

    # Reuses the existing buyer-side service: creates the SupportMessage and
    # moves the status to "waiting_for_user" for admin senders.
    support_message = add_support_message(
        support_request=support_request,
        sender=admin,
        sender_type=SupportMessage.SenderType.ADMIN,
        message=message,
    )

    _notify_buyer(
        support_request, admin,
        title="Support team replied",
        message=f"Your support request {display_id(support_request.pk)} "
                f"(\u201c{support_request.subject[:60]}\u201d) has a new response.",
        action="SUPPORT_REPLIED",
    )
    return support_message


@transaction.atomic
def change_request_status(*, request_id: int, admin: Any, new_status: str) -> SupportRequest:
    if new_status not in dict(SupportRequest.Status.choices):
        raise ValidationError("Invalid status.")

    support_request = get_object_or_404(
        SupportRequest.objects.select_for_update().select_related("user"), pk=request_id
    )

    if new_status == support_request.status:
        raise ValidationError("The request already has this status.")
    if new_status not in ALLOWED_TRANSITIONS.get(support_request.status, set()):
        raise ValidationError("That status change is not allowed from the current status.")

    previous = support_request.status
    support_request.status = new_status
    support_request.save(update_fields=["status", "updated_at"])

    # Only notify for outcomes the buyer cares about; replies already notify.
    if new_status == S.RESOLVED:
        _notify_buyer(
            support_request, admin,
            title="Support request resolved",
            message=f"Your support request {display_id(support_request.pk)} was marked as resolved.",
            action="SUPPORT_RESOLVED",
        )
    elif new_status == S.OPEN and previous in (S.RESOLVED, S.CLOSED):
        _notify_buyer(
            support_request, admin,
            title="Support request reopened",
            message=f"Your support request {display_id(support_request.pk)} was reopened.",
            action="SUPPORT_REOPENED",
        )

    return support_request