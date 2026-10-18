import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models.fields.files import FieldFile
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from admin_panel import services
from admin_panel.models import (
    AdminAuditLog,
    AdminSettingsData,
    CatalogSettings,
    CheckoutSettings,
    MarketplaceSettings,
    NotificationSettings,
    StoreSettings,
)
from notifications.models import ActivityLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CONSTANTS & SETTINGS HELPERS
# ---------------------------------------------------------

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

def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, FieldFile):
        try:
            return value.url
        except ValueError:
            return ""
    return value

def _model_values(instance) -> Dict[str, Any]:
    return {
        field.name: _json_value(getattr(instance, field.name))
        for field in instance._meta.fields
        if field.name not in {"id", "updated_at"}
    }

def _settings_payload() -> Dict[str, Any]:
    stored = AdminSettingsData.load().data or {}
    payload = dict(stored)
    for section, model_class in SETTINGS_SECTION_MODELS.items():
        values = dict(payload.get(section, {}))
        values.update(_model_values(model_class.load()))
        payload[section] = values
    return payload

def _client_ip(request: HttpRequest) -> str:
    return request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")

def _post_value(value: Any, field_name: str, boolean_fields: set) -> Any:
    if field_name in boolean_fields:
        return str(value).lower() in {"1", "true", "yes", "on"}
    return value


# ---------------------------------------------------------
# VIEWS
# ---------------------------------------------------------

@staff_member_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Render the primary administrative dashboard."""
    return render(request, "admin_dashboard.html")


@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_settings(request: HttpRequest) -> HttpResponse:
    """Manage platform-wide settings across various categories."""
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
        if uploaded and getattr(uploaded, "name", ""):
            values[key] = uploaded

    try:
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
        
    except (ValueError, InvalidOperation, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid configuration value submitted."}, status=400)
    except Exception:
        logger.exception("Failed to update admin settings.")
        return JsonResponse({"ok": False, "error": "An unexpected error occurred while saving settings."}, status=500)


@staff_member_required
@require_POST
def logout_all_devices(request: HttpRequest) -> JsonResponse:
    """Forcibly clear all active sessions for a given user."""
    user_id = request.POST.get("userId")
    deleted = 0
    for session in Session.objects.all():
        data = session.get_decoded()
        if data.get("_auth_user_id") == str(user_id):
            session.delete()
            deleted += 1
    return JsonResponse({"status": "success", "message": f"Logged out from {deleted} active device(s)."})