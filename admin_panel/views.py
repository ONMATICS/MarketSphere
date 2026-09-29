from django.db.models import Count, Sum, Q
from django.db.models.functions import Coalesce
from decimal import Decimal

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from accounts import services as account_services
from accounts.models import User, Address
from orders.models import Order
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError, transaction
from django.db.models import Model
from django.db.models.fields.files import FieldFile
from django.core.exceptions import ValidationError
from products.models import Brand, Category
from notifications.models import ActivityLog
import json
import csv
from django.utils.text import slugify
from django.core import serializers
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from .models import (
    AdminAuditLog,
    AdminSettingsData,
    CatalogSettings,
    CheckoutSettings,
    MarketplaceSettings,
    NotificationSettings,
    StoreSettings,
)
from decimal import Decimal, InvalidOperation
import json

# Create your views here.
def dashboard(request):
    
    return render(request, "admin_dashboard.html")


def user_management(request):
    return render(request, "user_management/overview.html")


def user_buyers(request):
    total_buyers = account_services.get_all_buyers().annotate(
        total_spent=Coalesce(
            Sum(
                "orders__total",
                filter=Q(orders__payment_status=Order.PaymentStatus.PAID),
            ),
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


def user_buyer(request, userId):
    context = services.get_buyer_details(userId)

    return render(
        request,
        "user_management/buyer/buyer_detail.html",
        context,
    )


def user_sellers(request):
    total_sellers = account_services.get_all_sellers()
    paginator = Paginator(total_sellers.order_by("-created_at"), 8)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request, "user_management/seller/seller.html", {
            "sellers": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "pagination_query": query_params,
        }
    )

def user_seller(request, sellerId):
    context = services.get_seller_detail(sellerId)
    return render(request, "user_management/seller/detail.html", context)

def catalog_products(request):
    context = services.get_products_catalog()
    paginator = Paginator(context["products"].order_by("-created_at"), 6)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    context.update({
        "products": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })
    return render(request, "catalog/products_management/products.html", context=context)


def catalog_product(request, product_slug):
    context = services.get_product_detail(product_slug)
    return render(request, "catalog/products_management/admin_product_detail.html", context=context)


def catalog_categories(request):
    context = services.get_categories_data()
    return render(request, "catalog/categories/categories.html", context=context)

from django.core.paginator import Paginator
from django.shortcuts import render

from orders import services as order_service


from django.core.paginator import Paginator
from django.shortcuts import render

from orders import services as order_service


def sales_orders(request):

    orders = order_service.get_admin_orders()

    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(
        request.GET.get("page", 1)
    )

    query_params = request.GET.copy()
    query_params.pop("page", None)

    admin_stats = order_service.get_admin_order_stats()

    return render(request, "sales/orders/order_list.html", {
        "dashboard_orders": page_obj,

        "admin": admin_stats,

        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params,
    })

def sales_order(request, order_number):
    order = Order.objects.filter(order_number=order_number).first()
    return render(request, "sales/orders/order_detail.html", {'order' : order})

def payment_management(request):
    return render(request, "sales/payments/payment_management.html")


SETTINGS_SECTION_MODELS = {
    "general": StoreSettings,
    "marketplace": MarketplaceSettings,
    "orders": CheckoutSettings,
    "catalog": CatalogSettings,
    "notifications": NotificationSettings,
}

NOTIFICATION_EVENTS = {
    "buyer": [
        ("ORDER_CREATED", "Order placed"),
        ("ORDER_CONFIRMED", "Order confirmed"),
        ("ORDER_SHIPPED", "Order shipped"),
        ("ORDER_DELIVERED", "Order delivered"),
        ("ORDER_CANCELLED", "Order cancelled"),
        ("WISHLIST_PRICE_DROP", "Wishlist price drop"),
    ],
    "seller": [
        ("ORDER_CREATED", "New order"),
        ("ORDER_CANCELLED", "Order cancelled"),
        ("LOW_STOCK", "Low stock alert"),
        ("SELLER_APPLICATION_APPROVED", "Application approved"),
        ("SELLER_APPLICATION_REJECTED", "Application rejected"),
    ],
    "admin": [
        ("SELLER_APPLICATION_APPROVED", "Seller application approved"),
        ("SELLER_APPLICATION_REJECTED", "Seller application rejected"),
        ("ORDER_CANCELLED", "Order cancelled"),
        ("SYSTEM", "System alert"),
    ],
}


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, FieldFile):
        try:
            return value.url
        except ValueError:
            return ""
    return value


def _model_values(instance):
    return {
        field.name: _json_value(getattr(instance, field.name))
        for field in instance._meta.fields
        if field.name not in {"id", "updated_at"}
    }


def _settings_payload():
    stored = AdminSettingsData.load().data or {}
    payload = dict(stored)
    for section, model_class in SETTINGS_SECTION_MODELS.items():
        values = dict(payload.get(section, {}))
        values.update(_model_values(model_class.load()))
        payload[section] = values
    return payload


