from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from products.models import Product, WishlistItem


def add_to_wishlist(user: Any, product_slug: str) -> WishlistItem:
    """Save a product to the user's personal wishlist."""
    product = get_object_or_404(Product, slug=product_slug, status=Product.Status.PUBLISHED)
    wishlist_item, _ = WishlistItem.objects.get_or_create(user=user, product=product)
    return wishlist_item


def remove_from_wishlist(user: Any, product_slug: str) -> bool:
    """Remove a product from the user's wishlist."""
    wishlist_item = WishlistItem.objects.filter(user=user, product__slug=product_slug).first()
    if wishlist_item:
        wishlist_item.delete()
        return True
    return False


def toggle_wishlist(user: Any, product_slug: str) -> bool:
    """Toggle wishlist presence, returning True if it was added, False if removed."""
    if is_in_wishlist(user, product_slug):
        remove_from_wishlist(user, product_slug)
        return False
    add_to_wishlist(user, product_slug)
    return True


def is_in_wishlist(user: Any, product_slug: str) -> bool:
    """Check if a product exists in a user's wishlist."""
    if not getattr(user, "is_authenticated", False):
        return False
    return WishlistItem.objects.filter(user=user, product__slug=product_slug).exists()


def get_wishlist_ids(user: Any) -> set[int]:
    """Return a set of raw product IDs currently saved by the user."""
    if user.is_authenticated:
        return set(WishlistItem.objects.filter(user=user).values_list("product_id", flat=True))
    return set()


def get_user_wishlist(user: Any) -> QuerySet[WishlistItem]:
    """Retrieve the fully populated wishlist entries for a user."""
    if not getattr(user, "is_authenticated", False):
        return WishlistItem.objects.none()
    return WishlistItem.objects.filter(user=user).select_related("product", "product__brand", "product__category")


def wishlist_count(user: Any) -> int:
    """Return the total number of items in a user's wishlist."""
    if not getattr(user, "is_authenticated", False):
        return 0
    return WishlistItem.objects.filter(user=user).count()