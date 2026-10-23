from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ActivityLog(models.Model):

    class ActorType(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        BUYER = "BUYER", "Buyer"
        SELLER = "SELLER", "Seller"
        SYSTEM = "SYSTEM", "System"

    class Category(models.TextChoices):
        ACCOUNT = "ACCOUNT", "Account"
        SELLER = "SELLER", "Seller"
        PRODUCT = "PRODUCT", "Product"
        ORDER = "ORDER", "Order"
        SECURITY = "SECURITY", "Security"
        SUPPORT = "SUPPORT", "Support"
        PAYMENT = "PAYMENT", "Payment"
        SYSTEM = "SYSTEM", "System"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )

    actor_type = models.CharField(
        max_length=20,
        choices=ActorType.choices,
        default=ActorType.SYSTEM,
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )

    action = models.CharField(
        max_length=100,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        blank=True,
    )

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )

    target_object_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    target = GenericForeignKey(
        "target_content_type",
        "target_object_id",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["category", "-created_at"],
            ),
            models.Index(
                fields=["actor", "-created_at"],
            ),
            models.Index(
                fields=[
                    "target_content_type",
                    "target_object_id",
                    "-created_at",
                ],
            ),
        ]

    def __str__(self):
        return self.title