from django.db import models


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