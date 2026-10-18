import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from orders.models import Order
from .services import create_support_request

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# HELP CONTENT INITIALIZATION
# ---------------------------------------------------------

HELP_ARTICLES_PATH = Path(__file__).resolve().parent / "data" / "help_articles.json"


def load_help_content() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load and structure static help articles and topics from the local JSON store."""
    try:
        with HELP_ARTICLES_PATH.open(encoding="utf-8") as content_file:
            data = json.load(content_file)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.error("Help articles JSON file is missing or corrupted at %s", HELP_ARTICLES_PATH)
        return {}, {}

    articles = data.get("articles", {})
    topics = {}
    
    for slug, topic in data.get("topics", {}).items():
        topics[slug] = {
            "name": topic.get("title", slug.replace("-", " ").title()),
            "description": topic.get("description", ""),
            "articles": [
                article_slug
                for article_slug, article in articles.items()
                if article.get("topic") == slug
            ],
        }

    for article in articles.values():
        article.setdefault("category", topics.get(article.get("topic"), {}).get("name", "Help"))

    return topics, articles


# Load globals once at module initialization to prevent repetitive disk I/O
HELP_TOPICS, HELP_ARTICLES = load_help_content()


# ---------------------------------------------------------
# PUBLIC HELP CENTER VIEWS
# ---------------------------------------------------------

@require_http_methods(["GET"])
def help_and_support_view(request: HttpRequest) -> HttpResponse:
    """Render the main Help and Support portal page."""
    support_requests = []
    orders = []
    
    if request.user.is_authenticated:
        support_requests = list(
            request.user.support_requests
            .select_related("related_order")
            .prefetch_related("messages")
            .all()
        )
        orders = list(request.user.orders.all()[:20])
        
    return render(request, "help_support.html", {
        "support_requests": support_requests,
        "support_orders": orders,
    })


@require_http_methods(["GET"])
def help_topic_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Render a specific category/topic page listing its associated articles."""
    topic = HELP_TOPICS.get(slug)
    if topic is None:
        raise Http404("Help topic not found.")

    articles = [
        {"slug": article_slug, **HELP_ARTICLES[article_slug]}
        for article_slug in topic["articles"]
        if article_slug in HELP_ARTICLES
    ]
    return render(request, "help_topic_detail.html", {"topic": topic, "slug": slug, "articles": articles})


@require_http_methods(["GET"])
def help_article_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Render an individual help article."""
    article = HELP_ARTICLES.get(slug)
    if article is None:
        raise Http404("Help article not found.")

    return render(request, "help_article_detail.html", {"article": article, "slug": slug})


# ---------------------------------------------------------
# AUTHENTICATED SUPPORT REQUESTS
# ---------------------------------------------------------

@login_required
@require_POST
def create_support_request_view(request: HttpRequest) -> JsonResponse:
    """Process a multipart form submission to create a new customer support ticket."""
    request_type = request.POST.get("request_type", "").strip()
    category = request.POST.get("category", "").strip()
    subject = request.POST.get("subject", "").strip()
    message = request.POST.get("message", "").strip()
    related_order_id = request.POST.get("related_order", "").strip()
    related_product_name = request.POST.get("related_product", "").strip()
    preferred_contact_method = request.POST.get("preferred_contact_method", "email").strip()
    attachment = request.FILES.get("attachment")

    related_order = None

    if related_order_id:
        related_order = Order.objects.filter(
            order_number=related_order_id,
            user=request.user,
        ).first()

        if not related_order:
            return JsonResponse({"success": False, "message": "The selected order could not be found."}, status=400)

    try:
        support_request = create_support_request(
            user=request.user,
            request_type=request_type,
            category=category,
            subject=subject,
            message=message,
            related_order=related_order,
            related_product_name=related_product_name,
            attachment=attachment,
            preferred_contact_method=preferred_contact_method,
        )
    except ValidationError as exc:
        error_message = exc.messages[0] if hasattr(exc, "messages") else str(exc)
        return JsonResponse({"success": False, "message": error_message}, status=400)
    except Exception:
        logger.exception("Failed to create support request for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "An unexpected error occurred while submitting your request."}, status=500)

    success_message = (
        "Your message has been sent to our support team."
        if request_type == "contact"
        else "Your problem report has been submitted. Our team will review it shortly."
    )

    return JsonResponse({
        "success": True,
        "message": success_message,
        "request": {
            "id": support_request.id,
            "subject": support_request.subject,
            "status": support_request.status,
            "category": support_request.category,
            "request_type": support_request.request_type,
            "created_at": support_request.created_at.isoformat(),
        },
    }, status=201)


def _serialize_support_request(support_request: Any) -> Dict[str, Any]:
    """Helper to convert a support request model instance into a JSON-safe dictionary."""
    created_label = support_request.created_at.strftime("%b %d, %Y").replace(" 0", " ")
    updated_label = support_request.updated_at.strftime("%b %d, %Y").replace(" 0", " ")
    
    return {
        "id": support_request.id,
        "display_id": f"SR-{support_request.id:05d}",
        "subject": support_request.subject,
        "message": support_request.message,
        "status": support_request.status,
        "status_label": support_request.get_status_display(),
        "category": support_request.category,
        "category_label": support_request.get_category_display(),
        "created_label": created_label,
        "updated_label": updated_label,
    }


@login_required
@require_http_methods(["GET"])
def support_requests_view(request: HttpRequest) -> JsonResponse:
    """Retrieve a JSON list of all support requests for the authenticated user."""
    requests = request.user.support_requests.prefetch_related("messages").all()
    return JsonResponse({
        "success": True, 
        "requests": [_serialize_support_request(item) for item in requests]
    })


@login_required
@require_http_methods(["GET"])
def support_request_detail_view(request: HttpRequest, request_id: int) -> JsonResponse:
    """Retrieve JSON details for a specific support request owned by the user."""
    support_request = request.user.support_requests.filter(pk=request_id).first()
    if support_request is None:
        return JsonResponse({"success": False, "message": "Support request not found."}, status=404)
        
    return JsonResponse({
        "success": True, 
        "request": _serialize_support_request(support_request)
    })