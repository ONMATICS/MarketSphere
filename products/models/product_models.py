from django.db import models
from django.db.models import Avg
from .base_models import TimeStampedModel
from .category_models import Category
from .brand_models import Brand


class Product(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        HIDDEN = "hidden", "Hidden"
        OUT_OF_STOCK = "out_of_stock", "Out of Stock"
        ARCHIVED = (
            "archived",
            "Archived",
        )
        PENDING = (
            "pending",
            "Pending",
        )
        REJECTED = (
            "rejected",
            "Rejected",
        )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )

    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )

    seller = models.ForeignKey(
        "accounts.Seller",
        on_delete=models.CASCADE,
        related_name="products",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    short_description = models.CharField(max_length=300, blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    sku = models.CharField(max_length=100, unique=True, null=True, blank=True)

    barcode = models.CharField(max_length=100, blank=True, null=True)

    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    stock_quantity = models.PositiveIntegerField(default=0)

    min_stock_level = models.PositiveIntegerField(default=5)

    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    promotions = models.ManyToManyField(
        "promotions.Promotion",
        through="promotions.PromotionProduct",
        related_name="products",
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_approved = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    admin_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first()  # type: ignore[attr-defined]

    @property
    def discount_percentage(self):
        if self.discount_price and self.price:
            return round(((self.price - self.discount_price) / self.price) * 100)
        return 0

    @property
    def average_rating(self):
        # Calculate the average rating from related reviews
        avg = self.reviews.aggregate(average=Avg('rating'))['average']
        return round(avg, 1) if avg is not None else 0.0
    
    @property
    def total_reviews(self):
        # Get total review count
        return self.reviews.count()

    @property
    def rating_stars(self):
        """Helper to generate full, half, and empty star CSS classes based on the average."""
        avg = self.average_rating
        stars = []
        for i in range(1, 6):
            if avg >= i:
                stars.append('bi-star-fill')
            elif avg >= i - 0.5:
                stars.append('bi-star-half')
            else:
                stars.append('bi-star')
        return stars

    def __str__(self):
        return self.name


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )

    # Cloudinary delivery URL. The field name is retained for compatibility
    # with the existing product/media code and templates.
    image = models.URLField(max_length=1000)

    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    media_type = models.CharField(
        max_length=10,
        choices=MediaType.choices,
        default=MediaType.IMAGE,
    )

    alt_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short description of the image for accessibility and SEO.",
    )

    is_primary = models.BooleanField(
        default=False, help_text="Used as the main image throughout the website."
    )

    display_order = models.PositiveSmallIntegerField(
        default=1, help_text="Lower numbers appear first."
    )

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"{self.product.name} - Image {self.display_order}"