def _client_ip(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")


def _post_value(value, field_name, boolean_fields):
    if field_name in boolean_fields:
        return str(value).lower() in {"1", "true", "yes", "on"}
    return value


@require_http_methods(["GET", "POST"])
def admin_settings(request):
    if request.method == "GET":
        payload = _settings_payload()
        context = {key: value for section in payload.values() for key, value in section.items()}
        store = StoreSettings.load()
        context.update({
            "marketplace_logo_url": store.marketplace_logo.url if store.marketplace_logo else "",
            "marketplace_favicon_url": store.marketplace_favicon.url if store.marketplace_favicon else "",
            "settings_payload": payload,
            "notification_buyer_events": NOTIFICATION_EVENTS["buyer"],
            "notification_seller_events": NOTIFICATION_EVENTS["seller"],
            "notification_admin_events": NOTIFICATION_EVENTS["admin"],
            "audit_log_entries": [
                {
                    "category": entry.section,
                    "admin_name": entry.admin.get_full_name() or entry.admin.username if entry.admin else "System",
                    "action": entry.action,
                    "setting_name": entry.setting_name,
                    "old_value": entry.old_value,
                    "new_value": entry.new_value,
                    "created_at": entry.timestamp,
                    "ip_address": entry.ip_address,
                }
                for entry in AdminAuditLog.objects.select_related("admin")[:100]
            ],
            "activity_logs": ActivityLog.objects.select_related("actor")[:100],
            "user_activity_logs": ActivityLog.objects.select_related("actor")[:100],
        })
        return render(request, "admin_settings.html", context)

    section = request.POST.get("__section", "").strip()
    if not section:
        return JsonResponse({"ok": False, "error": "A settings section is required."}, status=400)

    try:
        boolean_fields = set(json.loads(request.POST.get("__boolean_fields", "[]")))
    except (TypeError, ValueError):
        boolean_fields = set()

    values = {
        key: _post_value(value, key, boolean_fields)
        for key, value in request.POST.items()
        if not key.startswith("__")
    }
    for key, uploaded in request.FILES.items():
        # Browsers submit an empty UploadedFile for an untouched file input.
        # It must not overwrite an existing StoreSettings image.
        if uploaded and getattr(uploaded, "name", ""):
            values[key] = uploaded

    with transaction.atomic():
        settings_data = AdminSettingsData.load()
        all_data = dict(settings_data.data or {})
        section_data = dict(all_data.get(section, {}))
        model_class = SETTINGS_SECTION_MODELS.get(section)
        model_instance = model_class.load() if model_class else None

        if model_instance:
            model_field_names = {field.name for field in model_instance._meta.fields}
            for key, raw_value in values.items():
                if key not in model_field_names or key in {"id", "updated_at"}:
                    continue
                field = model_instance._meta.get_field(key)
                try:
                    if key in request.FILES:
                        converted = raw_value
                    elif field.get_internal_type() == "BooleanField":
                        converted = bool(raw_value)
                    elif field.get_internal_type() in {"IntegerField", "PositiveIntegerField", "PositiveSmallIntegerField"}:
                        converted = int(raw_value or 0)
                    elif field.get_internal_type() == "DecimalField":
                        converted = Decimal(raw_value or 0)
                    elif field.get_internal_type() == "JSONField":
                        converted = json.loads(raw_value or "{}")
                    else:
                        converted = raw_value
                    old_value = getattr(model_instance, key)
                    if old_value != converted:
                        services.log_audit_event(
                            admin=request.user if request.user.is_authenticated else None,
                            action="Updated",
                            section=section,
                            setting_name=key,
                            old_value=str(_json_value(old_value)),
                            new_value=str(_json_value(converted)),
                            ip_address=_client_ip(request),
                        )
                    setattr(model_instance, key, converted)
                except (ValueError, InvalidOperation, TypeError):
                    return JsonResponse({"ok": False, "error": f"Invalid value for {key}."}, status=400)
            model_instance.save()

        for key, value in values.items():
            if key in request.FILES:
                section_data[key] = _json_value(getattr(model_instance, key)) if model_instance and hasattr(model_instance, key) else ""
            else:
                section_data[key] = _json_value(value)
        all_data[section] = section_data
        settings_data.data = all_data
        settings_data.save()

        services.invalidate_platform_settings_cache()

    return JsonResponse({"ok": True, "section": section, "settings": _settings_payload().get(section, {})})

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from . import services


@require_http_methods(["GET"])
def export_categories_api(request):
    export_format = request.GET.get(
        "format",
        "CSV",
    )

    category_ids = request.GET.getlist(
        "category_id"
    )

    try:
        response = services.export_categories(
            export_format=export_format,
            category_ids=category_ids or None,
        )

        return response

    except ValueError as exc:
        return JsonResponse(
            {
                "ok": False,
                "error": str(exc),
            },
            status=400,
        )

    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "error": "Unable to export categories.",
            },
            status=500,
        )

def _category_api_error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)

