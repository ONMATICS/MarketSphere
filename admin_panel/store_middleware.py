from django.utils import timezone, translation

from .store import get_store_settings


class StoreSettingsMiddleware:
    """Apply the store's request-scoped timezone and language settings."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        store = get_store_settings()
        try:
            timezone.activate(getattr(store, "timezone", "UTC") or "UTC")
        except Exception:
            timezone.activate("UTC")
        try:
            translation.activate(getattr(store, "language", "en") or "en")
        except Exception:
            translation.activate("en")
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
            translation.deactivate()
