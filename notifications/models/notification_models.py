from django.conf import settings
from django.db import models


class Notification(models.Model):

    class NotificationType(models.TextChoices):
        ORDER_CREATED = "ORDER_CREATED", "Order Created"
        ORDER_CONFIRMED = "ORDER_CONFIRMED", "Order Confirmed"
        ORDER_PROCESSING = "ORDER_PROCESSING", "Order Processing"
        ORDER_SHIPPED = "ORDER_SHIPPED", "Order Shipped"
        ORDER_DELIVERED = "ORDER_DELIVERED", "Order Delivered"
        ORDER_CANCELLED = "ORDER_CANCELLED", "Order Cancelled"

        WISHLIST_PRICE_DROP = "WISHLIST_PRICE_DROP", "Wishlist Price Drop"

        LOW_STOCK = "LOW_STOCK", "Low Stock"

        SELLER_APPLICATION_APPROVED = (
            "SELLER_APPLICATION_APPROVED",
            "Seller Application Approved",
        )
        SELLER_APPLICATION_REJECTED = (
            "SELLER_APPLICATION_REJECTED",
            "Seller Application Rejected",
        )

        SYSTEM = "SYSTEM", "System"

    class Audience(models.TextChoices):
        ALL_USERS = "ALL_USERS", "All Users"
        SELLER = "SELLER", "Seller"
        BUYER = "BUYER", "Buyer"
        ADMIN = "ADMIN", "Admin"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
    )

    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
    )

    icon = models.CharField(
        max_length=100,
        blank=True,
    )

    title = models.CharField(
        max_length=255,
    )

    message = models.TextField()

    target_url = models.CharField(
        max_length=500,
        blank=True,
    )

    data = models.JSONField(
        default=dict,
        blank=True,
    )

    is_read = models.BooleanField(
        default=False,
        db_index=True,
    )

    read_at = models.DateTimeField(
        null=True,
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
                fields=["recipient", "is_read", "-created_at"]
            ),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.title}"