@require_http_methods(["GET", "POST"])
def category_api(request):

    if request.method == "GET":
        return JsonResponse({
            "ok": True,
            **services.get_categories_api_data(),
        })

    data = request.POST
    image = request.FILES.get("image")

    name = str(data.get("name") or "").strip()
    slug = str(data.get("slug") or "").strip()

    if not name or not slug:
        return _category_api_error("Name and slug are required.")

    parent = None
    parent_id = data.get("parent_id")

    if parent_id not in (None, ""):
        try:
            parent = Category.objects.filter(pk=parent_id).first()
        except (TypeError, ValueError):
            parent = None

        if not parent:
            return _category_api_error("Parent category was not found.")

    is_active = str(
        data.get("is_active", "true")
    ).lower() == "true"

    try:
        with transaction.atomic():
            if request.method == "POST":
                category = Category(
                    name=name,
                    slug=slug,
                    parent=parent,

                    description=str(
                        data.get("description") or ""
                    ).strip(),
                    icon=str(
                        data.get("icon") or ""
                    ).strip(),
                    is_active=is_active,
                )
                category.full_clean()
                category.save()
                if image:
                    result = services.store_catalog_image(
                        image, "categories", str(category.id), "image"
                    )
                    category.image = result.get("secure_url") or result.get("url")
                    category.save(update_fields=["image"])
            else:
                category_id = request.resolver_match.kwargs.get(
                    "category_id"
                )

                if not category_id:
                    return _category_api_error(
                        "Category ID is required for update."
                    )

                category = Category.objects.filter(
                    pk=category_id
                ).first()

                if not category:
                    return _category_api_error(
                        "Category was not found.",
                        status=404,
                    )

                if parent and parent.id == category.id:
                    return _category_api_error(
                        "A category cannot be its own parent."
                    )

                category.name = name
                category.slug = slug
                category.parent = parent
                category.description = str(
                    data.get("description") or ""
                ).strip()
                category.icon = str(
                    data.get("icon") or ""
                ).strip()
                category.is_active = is_active

                category.full_clean()
                category.save()
                if image:
                    result = services.store_catalog_image(
                        image, "categories", str(category.id), "image"
                    )
                    category.image = result.get("secure_url") or result.get("url")
                    category.save(update_fields=["image"])

    except IntegrityError:
        return _category_api_error(
            "A category with this name or slug already exists."
        )
    except ValidationError:
        return _category_api_error(
            "Category data or image is invalid. Please check the submitted fields."
        )
    except ValueError as error:
        return _category_api_error(str(error))

    return JsonResponse({
        "ok": True,
        "id": category.id,
    })

@require_http_methods(["POST", "PATCH", "PUT", "DELETE"])
def category_api_detail(request, category_id):
    category = Category.objects.filter(pk=category_id).first()

    if not category:
        return _category_api_error("Category was not found.", status=404)

    if request.method == "DELETE":
        if category.products.exists():
            return _category_api_error(
                "Categories with products cannot be deleted."
            )
        if category.children.exists():
            return _category_api_error(
                "Categories with subcategories cannot be deleted."
            )

        category.delete()
        return JsonResponse({"ok": True})

    content_type = request.content_type or ""

    if content_type.startswith("multipart/form-data"):
        data = request.POST
        image = request.FILES.get("image")
    else:
        try:
            data = json.loads(request.body or "{}")
        except (TypeError, ValueError):
            return _category_api_error("Invalid JSON request body.")

        image = None

    if "name" in data:
        name = str(data.get("name") or "").strip()

        if not name:
            return _category_api_error("Name cannot be empty.")

        category.name = name

    if "slug" in data:
        slug = str(data.get("slug") or "").strip()

        if not slug:
            return _category_api_error("Slug cannot be empty.")

        category.slug = slug

    if "description" in data:
        category.description = str(
            data.get("description") or ""
        ).strip()

    if "icon" in data:
        category.icon = str(
            data.get("icon") or ""
        ).strip()

    if "is_active" in data:
        category.is_active = str(
            data.get("is_active")
        ).lower() == "true"

    if "parent_id" in data:
        parent_id = data.get("parent_id")

        if parent_id in (None, ""):
            category.parent = None
        else:
            if str(parent_id) == str(category.id):
                return _category_api_error(
                    "A category cannot be its own parent."
                )

            parent = Category.objects.filter(pk=parent_id).first()

            if not parent:
                return _category_api_error(
                    "Parent category was not found."
                )

            descendant_ids = set()
            pending_parent_ids = [category.id]
            while pending_parent_ids:
                child_ids = list(Category.objects.filter(
                    parent_id__in=pending_parent_ids
                ).values_list("id", flat=True))
                descendant_ids.update(child_ids)
                pending_parent_ids = child_ids

            if parent.id in descendant_ids:
                return _category_api_error(
                    "A category cannot be moved below its descendant."
                )

            category.parent = parent

    try:
        category.full_clean()
        category.save()

        if image:
            result = services.store_catalog_image(
                image, "categories", str(category.id), "image"
            )
            category.image = result.get("secure_url") or result.get("url")
            category.save(update_fields=["image"])

    except IntegrityError:
        return _category_api_error(
            "A category with this name or slug already exists."
        )
    except ValidationError:
        return _category_api_error(
            "Category data or image is invalid. Please check the submitted fields."
        )
    except ValueError as error:
        return _category_api_error(str(error))

    return JsonResponse({
        "ok": True,
        "id": category.id,
    })

def catalog_brands(request):
    context = services.get_brands_data()
    return render(request, "catalog/brands/brands.html", context)


def _brand_api_error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


