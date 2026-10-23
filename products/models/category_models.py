from django.db import models


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