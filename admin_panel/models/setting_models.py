from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .base_models import SingletonModel


class StoreSettings(SingletonModel):
    marketplace_logo = models.ImageField(
        upload_to="platform/",
        blank=True,
        null=True,
    )
    marketplace_favicon = models.ImageField(
        upload_to="platform/",
        blank=True,
        null=True,
    )

    marketplace_name = models.CharField(
        max_length=100,
        default="MarketSphere",
    )
    business_name = models.CharField(
        max_length=150,
        blank=True,
    )
    marketplace_description = models.TextField(blank=True)

    business_address = models.TextField(blank=True)

    contact_email = models.EmailField(blank=True)
    support_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    support_url = models.URLField(blank=True)

    privacy_url = models.URLField(blank=True)
    terms_url = models.URLField(blank=True)

    country = models.CharField(
        max_length=2,
        default="PK",
    )
    timezone = models.CharField(
        max_length=50,
        default="Asia/Karachi",
    )
    currency = models.CharField(
        max_length=3,
        default="PKR",
    )
    language = models.CharField(
        max_length=10,
        default="en",
    )

    date_format = models.CharField(
        max_length=30,
        default="d/m/Y",
    )
    time_format = models.CharField(
        max_length=10,
        default="12",
    )

    business_registration_number = models.CharField(
        max_length=50,
        blank=True,
    )
    tax_registration_number = models.CharField(
        max_length=50,
        blank=True,
    )

    social_facebook = models.URLField(blank=True)
    social_instagram = models.URLField(blank=True)
    social_twitter = models.URLField(blank=True)
    social_linkedin = models.URLField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.marketplace_name


class MarketplaceSettings(SingletonModel):
    marketplace_online = models.BooleanField(default=True)

    buyer_registration = models.BooleanField(default=True)
    seller_registration = models.BooleanField(default=True)

    guest_checkout = models.BooleanField(default=False)
    multi_seller_orders = models.BooleanField(default=True)

    seller_approval_required = models.BooleanField(default=True)
    product_approval_required = models.BooleanField(default=False)

    buyer_reviews = models.BooleanField(default=True)
    seller_reviews = models.BooleanField(default=True)

    featured_products = models.BooleanField(default=True)
    featured_sellers = models.BooleanField(default=False)
    featured_brands = models.BooleanField(default=False)

    class CommissionType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FLAT = "flat", "Flat"
        TIERED = "tiered", "Tiered"

    commission_type = models.CharField(
        max_length=20,
        choices=CommissionType.choices,
        default=CommissionType.PERCENTAGE,
    )

    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=8,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
        ],
    )

    max_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500000,
        validators=[
            MinValueValidator(0),
        ],
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Marketplace Settings"


class CheckoutSettings(SingletonModel):
    auto_confirm_orders = models.BooleanField(default=True)

    allow_cancellation = models.BooleanField(default=True)
    allow_order_notes = models.BooleanField(default=True)
    allow_seller_notes = models.BooleanField(default=True)

    cancellation_window = models.PositiveIntegerField(
        default=12,
        help_text="Hours",
    )

    return_window = models.PositiveIntegerField(
        default=7,
        help_text="Days",
    )

    order_number_format = models.CharField(
        max_length=50,
        default="MS-{YYYY}{#####}",
    )

    min_checkout_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
        ],
    )

    guest_checkout = models.BooleanField(default=False)

    require_email = models.BooleanField(default=True)
    require_phone = models.BooleanField(default=True)
    require_address = models.BooleanField(default=True)

    class TaxCalculation(models.TextChoices):
        NONE = "none", "None"
        EXCLUSIVE = "exclusive", "Exclusive"
        INCLUSIVE = "inclusive", "Inclusive"

    tax_calculation = models.CharField(
        max_length=20,
        choices=TaxCalculation.choices,
        default=TaxCalculation.NONE,
    )

    class ShippingCalculation(models.TextChoices):
        FLAT = "flat", "Flat"
        FREE = "free", "Free"
        DYNAMIC = "dynamic", "Dynamic"

    shipping_calculation = models.CharField(
        max_length=20,
        choices=ShippingCalculation.choices,
        default=ShippingCalculation.FLAT,
    )

    partial_orders = models.BooleanField(default=False)
    split_orders = models.BooleanField(default=True)

    backorders = models.BooleanField(default=False)
    preorders = models.BooleanField(default=False)

    order_hold = models.BooleanField(default=True)
    fraud_review = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Checkout Settings"


class CatalogSettings(SingletonModel):
    brand_visibility = models.BooleanField(default=True)
    search_visibility = models.BooleanField(default=True)

    maximum_product_images = models.PositiveSmallIntegerField(
        default=8,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(8),
        ],
    )

    maximum_image_size_mb = models.PositiveSmallIntegerField(
        default=5,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(100),
        ],
        help_text="Maximum product image size in MB.",
    )

    low_stock_threshold = models.PositiveIntegerField(
        default=5,
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Catalog Settings"


class NotificationSettings(SingletonModel):
    buyer_notifications = models.JSONField(default=dict)
    seller_notifications = models.JSONField(default=dict)
    admin_notifications = models.JSONField(default=dict)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Notification Settings"


class AdminSettingsData(SingletonModel):
    """Persistent storage for settings that do not have a dedicated model yet.

    The settings screen intentionally exposes a wider configuration surface than
    the typed models above. Keeping those values in one JSON document lets the
    screen save every field without introducing dozens of mostly-unused columns.
    Core sections are still mirrored to their typed models by the settings API.
    """

    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Admin Settings Data"