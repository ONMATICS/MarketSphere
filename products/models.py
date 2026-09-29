from django.db import models
from django.conf import settings


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# Create your models here.
# will be shifted to products app later
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )

    slug = models.SlugField(unique=True)

    description = models.TextField(blank=True)

    icon = models.CharField(
        max_length=50, blank=True, help_text="Bootstrap icon or Font Awesome class"
    )

    # Changed from ImageField to URLField for Cloudinary URLs
    image = models.CharField(max_length=1000, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def root_category(self):
        category = self

        while category.parent is not None:
            category = category.parent

        return category

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    # Changed from ImageField to URLField for Cloudinary URLs
    logo = models.CharField(max_length=1000, blank=True, null=True)

    # Changed from ImageField to URLField for Cloudinary URLs
    cover_image = models.CharField(max_length=1000, blank=True, null=True)

    description = models.TextField(blank=True)

    country_of_origin = models.CharField(
        max_length=100,
        blank=True,
    )

    founded_year = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    website = models.URLField(blank=True)

    official_email = models.EmailField(blank=True)

    official_phone = models.CharField(
        max_length=50,
        blank=True,
    )

    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    display_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


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


class WishlistItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="wishlisted_by"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_wishlist_item"
            )
        ]

    def __str__(self):
        return f"{self.user.username} → {self.product.name}"


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.username}'s Cart"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    promotion_product = models.ForeignKey(
        "promotions.PromotionProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cart_items",
    )

    quantity = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def subtotal(self):
        return self.product.price * self.quantity

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                condition=models.Q(promotion_product__isnull=True),
                name="unique_cart_product_normal",
            ),
            models.UniqueConstraint(
                fields=["cart", "product", "promotion_product"],
                condition=models.Q(promotion_product__isnull=False),
                name="unique_cart_product_promotion",
            )
        ]

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"