@require_http_methods(["GET", "POST"])
def brand_api(request):
    if request.method == "GET":
        return JsonResponse({"ok": True, **services.get_brands_api_data()})
    try:
        brand = services.save_brand(request.POST, request.FILES)
        return JsonResponse({"ok": True, "brand": services.brand_payload(brand)})
    except (ValidationError, IntegrityError, ValueError) as exc:
        return _brand_api_error(str(exc) or "Invalid brand data.")


@require_http_methods(["GET", "POST", "PATCH", "PUT", "DELETE"])
def brand_api_detail(request, brand_id):
    brand = Brand.objects.filter(pk=brand_id).first()
    if not brand:
        return _brand_api_error("Brand was not found.", 404)
    if request.method == "GET":
        return JsonResponse({"ok": True, "brand": services.brand_detail_payload(brand)})
    if request.method == "DELETE":
        try:
            services.delete_brand(brand, request.GET.get("remove_products") == "true")
            return JsonResponse({"ok": True})
        except ValidationError as exc:
            return _brand_api_error(str(exc))

    data = request.POST
    if not data and request.body:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except (TypeError, ValueError, UnicodeDecodeError):
            return _brand_api_error("Invalid JSON request body.")
    action = data.get("action") if data else None
    if action:
        if action == "toggle_active":
            brand.is_active = not brand.is_active
        elif action == "toggle_featured":
            brand.is_featured = not brand.is_featured
        elif action == "activate":
            brand.is_active = True
        elif action == "deactivate":
            brand.is_active = False
        elif action == "feature":
            brand.is_featured = True
        elif action == "unfeature":
            brand.is_featured = False
        else:
            return _brand_api_error("This brand action is not supported by the current data model.")
        brand.save(update_fields=["is_active", "is_featured", "updated_at"])
        return JsonResponse({"ok": True, "brand": services.brand_payload(brand)})
    try:
        brand = services.save_brand(data, request.FILES, brand)
        return JsonResponse({"ok": True, "brand": services.brand_payload(brand)})
    except (ValidationError, IntegrityError, ValueError) as exc:
        return _brand_api_error(str(exc) or "Invalid brand data.")


@require_http_methods(["POST"])
def brand_import_api(request):
    upload = request.FILES.get("file")
    if not upload:
        return _brand_api_error("Choose a CSV or JSON file to import.")
    if upload.size > 5 * 1024 * 1024:
        return _brand_api_error("Import files must be smaller than 5MB.")
    try:
        count = services.import_brands(upload)
        return JsonResponse({"ok": True, "imported": count})
    except (ValidationError, IntegrityError, ValueError, json.JSONDecodeError) as exc:
        return _brand_api_error(str(exc) or "Unable to import brands.")


@require_http_methods(["GET"])
def brand_export_api(request):
    brands = Brand.objects.all()
    ids = request.GET.getlist("id")
    if ids:
        brands = brands.filter(id__in=ids)
    rows = [services.brand_payload(brand) for brand in brands]
    export_format = request.GET.get("format", "json").lower()
    if export_format == "json":
        return JsonResponse({"brands": rows})
    if export_format != "csv":
        return _brand_api_error("Only CSV and JSON exports are supported.")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="brands.csv"'
    writer = csv.DictWriter(response, fieldnames=["id", "name", "slug", "country_of_origin", "website", "is_active", "is_featured"])
    writer.writeheader()
    writer.writerows({key: row.get(key, "") for key in writer.fieldnames} for row in rows)
    return response

def seller_application(request, sellerId):
    context = services.get_pending_seller(sellerId)
    return render(request, "user_management/seller/application.html", context)

def change_state(request):
    if request.method == "POST":
        user_id = request.POST.get("userId")
        state = request.POST.get("state")
        print(user_id, state)
        account_services.change_account_state(user_id, state)
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "invalid request"})





import json
def reject_seller_application(request, application_id):
    print("hi")
    try:
        payload = json.loads(request.body)

        account_services.reject_seller_application_service(
            application_id=application_id,
            reason=payload.get("reason"),
            notes=payload.get("notes"),
        )

        return JsonResponse({
            "success": True,
            "message": "Application rejected successfully.",
        })

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )


from django.views.decorators.http import require_POST


@require_POST
def request_application_changes(request, application_id):

    try:
        payload = json.loads(request.body)

        account_services.request_application_changes_service(
            application_id=application_id,
            requested_changes=payload.get("requested_changes", []),
            notes=payload.get("notes", ""),
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Change request sent successfully.",
            }
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )

from django.http import JsonResponse
from django.views.decorators.http import require_POST


@require_POST
def approve_seller_application(request, application_id):

    try:

        account_services.approve_seller_application_service(
            application_id=application_id,
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Seller application approved successfully.",
            }
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )

from django.http import JsonResponse
from django.views.decorators.http import require_POST


@require_POST
def delete_seller_application(request, seller_id):
    try:

        account_services.delete_seller_account_service(seller_id)

        return JsonResponse(
            {
                "success": True,
                "message": "Seller account deleted successfully.",
            }
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )

import json

from django.http import JsonResponse


