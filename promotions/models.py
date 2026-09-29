from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class PromotionQuerySet(models.QuerySet):
    """
    Centralizes the "is this promotion actually visible right now" check
    so views/templates never have to re-derive
    `status == ACTIVE and start_at <= now <= end_at` by hand.
    """

    def visible(self):
        now = timezone.now()
        return self.filter(
            status=Promotion.Status.ACTIVE,
            start_at__lte=now,
            end_at__gt=now,
        )

    def upcoming(self):
        now = timezone.now()
        return self.filter(status=Promotion.Status.ACTIVE, start_at__gt=now)

    def ended(self):
        now = timezone.now()
        return self.filter(end_at__lt=now)

    def for_homepage(self):
        return self.visible().filter(display_on_homepage=True).order_by(
            "homepage_priority", "-created_at"
        )


class Promotion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=150)

    slug = models.SlugField(
        max_length=180,
        unique=True,
        blank=True,
    )

    # Small pill shown in the hero (e.g. "Flash Sale", "Coming Soon").
    # Left blank, the template falls back to a state-derived default
    # ("Limited-Time Offer" / "Coming Soon" / "Promotion Ended").
    badge_text = models.CharField(
        max_length=60,
        blank=True,
        help_text="Optional hero badge override, e.g. 'Flash Sale'. Leave "
        "blank to use the default label for the promotion's current state.",
    )

    short_description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Hero subheading / one-line pitch.",
    )

    description = models.TextField(
        blank=True,
        help_text="Longer copy — used lower on the page if the template needs it.",
    )

    # Full-bleed hero banner.
    banner = models.CharField(max_length=1000, blank=True, null=True)

    # Smaller crop for homepage promo cards; falls back to `banner` in
    # the template/service layer when not set.
    thumbnail = models.CharField(max_length=1000, blank=True, null=True)

    start_at = models.DateTimeField()

    end_at = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    maximum_discount_percentage = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(100),
        ],
        null=True,
        blank=True,
    )

    # Curated "Shop the Sale" categories, independently orderable from
    # whatever categories the attached products happen to belong to.
    # If empty, get_display_categories() derives them from
    # promotion_products instead.
    categories = models.ManyToManyField(
        "products.Category",
        related_name="promotions",
        blank=True,
    )

    display_on_homepage = models.BooleanField(
        default=False,
    )

    homepage_priority = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = PromotionQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"

        indexes = [
            models.Index(
                fields=["status", "start_at", "end_at"],
                name="promotion_status_dates_idx",
            ),
            models.Index(
                fields=["display_on_homepage", "homepage_priority"],
                name="promotion_homepage_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="promotion_end_after_start",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while (
                Promotion.objects.exclude(pk=self.pk)
                .filter(slug=slug)
                .exists()
            ):
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("promotion_detail", kwargs={"promotion_slug": self.slug})

    @property
    def is_upcoming(self):
        return self.status == self.Status.ACTIVE and timezone.now() < self.start_at

    @property
    def is_ended(self):
        return timezone.now() > self.end_at

    @property
    def is_running(self):
        now = timezone.now()
        return (
            self.status == self.Status.ACTIVE
            and self.start_at <= now < self.end_at
        )

    # Kept as an alias since existing code/templates may already
    # reference `is_visible`.
    @property
    def is_visible(self):
        return self.is_running

    @property
    def discount_text(self):
        """Hero headline text, e.g. 'Up to 50% Off'. Returns '' when no
        maximum discount has been configured, so templates can safely
        `{% if promotion.discount_text %}` around it."""
        if not self.maximum_discount_percentage:
            return ""
        return f"Up to {self.maximum_discount_percentage}% Off"

    @property
    def product_count(self):
        return self.promotion_products.count()

    def get_display_categories(self):
        """Curated categories if the admin picked any; otherwise derive
        the distinct categories of the products actually attached to
        this promotion."""
        curated = list(self.categories.filter(is_active=True))
        if curated:
            return curated

        from products.models import Category

        return list(
            Category.objects.filter(
                products__promotion_products__promotion=self,
                is_active=True,
            ).distinct()
        )

    def featured_promotion_products(self, limit=4):
        featured = list(
            self.promotion_products.filter(is_featured=True).select_related(
                "product", "product__brand", "product__category"
            )[:limit]
        )
        if len(featured) < limit:
            featured = list(
                self.promotion_products.select_related(
                    "product", "product__brand", "product__category"
                ).order_by("display_order", "-created_at")[:limit]
            )
        return featured


class PromotionProduct(models.Model):
    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.CASCADE,
        related_name="promotion_products",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="promotion_products",
    )

    promotion_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
        ],
    )

    is_featured = models.BooleanField(
        default=False,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["display_order", "-created_at"]
        verbose_name = "Promotion Product"
        verbose_name_plural = "Promotion Products"

        constraints = [
            models.UniqueConstraint(
                fields=["promotion", "product"],
                name="unique_promotion_product",
            ),
        ]

        indexes = [
            models.Index(
                fields=["promotion", "is_featured", "display_order"],
                name="promotion_product_featured_idx",
            ),
        ]

    def __str__(self):
        return f"{self.promotion.name} - {self.product.name}"

    def clean(self):
        # NOTE: self.product may be unset if called before the FK is
        # assigned (e.g. from a ModelForm with a missing field) —
        # guard against that rather than letting it raise DoesNotExist.
        if self.product_id and self.promotion_price is not None:
            original_price = self.original_price
            if original_price and self.promotion_price >= original_price:
                raise ValidationError(
                    {
                        "promotion_price": (
                            "Promotion price must be lower than the "
                            "product's regular price."
                        )
                    }
                )

    @property
    def original_price(self):
        return self.product.price

    @property
    def discount_percentage(self):
        original_price = self.original_price

        if not original_price or original_price <= 0:
            return Decimal("0")

        discount = (
            (original_price - self.promotion_price)
            / original_price
        ) * Decimal("100")

        return discount.quantize(Decimal("0.01"))

    @property
    def savings_amount(self):
        original_price = self.original_price

        if not original_price:
            return Decimal("0.00")

        savings = original_price - self.promotion_price
        return savings if savings > 0 else Decimal("0.00")
