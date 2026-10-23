from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class Address(models.Model):

    HOME = "home"
    OFFICE = "office"
    BUSINESS = "business"
    OTHER = "other"

    ADDRESS_TYPES = [
        (HOME, "Home"),
        (OFFICE, "Office"),
        (BUSINESS, "Business"),
        (OTHER, "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )

    address_type = models.CharField(
        max_length=20,
        choices=ADDRESS_TYPES,
        default=HOME,
    )

    full_name = models.CharField(max_length=150)

    phone = models.CharField(max_length=20)

    address_line_1 = models.CharField(max_length=255)

    address_line_2 = models.CharField(
        max_length=255,
        blank=True,
    )

    city = models.CharField(max_length=100)

    postal_code = models.CharField(max_length=20)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.pk and not self.user.addresses.exists():
            self.is_default = True

        if self.is_default:
            self.user.addresses.exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)
        
    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.get_address_type_display()}"


class User(AbstractUser):

    class AccountStatus(models.TextChoices):
        UNVERIFIED = "UNVERIFIED", "Unverified"
        VERIFIED = "VERIFIED", "Verified"
        SUSPENDED = "SUSPENDED", "Suspended"
        DEACTIVATED = "DEACTIVATED", "Deactivated"
        BLOCKED = "BLOCKED", "Blocked"

    contact = models.CharField(max_length=20, blank=True)

    profile_image_url = models.URLField(blank=True, null=True, max_length=500)

    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.UNVERIFIED,
    )


class UserPreferences(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="preferences",
    )

    order_updates = models.BooleanField(default=True)
    promotional_emails = models.BooleanField(default=True)
    price_drop_alerts = models.BooleanField(default=True)
    wishlist_alerts = models.BooleanField(default=True)
    low_stock_alerts = models.BooleanField(default=True)
    review_reminders = models.BooleanField(default=True)
    newsletter = models.BooleanField(default=True)

    security_alerts = models.BooleanField(default=True, editable=False)

    email_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"