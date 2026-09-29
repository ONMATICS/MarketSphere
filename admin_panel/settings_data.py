"""Cached access to settings kept in the AdminSettingsData JSON document."""

from django.core.cache import cache

from .models import AdminSettingsData


ADMIN_SETTINGS_DATA_CACHE_KEY = "admin_settings_data:all"
ADMIN_SETTINGS_DATA_CACHE_TIMEOUT = 60


def get_admin_settings_data():
    try:
        cached = cache.get(ADMIN_SETTINGS_DATA_CACHE_KEY)
        if cached is not None:
            return cached
        data = AdminSettingsData.objects.filter(pk=1).values_list("data", flat=True).first() or {}
        if not isinstance(data, dict):
            data = {}
        cache.set(ADMIN_SETTINGS_DATA_CACHE_KEY, data, timeout=ADMIN_SETTINGS_DATA_CACHE_TIMEOUT)
        return data
    except Exception:
        return {}


def get_admin_setting(section, key, default=None):
    value = get_admin_settings_data().get(section, {}).get(key, default)
    return default if value is None else value


def invalidate_admin_settings_data_cache():
    try:
        cache.delete(ADMIN_SETTINGS_DATA_CACHE_KEY)
    except Exception:
        pass