def flag_seller_document(request, document_id):

    try:

        payload = json.loads(request.body)

        account_services.flag_seller_document_service(
            document_id=document_id,
            issue=payload.get("issue"),
            note=payload.get("note"),
        )

        return JsonResponse({
            "success": True,
            "message": "Document has been flagged successfully.",
        })

    except Exception as exc:

        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )

import json
from django.http import JsonResponse


def verify_seller_document(request, document_id):
    try:
        payload = json.loads(request.body)

        account_services.verify_seller_document_service(
            document_id=document_id,
            document_type=payload.get("document_type"),
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Document verified successfully.",
            }
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )


import json
from django.http import JsonResponse


def request_missing_document(request):
    try:
        payload = json.loads(request.body)
        print(payload)

        account_services.request_missing_document_service(
            application_id=payload.get("application_id"),
            document_type=payload.get("document_type"),
            reason=payload.get("reason"),
            note=payload.get("note"),
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Document request sent successfully.",
            }
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )


from django.views.decorators.http import require_POST


@require_POST
def save_application_notes(request):

    try:

        payload = json.loads(request.body)

        account_services.save_application_notes_service(
            application_id=payload.get("application_id"),
            notes=payload.get("notes", ""),
        )

        return JsonResponse({
            "success": True,
            "message": "Notes saved successfully.",
        })

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e),
            },
            status=400,
        )
    
from django.contrib.admin.views.decorators import staff_member_required
from . import services


def export_order_history(request, user_id):
    return services.export_order_history(user_id)

from accounts.models import Seller
@staff_member_required
def export_seller_orders(request, seller_id):
    seller = get_object_or_404(Seller, id=seller_id)
    return services.export_seller_orders(seller)

from .revenue_report import export_revenue_report
# @staff_member_required
def export_revenue_report_view(request, seller_id):
    """
    Admin-only endpoint to export a seller's complete revenue report as a PDF.
    """
    seller = get_object_or_404(Seller, pk=seller_id)
    
    # The service function handles calculations, PDF building, and the HTTP Response
    return export_revenue_report(seller)

from django.contrib.sessions.models import Session
def logout_all_devices(request):

    user_id = request.POST.get("userId")

    deleted = 0

    for session in Session.objects.all():
        data = session.get_decoded()

        if data.get("_auth_user_id") == str(user_id):
            session.delete()
            deleted += 1

    return JsonResponse(
        {"status": "success", "message": f"Logged out from {deleted} active device(s)."}
    )


from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model

# Adjust the import path based on where you save the service file
from accounts.buyer_pdf import generate_buyer_profile_pdf

User = get_user_model()


def export_buyer_profile(request, user_id):
    """
    Exports a comprehensive buyer profile as a professionally formatted PDF.
    Restricted to staff/admin users.
    """
    # Using prefetch_related for common relational names to prevent N+1 queries.
    # The service will dynamically check these relationships gracefully.
    prefetch_fields = [
        "order_set",
        "orders",
        "address_set",
        "addresses",
        "useraddress_set",
        "review_set",
        "reviews",
        "wishlist_set",
        "wishlists",
    ]

    # Filter valid relationships that actually exist on the User model
    valid_prefetches = [
        f
        for f in prefetch_fields
        if hasattr(User, f) or hasattr(User, f.replace("_set", ""))
    ]

    buyer = get_object_or_404(
        User.objects.prefetch_related(*valid_prefetches), pk=user_id
    )

    # Delegate PDF generation to the dedicated service
    pdf_buffer = generate_buyer_profile_pdf(buyer, request.user)

    # Construct filename based on requirement: buyer_john_doe_YYYY-MM-DD.pdf
    date_str = timezone.now().strftime("%Y-%m-%d")
    identifier = getattr(buyer, "username", getattr(buyer, "first_name", str(buyer.id)))
    safe_name = str(identifier).replace(" ", "_").replace(".", "_").lower()
    filename = f"buyer_{safe_name}_{date_str}.pdf"

    # Return the binary buffer as an HTTP download response
    response = HttpResponse(pdf_buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'

    return response


from accounts.seller_pdf import export_seller_profile_snapshot
# =============================================================
# DJANGO VIEW
# =============================================================
# @staff_member_required
def export_seller_profile(request, seller_id):
    """
    Admin-only endpoint to export a seller's complete profile snapshot as a PDF.
    """
    # Assuming Seller model is imported at the top. 
    # Use apps.get_model as a robust fallback for generic code execution.
    from django.apps import apps
    Seller = apps.get_model('accounts', 'Seller')
    
    seller = get_object_or_404(
        Seller.objects.select_related(
            "user",
            "profile",
            "settings",
        ),
        pk=seller_id,
    )
    
    return export_seller_profile_snapshot(seller)
@require_POST
def update_buyer_profile_view(request, buyer_id):
    try:
        buyer = User.objects.get(pk=buyer_id)
    except User.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "message": "Buyer not found.",
            },
            status=404,
        )

    success, message, buyer, email_changed, errors = (
        account_services.update_buyer_profile(
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
    )

    if not success:
        return JsonResponse(
            {
                "success": False,
                "message": message,
                "errors": errors,
            },
            status=400,
        )

    return JsonResponse(
        {
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
        }
    )


from django.contrib.admin.views.decorators import staff_member_required

from allauth.account.forms import ResetPasswordForm
from django.contrib.auth import get_user_model

User = get_user_model()


@staff_member_required
@require_POST
def admin_reset_password(request, user_id):
    buyer = get_object_or_404(User, id=user_id)

    form = ResetPasswordForm(
        data={
            "email": buyer.email,
        }
    )

    if form.is_valid():
        form.save(request)

        return JsonResponse(
            {"success": True, "message": f"Password reset email sent to {buyer.email}."}
        )

    return JsonResponse(
        {"success": False, "error": form.errors.get_json_data()}, status=400
    )


def send_user_email(request, user_id):
    try:
        user = User.objects.get(pk=user_id)

    except User.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "message": "Buyer not found.",
            },
            status=404,
        )

    subject = request.POST.get("subject", "").strip()
    message = request.POST.get("message", "").strip()
    button_text = request.POST.get("buttonText", "").strip()
    button_url = request.POST.get("buttonUrl", "").strip()

    if not subject:
        return JsonResponse(
            {
                "success": False,
                "message": "Subject is required.",
            },
            status=400,
        )

    if not message:
        return JsonResponse(
            {
                "success": False,
                "message": "Message is required.",
            },
            status=400,
        )

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

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e),
            },
            status=500,
        )

    return JsonResponse(
        {
            "success": True,
            "message": "Email sent successfully.",
        }
    )

