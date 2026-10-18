import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import Category
from promotions import services as promotion_services
from promotions.models import Promotion


@staff_member_required
def admin_promotions(request: HttpRequest) -> HttpResponse:
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    promotions_qs = promotion_services.get_admin_promotions_queryset(search=search_query, status=status_filter)
    summary = promotion_services.get_admin_promotion_summary()

    paginator = Paginator(promotions_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    promotion_services.annotate_promotion_display_status(page_obj.object_list)

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "promotions/promotions_list.html", {
        "promotions": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
        "summary": summary,
        "search_query": search_query,
        "status_filter": status_filter,
        "status_choices": Promotion.Status.choices,
    })

@staff_member_required
def admin_create_promotion(request: HttpRequest) -> HttpResponse:
    categories = Category.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        try:
            success, message, promotion, errors = promotion_services.create_promotion_service(
                request.POST, request.FILES,
            )
        except ValueError as exc:
            success, message, promotion, errors = False, str(exc), None, {}

        if success:
            messages.success(request, message)
            return redirect("admin-promotions")

        messages.error(request, message)
        return render(request, "promotions/promotion_create.html", {
            "categories": categories,
            "errors": errors,
            "form_data": request.POST,
            "selected_category_ids": request.POST.getlist("categories"),
        })

    return render(request, "promotions/promotion_create.html", {
        "categories": categories,
        "errors": {},
        "form_data": {},
        "selected_category_ids": [],
    })

@staff_member_required
def admin_promotion_detail(request: HttpRequest, promotion_slug: str) -> HttpResponse:
    context = promotion_services.get_admin_promotion_detail(promotion_slug)
    promotion_services.annotate_promotion_display_status([context["promotion"]])
    return render(request, "promotions/promotion_detail.html", context)

@staff_member_required
def admin_edit_promotion(request: HttpRequest, promotion_slug: str) -> HttpResponse:
    categories = Category.objects.filter(is_active=True).order_by("name")
    context = promotion_services.get_admin_promotion_detail(promotion_slug)

    if request.method == "POST":
        try:
            success, message, promotion, errors = promotion_services.update_promotion_service(
                request.POST, request.FILES, promotion_slug
            )
        except ValueError as exc:
            success, message, promotion, errors = False, str(exc), None, {}

        if success:
            messages.success(request, message)
            return redirect("admin-promotion-detail", promotion_slug=promotion.slug)

        messages.error(request, message)
        return render(request, "promotions/promotion_edit.html", {
            "categories": categories,
            "errors": errors,
            "form_data": request.POST,
            "promotion": context["promotion"],
            "selected_category_ids": request.POST.getlist("categories"),
        })

    return render(request, "promotions/promotion_edit.html", {
        "categories": categories,
        "errors": {},
        "form_data": context["promotion"].__dict__,
        "promotion": context["promotion"], 
        "selected_category_ids": [str(cat.id) for cat in context["promotion"].categories.all()],
    })

@staff_member_required
def admin_manage_promotion_products(request: HttpRequest, promotion_slug: str) -> HttpResponse:
    promotion = get_object_or_404(Promotion, slug=promotion_slug)
    promotion_services.annotate_promotion_display_status([promotion])

    search_query = request.GET.get("q", "").strip()
    seller_filter = request.GET.get("seller", "").strip()
    category_filter = request.GET.get("category", "").strip()
    featured_filter = request.GET.get("featured", "").strip()
    sort = request.GET.get("sort", "").strip()

    queryset = promotion_services.get_admin_promotion_products_queryset(
        promotion,
        search=search_query,
        seller_id=seller_filter or None,
        category_id=category_filter or None,
        featured=featured_filter or None,
        sort=sort or None,
    )

    filters = promotion_services.get_promotion_product_filters(promotion)
    summary = promotion_services.get_promotion_products_summary(promotion)

    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "promotions/manage_products.html", {
        "promotion": promotion,
        "promotion_products": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
        "summary": summary,
        "sellers": filters["sellers"],
        "categories": filters["categories"],
        "search_query": search_query,
        "seller_filter": seller_filter,
        "category_filter": category_filter,
        "featured_filter": featured_filter,
        "sort": sort,
    })

@staff_member_required
@require_POST
def update_promotion_product_price(request: HttpRequest, promotion_product_id: int) -> JsonResponse:
    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    try:
        promotion_product = promotion_services.update_promotion_product_price_service(
            promotion_product_id, data.get("promotion_price"),
        )
        return JsonResponse({
            "success": True,
            "message": "Promotion price updated successfully.",
            "promotion_price": str(promotion_product.promotion_price),
            "discount_percentage": str(promotion_product.discount_percentage),
        })
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)

@staff_member_required
@require_POST
def toggle_promotion_product_featured(request: HttpRequest, promotion_product_id: int) -> JsonResponse:
    promotion_product = promotion_services.toggle_promotion_product_featured_service(promotion_product_id)
    return JsonResponse({
        "success": True,
        "is_featured": promotion_product.is_featured,
        "message": "Product marked as featured." if promotion_product.is_featured else "Product unmarked as featured.",
    })

@staff_member_required
@require_POST
def remove_promotion_product(request: HttpRequest, promotion_product_id: int) -> JsonResponse:
    promotion_services.remove_promotion_product_service(promotion_product_id)
    return JsonResponse({"success": True, "message": "Product removed from the promotion."})