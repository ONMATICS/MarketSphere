from django.conf import settings
from django.db import models


class SupportRequest(models.Model):

    class RequestType(models.TextChoices):
        CONTACT = "contact", "Contact Support"
        PROBLEM = "problem", "Report a Problem"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        WAITING_FOR_USER = "waiting_for_user", "Waiting for User"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Category(models.TextChoices):
        GENERAL = "general", "General Question"
        ORDER = "order", "Order"
        DELIVERY = "delivery", "Delivery"
        PAYMENT = "payment", "Payment"
        PRODUCT = "product", "Product"
        SELLER = "seller", "Seller"
        ACCOUNT = "account", "Account"
        TECHNICAL = "technical", "Technical"
        FEEDBACK = "feedback", "Feedback / Suggestion"
        OTHER = "other", "Other"

    class ContactMethod(models.TextChoices):
        EMAIL = "email", "Email"
        IN_APP = "in_app", "In-App Response"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_requests",
    )

    request_type = models.CharField(
        max_length=20,
        choices=RequestType.choices,
    )

    category = models.CharField(
        max_length=30,
        choices=Category.choices,
    )

    subject = models.CharField(
        max_length=255,
    )

    message = models.TextField(
        max_length=600,
    )

    related_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_requests",
    )

    related_product_name = models.CharField(
        max_length=255,
        blank=True,
    )

    attachment = models.FileField(
        upload_to="support/attachments/",
        null=True,
        blank=True,
    )

    preferred_contact_method = models.CharField(
        max_length=20,
        choices=ContactMethod.choices,
        default=ContactMethod.EMAIL,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-updated_at", "-created_at"]

        indexes = [
            models.Index(
                fields=["user", "status", "-updated_at"]
            ),
            models.Index(
                fields=["request_type", "status", "-created_at"]
            ),
        ]

    def __str__(self):
        return f"#{self.pk} - {self.subject}"


class SupportMessage(models.Model):

    class SenderType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        ADMIN = "admin", "Admin"

    request = models.ForeignKey(
        SupportRequest,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="support_messages",
    )

    sender_type = models.CharField(
        max_length=20,
        choices=SenderType.choices,
    )

    message = models.TextField()

    attachment = models.FileField(
        upload_to="support/messages/",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Request #{self.request_id} - {self.sender_type}"