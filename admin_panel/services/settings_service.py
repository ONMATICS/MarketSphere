from decimal import Decimal
from typing import Any

from django.core.cache import cache

from accounts.models import User
from admin_panel.catalog import invalidate_catalog_settings_cache
from admin_panel.checkout import invalidate_checkout_settings_cache
from admin_panel.marketplace import invalidate_marketplace_settings_cache
from admin_panel.models import (
    AdminAuditLog, CatalogSettings, CheckoutSettings, MarketplaceSettings,
    NotificationSettings, StoreSettings
)
from admin_panel.notification_settings import invalidate_notification_settings_cache
from admin_panel.settings_data import invalidate_admin_settings_data_cache
from admin_panel.store import invalidate_store_settings_cache


MARKETPLACE_ONLINE_CACHE_KEY = "marketplace_settings:marketplace_online"
PLATFORM_SETTINGS_CACHE_KEY = "platform_settings"
PLATFORM_SETTINGS_CACHE_TIMEOUT = 3600
SENSITIVE_SETTING_NAMES = {
    "password", "smtp_password", "api_key", "secret_key", "client_secret",
    "access_token", "refresh_token", "private_key", "encryption_key", "webhook_secret",
}


def get_platform_settings() -> dict[str, Any]:
    """Retrieve macro-level configurations for the storefront operations."""
    cached = cache.get(PLATFORM_SETTINGS_CACHE_KEY)
    if cached is not None:
        return cached

    settings_data = {
        "store": StoreSettings.load(),
        "marketplace": MarketplaceSettings.load(),
        "checkout": CheckoutSettings.load(),
        "catalog": CatalogSettings.load(),
        "notifications": NotificationSettings.load(),
    }

    cache.set(PLATFORM_SETTINGS_CACHE_KEY, settings_data, timeout=PLATFORM_SETTINGS_CACHE_TIMEOUT)
    return settings_data


def invalidate_platform_settings_cache() -> None:
    """Clear cached objects tying to overall system policies and definitions."""
    cache.delete(PLATFORM_SETTINGS_CACHE_KEY)
    invalidate_marketplace_settings_cache()
    invalidate_checkout_settings_cache()
    invalidate_catalog_settings_cache()
    invalidate_notification_settings_cache()
    invalidate_admin_settings_data_cache()
    invalidate_store_settings_cache()


def serialize_setting_value(value: Any) -> str:
    """Convert a raw setting object into its printable form for log tracking."""
    if value is None: return ""
    if isinstance(value, Decimal): return str(value)
    if hasattr(value, "url"):
        try: return value.url
        except ValueError: return ""
    if isinstance(value, bool): return "true" if value else "false"
    return str(value)


def is_sensitive_setting(setting_name: str) -> bool:
    """Identify if a configuration setting contains a private token or key."""
    name = setting_name.lower()
    return name in SENSITIVE_SETTING_NAMES or any(
        sensitive in name for sensitive in ("password", "secret", "token", "private_key", "api_key")
    )


def log_audit_event(
    admin: User, action: str, section: str, setting_name: str,
    old_value: Any, new_value: Any, ip_address: str | None = None
) -> None:
    """Document a distinct setting mutation applied by an authorized backend employee."""
    if is_sensitive_setting(setting_name):
        old_value = "********"
        new_value = "********"
    else:
        old_value = serialize_setting_value(old_value)
        new_value = serialize_setting_value(new_value)

    AdminAuditLog.objects.create(
        admin=admin, action=action, section=section, setting_name=setting_name,
        old_value=old_value, new_value=new_value, ip_address=ip_address,
    )


def get_store_settings() -> StoreSettings:
    """Retrieve global store settings (utilizing isolated lazy cache fetching)."""
    from admin_panel.store import get_store_settings as get_cached_store_settings
    return get_cached_store_settings()


def get_marketplace_settings() -> MarketplaceSettings:
    """Retrieve standard marketplace rules (utilizing isolated lazy cache fetching)."""
    from admin_panel.marketplace import get_marketplace_settings as get_cached_marketplace_settings
    return get_cached_marketplace_settings()


def get_checkout_settings() -> CheckoutSettings:
    """Retrieve standard checkout properties (utilizing isolated lazy cache fetching)."""
    from admin_panel.checkout import get_checkout_settings as get_cached_checkout_settings
    return get_cached_checkout_settings()


def get_catalog_settings() -> CatalogSettings:
    """Retrieve inventory logic rules (utilizing isolated lazy cache fetching)."""
    from admin_panel.catalog import get_catalog_settings as get_cached_catalog_settings
    return get_cached_catalog_settings()