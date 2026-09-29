"""Cached access to the notification channel configuration."""

from django.core.cache import cache

from .models import NotificationSettings


NOTIFICATION_SETTINGS_CACHE_KEY = "notification_settings:all"
NOTIFICATION_SETTINGS_CACHE_TIMEOUT = 60

DEFAULT_CHANNELS = {"email": True, "in_app": True, "push": False}


def _normalise_channels(value):
    channels = dict(DEFAULT_CHANNELS)
    if isinstance(value, dict):
        for name in channels:
            raw = value.get(name, channels[name])
            if isinstance(raw, str):
                raw = raw.strip().lower() in {"1", "true", "yes", "on"}
            channels[name] = bool(raw)
    return channels


def get_notification_settings():
    try:
        cached = cache.get(NOTIFICATION_SETTINGS_CACHE_KEY)
        if cached is not None:
            return cached
        settings = NotificationSettings.objects.filter(pk=1).first()
        if settings is None:
            settings = NotificationSettings(pk=1)
        cache.set(NOTIFICATION_SETTINGS_CACHE_KEY, settings, timeout=NOTIFICATION_SETTINGS_CACHE_TIMEOUT)
        return settings
    except Exception:
        return NotificationSettings(pk=1)


def notification_channel_enabled(notification_type, audience, channel):
    """Return whether a configured channel is enabled for an event/audience."""
    if channel not in DEFAULT_CHANNELS:
        return False
    settings = get_notification_settings()
    audience_map = {
        "BUYER": settings.buyer_notifications,
        "SELLER": settings.seller_notifications,
        "ADMIN": settings.admin_notifications,
        "ALL_USERS": settings.buyer_notifications,
    }
    event_map = audience_map.get(str(audience), {}) or {}
    configured = event_map.get(str(notification_type), event_map.get("*", DEFAULT_CHANNELS))
    return _normalise_channels(configured).get(channel, DEFAULT_CHANNELS[channel])


def invalidate_notification_settings_cache():
    try:
        cache.delete(NOTIFICATION_SETTINGS_CACHE_KEY)
    except Exception:
        pass
