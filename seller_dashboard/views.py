from django.shortcuts import render
from accounts.decorators import verified_seller
from products.services import (
    create_product,
    hide_product_by_slug,
    unhide_product_by_slug,
    delete_product_by_slug,
    save_draft,
    edit_product,
    get_edit_product_by_slug,
    toggle_product_featured,
    toggle_product_archive,
    )
from orders.services import get_user_order_for_seller, get_seller_orders, update_order_status
from orders.models import Order
from django.core.paginator import Paginator
from products.models import Product
from promotions.services import get_available_promotions_for_seller
from admin_panel.settings_data import get_admin_setting
from django.contrib.contenttypes.models import ContentType
from notifications.models import ActivityLog
import json
# Create your views here.


from django.contrib import messages

def dashboard(request):
    seller = request.user.seller_profile
    context = { "seller": seller}

    return render(request, "dashboard.html", context)

def products(request):
    seller = request.user.seller_profile
    products_qs = Product.objects.filter(seller=seller).select_related(
        "category", "brand"
    ).prefetch_related("images").order_by("-created_at")
    paginator = Paginator(products_qs, 8)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(request, "products/list.html", {
        "dashboard_seller_products": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })


from django.http import JsonResponse


def add_product(request):

    if request.method == "POST":

        try:
            product = create_product(
                request.user,
                request.POST,
                request.FILES,
            )
        except ValueError as error:
            return JsonResponse({"success": False, "message": str(error)}, status=400)

        return JsonResponse(
            {
                "success": True,
                "message": "Product created successfully.",
                "product_id": product.id,
            }
        )
    return render(request, "products/create.html", {
        "available_promotions": get_available_promotions_for_seller(request.user.seller_profile),
        "selected_promotion_ids": [],
    })


def draft_product(request):

    if not get_admin_setting("catalog", "allow_seller_drafts", True):
        if request.method == "POST":
            return JsonResponse({"success": False, "message": "Seller drafts are currently disabled."}, status=403)
        return JsonResponse({"success": False, "message": "Seller drafts are currently disabled."}, status=403)

    if request.method == "POST":

        try:
            product = save_draft(
                request.user,
                request.POST,
                request.FILES,
            )
        except ValueError as error:
            return JsonResponse({"success": False, "message": str(error)}, status=400)

        return JsonResponse(
            {
                "success": True,
                "message": "Product created successfully.",
                "product_id": product.id,
            }
        )
    return render(request, "products/create.html", {
        "available_promotions": get_available_promotions_for_seller(request.user.seller_profile),
        "selected_promotion_ids": [],
    })


def edit_products(request, product_slug):

    product = get_edit_product_by_slug(product_slug, request.user.seller_profile)

    if request.method == "POST":

        try:
            product = edit_product(
                request.user.seller_profile,
                product,
                request.POST,
                request.FILES,
            )
        except ValueError as error:
            return JsonResponse({"success": False, "message": str(error)}, status=400)

        return JsonResponse(
            {
                "success": True,
                "message": "Product updated successfully.",
                "product_id": product.id,
            }
        )

    context = {
        "product": product,
        "available_promotions": get_available_promotions_for_seller(request.user.seller_profile),
        "selected_promotion_ids": list(
            product.promotion_products.values_list("promotion_id", flat=True)
        ),
    }
    selected_promotion_prices = {
        relation.promotion_id: relation.promotion_price
        for relation in product.promotion_products.all()
    }
    for promotion in context["available_promotions"]:
        promotion.selected_promotion_price = selected_promotion_prices.get(promotion.id)

    return render(
        request,
        "products/edit.html",
        context,
    )


def hide_product(request):
    try:
        data = json.loads(request.body)
        product_slug = data.get("productSlug")
        hide_product_by_slug(product_slug)
        return JsonResponse(
            {
                "status": "success",
                "message": "The product has been hidden successfully.",
            }
        )

    except Exception:
        return JsonResponse(
            {"status": "error", "message": "Something went wrong."}, status=400
        )


def unhide_product(request):
    try:
        data = json.loads(request.body)
        product_slug = data.get("productSlug")
        unhide_product_by_slug(product_slug)
        return JsonResponse(
            {
                "status": "success",
                "message": "The product has been unhidden successfully.",
            }
        )

    except Exception:
        return JsonResponse(
            {"status": "error", "message": "Something went wrong."}, status=400
        )


def delete_product(request):
    data = json.loads(request.body)
    product_slug = data.get("productSlug")
    result = delete_product_by_slug(
        product_slug,
    )
    print(result)

    if result["success"]:
        return JsonResponse(
            {
                "status": "success",
                "archived": result["archived"],
                "message": (
                    "Product deleted successfully."
                    if not result["archived"]
                    else "Product has previous orders, so it was archived instead."
                ),
            }
        )

    return JsonResponse(
        {
            "status": "error",
            "message": "Product not found.",
        },
        status=404,
    )




def toggle_product_featured_view(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid request data.",
            },
            status=400,
        )

    product_slug = data.get("productSlug")
    action = data.get("action")

    if not product_slug:
        return JsonResponse(
            {
                "status": "error",
                "message": "Product slug is required.",
            },
            status=400,
        )

    if action not in {"feature", "unfeature"}:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid featured action.",
            },
            status=400,
        )

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = toggle_product_featured(
        product_slug=product_slug,
        action=action,
    )

    if not result["success"]:
        status_code = (
            404
            if result["error"] == "not_found"
            else 400
        )

        return JsonResponse(
            {
                "status": "error",
                "message": result["message"],
            },
            status=status_code,
        )

    return JsonResponse(
        {
            "status": "success",
            "featured": result["featured"],
            "changed": result["changed"],
            "message": result["message"],
        }
    )



def toggle_product_archive_view(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid request data.",
            },
            status=400,
        )

    product_slug = data.get("productSlug")
    action = data.get("action")

    if not product_slug:
        return JsonResponse(
            {
                "status": "error",
                "message": "Product slug is required.",
            },
            status=400,
        )

    if action not in {"archive", "unarchive"}:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid archive action.",
            },
            status=400,
        )

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = toggle_product_archive(
        product_slug=product_slug,
        seller=seller,
        action=action,
    )

    if not result["success"]:
        status_code = (
            404
            if result["error"] == "not_found"
            else 400
        )

        return JsonResponse(
            {
                "status": "error",
                "message": result["message"],
            },
            status=status_code,
        )

    return JsonResponse(
        {
            "status": "success",
            "archived": result["archived"],
            "changed": result["changed"],
            "message": result["message"],
        }
    )

def orders(request):
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

def order_detail(request, order_no):
    order = get_user_order_for_seller(request.user.seller_profile, order_no)

    return render(request, "orders/detail.html", {
        "order": order,
        "order_activity_logs": ActivityLog.objects.select_related("actor").filter(
            target_content_type=ContentType.objects.get_for_model(Order),
            target_object_id=order.pk,
        )[:20],
    })


def update_user_order_status(request, order_no, status):
    update_order_status(
        request.user.seller_profile,
        order_no,
        status,
    )

    return JsonResponse({
        "success": True,
        "status": status,
    })


from accounts.services import get_seller_application_documents
def dashboard_settings(request):
    seller = request.user.seller_profile
    documents = get_seller_application_documents(seller)
    return render(request, "settings.html", {"seller": seller, "documents": documents})
