import csv
import json
import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from admin_panel import services
from products.models import Brand, Category
from services.decorators.decorators import catalog_admin_required

logger = logging.getLogger(__name__)

@catalog_admin_required
def catalog_categories(request: HttpRequest) -> HttpResponse:
    """Render the category management page."""
    context = services.get_categories_data()
    return render(request, "catalog/categories/categories.html", context=context)

@catalog_admin_required
@require_http_methods(["GET"])
def export_categories_api(request: HttpRequest) -> JsonResponse:
    export_format = request.GET.get("format", "CSV")
    category_ids = request.GET.getlist("category_id")

    try:
        return services.export_categories(export_format=export_format, category_ids=category_ids or None)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception:
        logger.exception("Unable to export categories.")
        return JsonResponse({"ok": False, "error": "Unable to export categories."}, status=500)

def _category_api_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)

@catalog_admin_required
@require_http_methods(["GET", "POST"])
def category_api(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse({"ok": True, **services.get_categories_api_data()})

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

    is_active = str(data.get("is_active", "true")).lower() == "true"

    try:
        with transaction.atomic():
            if request.method == "POST":
                category = Category(
                    name=name,
                    slug=slug,
                    parent=parent,
                    description=str(data.get("description") or "").strip(),
                    icon=str(data.get("icon") or "").strip(),
                    is_active=is_active,
                )
                category.full_clean()
                category.save()
                if image:
                    result = services.store_catalog_image(image, "categories", str(category.id), "image")
                    category.image = result.get("secure_url") or result.get("url")
                    category.save(update_fields=["image"])
    except IntegrityError:
        return _category_api_error("A category with this name or slug already exists.")
    except ValidationError:
        return _category_api_error("Category data or image is invalid. Please check the submitted fields.")
    except ValueError as error:
        return _category_api_error(str(error))

    return JsonResponse({"ok": True, "id": category.id})

@catalog_admin_required
@require_http_methods(["POST", "PATCH", "PUT", "DELETE"])
def category_api_detail(request: HttpRequest, category_id: int) -> JsonResponse:
    category = Category.objects.filter(pk=category_id).first()
    if not category:
        return _category_api_error("Category was not found.", status=404)

    if request.method == "DELETE":
        if category.products.exists():
            return _category_api_error("Categories with products cannot be deleted.")
        if category.children.exists():
            return _category_api_error("Categories with subcategories cannot be deleted.")
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
        category.description = str(data.get("description") or "").strip()

    if "icon" in data:
        category.icon = str(data.get("icon") or "").strip()

    if "is_active" in data:
        category.is_active = str(data.get("is_active")).lower() == "true"

    if "parent_id" in data:
        parent_id = data.get("parent_id")
        if parent_id in (None, ""):
            category.parent = None
        else:
            if str(parent_id) == str(category.id):
                return _category_api_error("A category cannot be its own parent.")
            parent = Category.objects.filter(pk=parent_id).first()
            if not parent:
                return _category_api_error("Parent category was not found.")

            descendant_ids = set()
            pending_parent_ids = [category.id]
            while pending_parent_ids:
                child_ids = list(Category.objects.filter(parent_id__in=pending_parent_ids).values_list("id", flat=True))
                descendant_ids.update(child_ids)
                pending_parent_ids = child_ids

            if parent.id in descendant_ids:
                return _category_api_error("A category cannot be moved below its descendant.")
            category.parent = parent

    try:
        category.full_clean()
        category.save()
        if image:
            result = services.store_catalog_image(image, "categories", str(category.id), "image")
            category.image = result.get("secure_url") or result.get("url")
            category.save(update_fields=["image"])
    except IntegrityError:
        return _category_api_error("A category with this name or slug already exists.")
    except ValidationError:
        return _category_api_error("Category data or image is invalid. Please check the submitted fields.")
    except ValueError as error:
        return _category_api_error(str(error))

    return JsonResponse({"ok": True, "id": category.id})

@catalog_admin_required
def catalog_brands(request: HttpRequest) -> HttpResponse:
    """Render the brand management page."""
    context = services.get_brands_data()
    return render(request, "catalog/brands/brands.html", context)

def _brand_api_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)

@catalog_admin_required
@require_http_methods(["GET", "POST"])
def brand_api(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse({"ok": True, **services.get_brands_api_data()})
    try:
        brand = services.save_brand(request.POST, request.FILES)
        return JsonResponse({"ok": True, "brand": services.brand_payload(brand)})
    except (ValidationError, IntegrityError, ValueError) as exc:
        return _brand_api_error(str(exc) or "Invalid brand data.")

@catalog_admin_required
@require_http_methods(["GET", "POST", "PATCH", "PUT", "DELETE"])
def brand_api_detail(request: HttpRequest, brand_id: int) -> JsonResponse:
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
        elif action in {"activate", "deactivate"}:
            brand.is_active = action == "activate"
        elif action in {"feature", "unfeature"}:
            brand.is_featured = action == "feature"
        else:
            return _brand_api_error("This brand action is not supported.")
        brand.save(update_fields=["is_active", "is_featured", "updated_at"])
        return JsonResponse({"ok": True, "brand": services.brand_payload(brand)})
        
    try:
        brand = services.save_brand(data, request.FILES, brand)
        return JsonResponse({"ok": True, "brand": services.brand_payload(brand)})
    except (ValidationError, IntegrityError, ValueError) as exc:
        return _brand_api_error(str(exc) or "Invalid brand data.")

@catalog_admin_required
@require_POST
def brand_import_api(request: HttpRequest) -> JsonResponse:
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

@catalog_admin_required
@require_http_methods(["GET"])
def brand_export_api(request: HttpRequest) -> HttpResponse:
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
