from django.db import models
from django.conf import settings
from .product_models import Product


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