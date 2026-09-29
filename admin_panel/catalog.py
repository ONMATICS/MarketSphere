from django.core.cache import cache

from .models import AdminSettingsData, CatalogSettings


CATALOG_SETTINGS_CACHE_KEY = "catalog_settings:all"
CATALOG_SETTINGS_CACHE_TIMEOUT = 60
CATEGORY_VISIBILITY_CACHE_KEY = "catalog_settings:category_visibility"


def get_catalog_settings():
    """Return cached catalog settings without creating a missing database row."""
    try:
        cached = cache.get(CATALOG_SETTINGS_CACHE_KEY)
        if cached is not None:
            return cached

        settings = CatalogSettings.objects.filter(pk=1).first()
        if settings is None:
            settings = CatalogSettings(pk=1)

        cache.set(
            CATALOG_SETTINGS_CACHE_KEY,
            settings,
            timeout=CATALOG_SETTINGS_CACHE_TIMEOUT,
        )
        return settings
    except Exception:
        return CatalogSettings(pk=1)


def invalidate_catalog_settings_cache():
    try:
        cache.delete(CATALOG_SETTINGS_CACHE_KEY)
        cache.delete(CATEGORY_VISIBILITY_CACHE_KEY)
    except Exception:
        pass


def categories_are_visible():
    """Read the category toggle used by the settings screen safely."""
    try:
        cached = cache.get(CATEGORY_VISIBILITY_CACHE_KEY)
        if cached is not None:
            return bool(cached)
        data = AdminSettingsData.objects.filter(pk=1).values_list("data", flat=True).first() or {}
        value = data.get("catalog", {}).get("category_visibility", True)
        if isinstance(value, str):
            value = value.strip().lower() not in {"false", "0", "off", "no"}
        value = bool(value)
        cache.set(CATEGORY_VISIBILITY_CACHE_KEY, value, timeout=CATALOG_SETTINGS_CACHE_TIMEOUT)
        return value
    except Exception:
        return True
