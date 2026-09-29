import logging

from django.db import transaction
from django.utils import timezone

from notifications.models import ActivityLog, Notification
from admin_panel.notification_settings import notification_channel_enabled

logger = logging.getLogger(__name__)


MAX_NOTIFICATIONS = 10


def create_activity_log(
    *,
    category,
    action,
    title,
    description="",
    actor=None,
    actor_type=ActivityLog.ActorType.SYSTEM,
    target=None,
    metadata=None,
):
    """Create an activity entry for the same event as a notification/email."""
    activity_log = ActivityLog(
        actor=actor,
        actor_type=actor_type,
        category=category,
        action=action,
        title=title,
        description=description,
        metadata=metadata or {},
    )

    if target is not None:
        activity_log.target = target

    activity_log.save()
    return activity_log


def get_notifications(user_id, audience=Notification.Audience.ALL_USERS):
    return Notification.objects.filter(
        recipient_id=user_id,
        audience=audience
    ).order_by("-created_at")[:MAX_NOTIFICATIONS]


def get_unread_count(user_id, audience=Notification.Audience.ALL_USERS):
    return Notification.objects.filter(
        recipient_id=user_id,
        audience=audience,
        is_read=False,
    ).count()


@transaction.atomic
def create_notification(
    user_id,
    notification_type,
    title,
    message,
    icon="",
    target_url="",
    audience=Notification.Audience.ALL_USERS,
    data=None,
):
    if not notification_channel_enabled(notification_type, audience, "in_app"):
        return None

    notifications = Notification.objects.filter(
        recipient_id=user_id,
        audience=audience
    ).order_by("-created_at")

    excess_count = notifications.count() - (MAX_NOTIFICATIONS - 1)

    if excess_count > 0:
        oldest_notifications = notifications.order_by(
            "created_at"
        )[:excess_count]

        Notification.objects.filter(
            id__in=oldest_notifications.values_list("id", flat=True)
        ).delete()

    return Notification.objects.create(
        recipient_id=user_id,
        notification_type=notification_type,
        icon=icon,
        title=title,
        message=message,
        target_url=target_url,
        audience=audience,
        data=data or {},
    )


@transaction.atomic
def mark_all_as_read(user_id):
    return Notification.objects.filter(
        recipient_id=user_id,
        is_read=False,
    ).update(
        is_read=True,
        read_at=timezone.now(),
    )


@transaction.atomic
def clear_all_notifications(user_id):
    deleted_count, _ = Notification.objects.filter(
        recipient_id=user_id
    ).delete()

    return deleted_count


def notify(
    user_id,
    notification_type,
    title,
    message,
    icon="",
    target_url="",
    audience=Notification.Audience.ALL_USERS,
    data=None,
    email=False,
    email_service=None,
    email_object=None,
    activity=False,
    activity_category=ActivityLog.Category.SYSTEM,
    activity_action=None,
    activity_title=None,
    activity_description="",
    activity_actor=None,
    activity_actor_type=ActivityLog.ActorType.SYSTEM,
    activity_target=None,
    activity_metadata=None,
):
    email = email and notification_channel_enabled(notification_type, audience, "email")
    notification = create_notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        icon=icon,
        target_url=target_url,
        audience=audience,
        data=data,
    )

    if activity:
        create_activity_log(
            category=activity_category,
            action=activity_action or str(notification_type),
            title=activity_title or title,
            description=activity_description or message,
            actor=activity_actor,
            actor_type=activity_actor_type,
            target=activity_target,
            metadata=activity_metadata,
        )

    if email and email_service and email_object:
        transaction.on_commit(
            lambda: email_service(email_object)
        )

    return notification


def schedule_notification(
    *, user_id, notification_type, title, message, icon="", target_url="",
    audience=Notification.Audience.ALL_USERS, data=None, activity=False,
    activity_category=ActivityLog.Category.SYSTEM, activity_action=None,
    activity_title=None, activity_description="", activity_actor=None,
    activity_actor_type=ActivityLog.ActorType.SYSTEM, activity_target=None,
    activity_metadata=None,
):
    """Create an in-app notification only after the surrounding transaction commits."""
    def _create():
        try:
            create_notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                icon=icon,
                target_url=target_url,
                audience=audience,
                data=data,
            )
            if activity:
                create_activity_log(
                    category=activity_category,
                    action=activity_action or str(notification_type),
                    title=activity_title or title,
                    description=activity_description or message,
                    actor=activity_actor,
                    actor_type=activity_actor_type,
                    target=activity_target,
                    metadata=activity_metadata,
                )
        except Exception:
            logger.exception("Could not create notification for user %s", user_id)

    transaction.on_commit(_create, robust=True)


def schedule_low_stock_event(product, previous_stock, current_stock):
    """Schedule one low-stock event when stock crosses into the low range."""
    threshold = product.min_stock_level
    if previous_stock <= threshold or current_stock > threshold:
        return False

    from django.urls import NoReverseMatch, reverse
    from django.conf import settings
    from notifications.emails.sellers import send_low_stock_email

    try:
        target_url = f"{settings.SITE_URL.rstrip('/')}/{reverse('seller-edit-product', kwargs={'product_slug': product.slug}).lstrip('/')}"
    except NoReverseMatch:
        logger.exception("Could not reverse low-stock product URL")
        target_url = ""

    data = {
        "product_id": product.pk,
        "product_slug": product.slug,
        "stock_quantity": current_stock,
        "min_stock_level": threshold,
    }

    def _create_event():
        try:
            schedule_notification_now = create_notification(
                user_id=product.seller.user_id,
                notification_type=Notification.NotificationType.LOW_STOCK,
                title="Low stock alert",
                message=(
                    f"{product.name} has {current_stock} units remaining "
                    f"(minimum {threshold})."
                ),
                icon="bi-exclamation-triangle",
                target_url=target_url,
                audience=Notification.Audience.SELLER,
                data=data,
            )
            create_activity_log(
                category=ActivityLog.Category.PRODUCT,
                action="LOW_STOCK",
                title="Low stock alert",
                description=(
                    f"{product.name} has {current_stock} units remaining "
                    f"(minimum {threshold})."
                ),
                actor_type=ActivityLog.ActorType.SYSTEM,
                target=product,
                metadata=data,
            )
            # Email preference is deliberately checked only by the email function.
            if notification_channel_enabled("LOW_STOCK", "SELLER", "email"):
                send_low_stock_email(product)
            return schedule_notification_now
        except Exception:
            logger.exception("Could not create low-stock event for product %s", product.pk)
            return None

    transaction.on_commit(_create_event, robust=True)
    return True
