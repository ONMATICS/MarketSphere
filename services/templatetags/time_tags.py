from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def custom_timesince(value):
    if not value:
        return ""

    now = timezone.now()

    if timezone.is_naive(value):
        value = timezone.make_aware(value)

    seconds = int((now - value).total_seconds())

    if seconds < 60:
        return "now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"

    days = hours // 24
    if days < 7:
        return f"{days}d ago"

    weeks = days // 7
    if weeks < 5:
        return f"{weeks}w ago"

    months = days // 30
    if months < 12:
        return f"{months}mo ago"

    years = days // 365
    return f"{years}y ago"