"""Cached access to the public store identity and contact settings."""

from django.core.cache import cache

from .models import StoreSettings


STORE_SETTINGS_CACHE_KEY = "store_settings:all"
STORE_SETTINGS_CACHE_TIMEOUT = 60


def get_store_settings():
    try:
        cached = cache.get(STORE_SETTINGS_CACHE_KEY)
        if cached is not None:
            return cached
        settings = StoreSettings.objects.filter(pk=1).first()
        if settings is None:
            settings = StoreSettings(pk=1)
        cache.set(STORE_SETTINGS_CACHE_KEY, settings, timeout=STORE_SETTINGS_CACHE_TIMEOUT)
        return settings
    except Exception:
        return StoreSettings(pk=1)


def invalidate_store_settings_cache():
    try:
        cache.delete(STORE_SETTINGS_CACHE_KEY)
    except Exception:
        pass
