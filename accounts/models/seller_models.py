from django.db import models
from django.conf import settings
from .user_models import Address


class Seller(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        DEACTIVATED = "deactivated", "Deactivated"
        SUSPENDED = "suspended", "Suspended"
        BLOCKED = "blocked", "Blocked"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )

    store_email = models.EmailField(blank=True, null=True)

    store_name = models.CharField(max_length=100)

    slug = models.SlugField(unique=True, help_text="Unique URL for the seller store.")

    store_description = models.TextField(blank=True, null=True)

    # Cloudinary URL. Existing local values are kept untouched; new uploads use
    # the seller's Cloudinary folder through accounts.services.
    store_logo = models.URLField(blank=True, null=True, max_length=1000)

    store_banner = models.URLField(blank=True, null=True, max_length=1000)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )

    verification_notes = models.TextField(
        blank=True, null=True, help_text="Reason for rejection or notes from the admin."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_verified(self):
        return self.status == self.Status.VERIFIED

    @property
    def can_sell(self):
        return self.status == self.Status.VERIFIED

    @property
    def can_access_dashboard(self):
        return self.status in (
            self.Status.VERIFIED,
            self.Status.DEACTIVATED,
        )

    @property
    def business_address(self):
        return self.user.addresses.filter(address_type=Address.BUSINESS).first()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Seller"
        verbose_name_plural = "Sellers"

    def __str__(self):
        return self.store_name


class SellerSettings(models.Model):
    seller = models.OneToOneField(
        Seller,
        on_delete=models.CASCADE,
        related_name="settings",
    )

    class HandlingTime(models.IntegerChoices):
        ONE_DAY = 1, "1 business day"
        TWO_DAYS = 2, "2 business days"
        THREE_DAYS = 3, "3 business days"
        FIVE_DAYS = 5, "5 business days"

    default_handling_time = models.PositiveSmallIntegerField(
        choices=HandlingTime.choices,
        default=HandlingTime.TWO_DAYS,
    )
    
    # Shipping
    default_courier = models.CharField(max_length=100, blank=True)
    auto_mark_shipped = models.BooleanField(default=False)
    shipping_notes = models.TextField(blank=True)
    return_address = models.TextField(blank=True)
    shipping_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    # Notifications
    email_new_order = models.BooleanField(default=True)
    email_cancelled_order = models.BooleanField(default=True)
    email_delivered_order = models.BooleanField(default=True)
    email_low_stock = models.BooleanField(default=True)
    weekly_sales_summary = models.BooleanField(default=False)
    monthly_store_report = models.BooleanField(default=True)

    business_registration_number = models.CharField(
        max_length=100,
        blank=True,
    )

    tax_id = models.CharField(
        max_length=100,
        blank=True,
    )

    business_registration_verified = models.BooleanField(default=False)

    bank_account_verified = models.BooleanField(default=False)

    address_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SellerProfile(models.Model):
    seller = models.OneToOneField(
        Seller,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    business_category = models.CharField(max_length=100, blank=True)

    business_type = models.CharField(
        max_length=100,
        blank=True,
    )

    national_id_number = models.CharField(
        max_length=30,
        blank=True,
    )

    years_in_business = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    expected_monthly_volume = models.CharField(
        max_length=100,
        blank=True,
    )

    product_categories = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated categories",
    )

    website = models.URLField(blank=True)

    facebook_label = models.CharField(max_length=100, blank=True)
    facebook_url = models.URLField(blank=True)

    linkedin_label = models.CharField(max_length=100, blank=True)
    linkedin_url = models.URLField(blank=True)

    instagram_label = models.CharField(max_length=100, blank=True)
    instagram_url = models.URLField(blank=True)

    twitter_label = models.CharField(max_length=100, blank=True)
    twitter_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)