from products import services as product_services
from products.models import Product

@staff_member_required
@require_POST
def approve_product_view(request, product_slug):

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )

    notify_seller = data.get("notify_seller", False)
    publish_immediately = data.get("publish_immediately", False)

    if not product_slug:
        return JsonResponse(
            {
                "success": False,
                "message": "Product slug is required.",
            },
            status=400,
        )

    try:
        product = product_services.approve_product(
            product_slug=product_slug,
            publish_immediately=publish_immediately,
        )
    except Product.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "message": "Product not found.",
            },
            status=404,
        )

    if not product:
        return JsonResponse(
            {
                "success": False,
                "message": "Unable to approve product.",
            },
            status=400,
        )

    # TODO:
    # notify_seller will be handled here later.

    return JsonResponse(
        {
            "success": True,
            "message": (
                "Product approved and published successfully."
                if publish_immediately
                else "Product approved successfully."
            ),
            "product": {
                "slug": product.slug,
                "is_approved": product.is_approved,
                "status": product.status,
                "status_display": product.get_status_display(),
            },
        }
    )

@require_POST
def hide_product_view(request, product_slug):

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )

    reason = data.get("reason", "")
    notify_seller = data.get("notify_seller", False)

    if not product_slug:
        return JsonResponse(
            {
                "success": False,
                "message": "Product slug is required.",
            },
            status=400,
        )

    try:
        product = product_services.hide_product_by_slug(product_slug, reason)
    except Product.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "message": "Product not found.",
            },
            status=404,
        )

    # TODO:
    # reason will be stored in moderation/history later.
    #
    # TODO:
    # notify_seller will be handled later.

    return JsonResponse(
        {
            "success": True,
            "message": "Product hidden from storefront.",
        }
    )

@staff_member_required
@require_POST
def unhide_product_view(request, product_slug):

    try:
        product_services.unhide_product_by_slug(product_slug)

    except Product.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "message": "Product not found.",
            },
            status=404,
        )

    return JsonResponse(
        {
            "success": True,
            "message": "Product unhidden successfully.",
        }
    )

@require_POST
def reject_product_view(request, product_slug):

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )

    reason = data.get("reason", "")
    admin_note = data.get("admin_note", "")
    allow_resubmit = data.get("allow_resubmit", False)

    if not reason:
        return JsonResponse(
            {
                "success": False,
                "message": "Rejection reason is required.",
            },
            status=400,
        )

    try:
        product = product_services.reject_product(
            product_slug=product_slug,
            admin_note=admin_note,
        )

    except Product.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "message": "Product not found.",
            },
            status=404,
        )

    # TODO:
    # Email the seller using `admin_note` and `reason`
    # when the email/notification system is integrated.

    # TODO:
    # Store/use `allow_resubmit` when the resubmission
    # workflow is implemented.

    return JsonResponse(
        {
            "success": True,
            "message": "Product rejected successfully.",
            "product": {
                "slug": product.slug,
                "is_approved": product.is_approved,
                "admin_note": product.admin_notes,
            },
        }
    )

@require_POST
def admin_toggle_product_featured_view(request, product_slug):

    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )

    action = data.get("action")

    if action not in {"feature", "unfeature"}:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid featured action.",
            },
            status=400,
        )

    result = product_services.toggle_product_featured(
        product_slug=product_slug,
        action=action,
    )

    if not result["success"]:
        status_code = (
            404
            if result.get("error") == "not_found"
            else 400
        )

        return JsonResponse(
            {
                "success": False,
                "message": result["message"],
            },
            status=status_code,
        )

    return JsonResponse(
        {
            "success": True,
            "featured": result["featured"],
            "changed": result["changed"],
            "message": result["message"],
        }
    )

