from typing import Any

from orders.models import Order
from products.models import CartItem, Product
from products.services import get_or_create_cart

from .buyer_service import get_user_order


def add_to_cart(user: Any, product: Product, quantity: int = 1) -> CartItem:
    """Add a product to the user's cart or increment its quantity if it already exists."""
    cart = get_or_create_cart(user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": quantity},
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save(update_fields=["quantity", "updated_at"])

    return cart_item


def reorder_user_order(user: Any, order_number: str) -> Order | None:
    """Push the items of a previously delivered order back into the user's cart."""
    order = get_user_order(user, order_number)

    if order.status != Order.Status.DELIVERED:
        return None

    for item in order.items.select_related("product"):
        add_to_cart(user=user, product=item.product, quantity=item.quantity)

    return order