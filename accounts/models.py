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

from django.conf import settings
from django.db import models


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

class SellerApplication(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        CHANGES_REQUESTED = "changes_requested", "Changes Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    seller = models.OneToOneField(
        Seller,
        on_delete=models.CASCADE,
        related_name="application",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    submitted_at = models.DateTimeField(null=True, blank=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_applications",
    )

    application_source = models.CharField(
        max_length=100,
        blank=True,
    )

    referral_code = models.CharField(
        max_length=100,
        blank=True,
    )

    admin_notes = models.TextField(blank=True)

    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

class SellerApplicationDocument(models.Model):

    class DocumentType(models.TextChoices):
        CNIC_FRONT = "cnic_front", "CNIC Front"
        CNIC_BACK = "cnic_back", "CNIC Back"
        BUSINESS_CERTIFICATE = "business_certificate", "Business Registration Certificate"
        NTN = "ntn", "NTN Certificate"
        BANK_STATEMENT = "bank_statement", "Bank Statement"
        STORE_PHOTO = "store_photo", "Store Photo"

    application = models.ForeignKey(
        SellerApplication,
        related_name="documents",
        on_delete=models.CASCADE,
    )

    document_type = models.CharField(
        max_length=50,
        choices=DocumentType.choices,
    )

    # Cloudinary URL for images, PDFs, and other seller application files.
    file = models.URLField(blank=True, null=True, max_length=1000)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    verified = models.BooleanField(default=False)

    verification_note = models.TextField(blank=True)

    @property
    def is_image(self):
        """Keep document previews working for Cloudinary URL-backed files."""
        if not self.file:
            return False
        path = self.file.split("?", 1)[0].lower()
        return path.endswith((".jpg", ".jpeg", ".png", ".webp"))

class SellerApplicationFlag(models.Model):

    class Severity(models.TextChoices):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"

    application = models.ForeignKey(
        SellerApplication,
        related_name="flags",
        on_delete=models.CASCADE,
    )

    title = models.CharField(max_length=200)

    description = models.TextField()

    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
    )

    resolved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

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