def publish_product_view(request, product_slug):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    try:
        data = json.loads(request.body or "{}")

    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )

    publish_immediately = data.get(
        "publish_immediately",
        True,
    )

    feature_homepage = data.get(
        "feature_homepage",
        False,
    )

    if not publish_immediately:
        return JsonResponse(
            {
                "success": False,
                "message": "Product must be published immediately.",
            },
            status=400,
        )

    result = product_services.publish_product(
        product_slug=product_slug,
        feature_homepage=feature_homepage,
    )

    if not result["success"]:
        return JsonResponse(
            {
                "success": False,
                "message": result["message"],
            },
            status=404,
        )

    return JsonResponse(result)

def upload_product_image_view(request, product_slug):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    image_file = request.FILES.get("image")

    if not image_file:
        return JsonResponse(
            {
                "success": False,
                "message": "Image is required.",
            },
            status=400,
        )

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = product_services.upload_product_image(
        product_slug=product_slug,
        image_file=image_file,
        seller=seller,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=404,
        )

    return JsonResponse(result)

def delete_product_image_view(request, product_slug, image_id):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = product_services.delete_product_image(
        product_slug=product_slug,
        image_id=image_id,
        seller=seller,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=404,
        )

    return JsonResponse(result)

def reorder_product_images_view(request, product_slug):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )

    image_ids = data.get("image_ids")

    if not isinstance(image_ids, list) or not image_ids:
        return JsonResponse(
            {
                "success": False,
                "message": "Image order is required.",
            },
            status=400,
        )

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = product_services.reorder_product_images(
        product_slug=product_slug,
        image_ids=image_ids,
        seller=seller,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=400,
        )

    return JsonResponse(result)

def set_primary_product_image_view(request, product_slug, image_id):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    try:
        seller = request.user.seller_profile
    except AttributeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = product_services.set_primary_product_image(
        product_slug=product_slug,
        image_id=image_id,
        seller=seller,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=404,
        )

    return JsonResponse(result)


import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.views.decorators.http import require_POST


@require_POST
def update_product_pricing_view(request, product_slug):

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )

    price_value = data.get("price")
    discount_value = data.get("discount_price")

    if price_value in (None, ""):
        return JsonResponse(
            {
                "success": False,
                "message": "Price is required.",
            },
            status=400,
        )

    try:
        price = Decimal(str(price_value))

    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid price.",
            },
            status=400,
        )

    if price < 0:
        return JsonResponse(
            {
                "success": False,
                "message": "Price cannot be negative.",
            },
            status=400,
        )

    discount_price = None

    if discount_value not in (None, ""):

        try:
            discount_price = Decimal(
                str(discount_value)
            )

        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid discount price.",
                },
                status=400,
            )

        if discount_price < 0:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Discount price cannot be negative.",
                },
                status=400,
            )

        if discount_price >= price:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Discount price must be lower than the current price.",
                },
                status=400,
            )

    try:
        seller = request.user.seller_profile

    except AttributeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = product_services.update_product_pricing(
        product_slug=product_slug,
        seller=seller,
        price=price,
        discount_price=discount_price,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=404,
        )

    return JsonResponse(result)


def remove_product_discount_view(request, product_slug):

    result = product_services.remove_product_discount(
        product_slug=product_slug,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=404,
        )

    return JsonResponse(result)

@require_POST
def adjust_product_stock_view(request, product_slug):

    try:
        data = json.loads(request.body)

    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )

    adjustment_type = data.get(
        "adjustment_type"
    )

    quantity = data.get(
        "quantity"
    )

    reason = data.get(
        "reason",
        ""
    )

    note = data.get(
        "note",
        ""
    )

    if adjustment_type not in {
        "increase",
        "decrease",
        "set",
    }:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid adjustment type.",
            },
            status=400,
        )

    try:
        quantity = int(quantity)

    except (TypeError, ValueError):
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid quantity.",
            },
            status=400,
        )

    if quantity < 0:
        return JsonResponse(
            {
                "success": False,
                "message": "Quantity cannot be negative.",
            },
            status=400,
        )

    try:
        seller = request.user.seller_profile

    except AttributeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = product_services.adjust_product_stock(
        product_slug=product_slug,
        seller=seller,
        adjustment_type=adjustment_type,
        quantity=quantity,
        reason=reason,
        note=note,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=400,
        )

    return JsonResponse(result)


@require_POST
def mark_product_out_of_stock_view(
    request,
    product_slug,
):
    try:
        seller = request.user.seller_profile

    except AttributeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = product_services.mark_product_out_of_stock(
        product_slug=product_slug,
        seller=seller,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=404,
        )

    return JsonResponse(result)

@require_POST
def restore_product_stock_view(
    request,
    product_slug,
):
    try:
        seller = request.user.seller_profile

    except AttributeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller profile not found.",
            },
            status=403,
        )

    result = product_services.restore_product_stock(
        product_slug=product_slug,
        seller=seller,
    )

    if not result["success"]:
        return JsonResponse(
            result,
            status=400,
        )

    return JsonResponse(result)

import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from products.models import Product, Category, Brand
from . import services


@require_POST
def edit_product_view(request, product_slug):

    try:
        product = Product.objects.select_related(
            "seller",
            "category",
            "brand",
        ).get(
            slug=product_slug
        )

    except Product.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Product not found.",
            },
            status=404,
        )


    try:
        data = json.loads(request.body)

    except (json.JSONDecodeError, TypeError):

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request data.",
            },
            status=400,
        )



    category = None

    category_id = data.get("category_id")

    if category_id:

        category = Category.objects.filter(
            id=category_id
        ).first()

        if not category:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Selected category not found.",
                },
                status=400,
            )



    brand = None

    brand_id = data.get("brand_id")

    if brand_id:

        brand = Brand.objects.filter(
            id=brand_id
        ).first()

        if not brand:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Selected brand not found.",
                },
                status=400,
            )
    post_data = {

        "name": data.get(
            "name",
            product.name
        ).strip(),

        "slug": data.get(
            "slug",
            product.slug
        ).strip(),

        "short_description": data.get(
            "short_description",
            product.short_description or ""
        ),

        "description": data.get(
            "description",
            product.description or ""
        ),

        "sku": data.get(
            "sku",
            product.sku or ""
        ),

        "barcode": data.get(
            "barcode",
            product.barcode or ""
        ),



        "category": (
            category.slug
            if category
            else ""
        ),

        "brand": (
            brand.slug
            if brand
            else ""
        ),



        "price": product.price,

        "discount_price": product.discount_price,

        "stock_quantity": product.stock_quantity,

        "min_stock_level": product.min_stock_level,

        "weight": product.weight,

        "is_featured": (
            "true"
            if product.is_featured
            else "false"
        ),

        "visibility": product.status,



        "tags": json.dumps([]),

        "collections": json.dumps([]),

        "dimensions": json.dumps({}),

        "deleted_images": json.dumps([]),
    }


    try:

        updated_product = product_services.edit_product(
            seller=product.seller,
            product=product,
            post_data=post_data,
            files=request.FILES,
        )

    except Exception as exc:

        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status=400,
        )


    return JsonResponse(
        {
            "success": True,

            "message":
                "Product information updated successfully.",

            "product": {
                "id": updated_product.id,
                "name": updated_product.name,
                "slug": updated_product.slug,
            },
        }
    )

from promotions.models import Promotion
from promotions import services as promotion_services


def admin_promotions(request):
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    promotions_qs = promotion_services.get_admin_promotions_queryset(
        search=search_query,
        status=status_filter,
    )

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

def admin_create_promotion(request):
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


def admin_promotion_detail(request, promotion_slug):
    context = promotion_services.get_admin_promotion_detail(promotion_slug)
    promotion_services.annotate_promotion_display_status([context["promotion"]])
    return render(request, "promotions/promotion_detail.html", context)

def admin_edit_promotion(request, promotion_slug):
    categories = Category.objects.filter(is_active=True).order_by("name")
    context = promotion_services.get_admin_promotion_detail(promotion_slug)

    if request.method == "POST":
        try:
            success, message, promotion, errors = promotion_services.update_promotion_service(
                request.POST, request.FILES, promotion_slug
            )
        except ValueError as exc:
            success, message, promotion, errors = False, str(exc), {}

        if success:
            messages.success(request, message)
            return redirect("admin-promotion-detail", promotion_slug=promotion.slug)

        # ON FAILURE: Do not redirect. Re-render the form with the errors and the user's input.
        messages.error(request, message)
        return render(request, "promotions/promotion_edit.html", {
            "categories": categories,
            "errors": errors,                             # Pass the validation errors
            "form_data": request.POST,                    # Keep what the user just typed
            "promotion": context["promotion"],            # Keep the DB object for image URLs
            "selected_category_ids": request.POST.getlist("categories"), # Keep selected checkboxes
        })

    # ON GET (Initial page load):
    return render(request, "promotions/promotion_edit.html", {
        "categories": categories,
        "errors": {},
        "form_data": context["promotion"].__dict__,
        "promotion": context["promotion"], 
        "selected_category_ids": [str(cat.id) for cat in context["promotion"].categories.all()],
    })

from promotions.models import PromotionProduct


def admin_manage_promotion_products(request, promotion_slug):
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


@require_POST
def update_promotion_product_price(request, promotion_product_id):
    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    try:
        promotion_product = promotion_services.update_promotion_product_price_service(
            promotion_product_id, data.get("promotion_price"),
        )
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)

    return JsonResponse({
        "success": True,
        "message": "Promotion price updated successfully.",
        "promotion_price": str(promotion_product.promotion_price),
        "discount_percentage": str(promotion_product.discount_percentage),
    })


@require_POST
def toggle_promotion_product_featured(request, promotion_product_id):
    promotion_product = promotion_services.toggle_promotion_product_featured_service(
        promotion_product_id,
    )
    return JsonResponse({
        "success": True,
        "is_featured": promotion_product.is_featured,
        "message": (
            "Product marked as featured."
            if promotion_product.is_featured
            else "Product unmarked as featured."
        ),
    })


@require_POST
def remove_promotion_product(request, promotion_product_id):
    promotion_services.remove_promotion_product_service(promotion_product_id)
    return JsonResponse({
        "success": True,
        "message": "Product removed from the promotion.",
    })
