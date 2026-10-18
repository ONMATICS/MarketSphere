import json
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import Seller
from products.models import Cart, CartItem, Product
from promotions.models import Promotion, PromotionProduct


def get_or_create_cart(user: Any) -> Cart:
    """Retrieve or initialize an active shopping cart for a user."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _promotion_product_for_purchase(product: Product, promotion_product_id: int | str | None = None) -> PromotionProduct | None:
    """Resolve and validate active promotional contexts for an intended purchase."""
    if not promotion_product_id:
        return None
    try:
        promotion_product_id = int(promotion_product_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid promotion context.")
    try:
        promotion_product = PromotionProduct.objects.select_related(
            "promotion", "product", "product__seller"
        ).get(id=promotion_product_id, product=product)
    except PromotionProduct.DoesNotExist:
        raise ValueError("This product is not part of the selected promotion.")

    now = timezone.now()
    promotion = promotion_product.promotion
    if not (promotion.status == Promotion.Status.ACTIVE and promotion.start_at <= now < promotion.end_at):
        raise ValueError("This promotion is no longer available.")
    if product.status != Product.Status.PUBLISHED:
        raise ValueError("This product is no longer available.")
    if not product.seller or product.seller.status != Seller.Status.VERIFIED:
        raise ValueError("This seller is not currently verified.")
    if not product.price or promotion_product.promotion_price >= product.price:
        raise ValueError("This promotion price is no longer valid.")
    
    return promotion_product


def get_promotion_product_for_purchase(product: Product, promotion_product_id: int | str) -> PromotionProduct | None:
    """Public wrapper to validate promotion logic for checkout contexts."""
    return _promotion_product_for_purchase(product, promotion_product_id)


def get_cart_item_pricing(cart_item: CartItem, refresh_promotion: bool = True) -> dict[str, Any]:
    """Calculate and return authoritative money values for a specific cart line."""
    product = cart_item.product
    original_price = Decimal(product.price or "0.00")
    promotion_ended = False
    promotion_product = cart_item.promotion_product

    if promotion_product:
        try:
            promotion_product = _promotion_product_for_purchase(product, promotion_product.id)
        except ValueError:
            promotion_product = None
            promotion_ended = True
            if refresh_promotion:
                cart_item.promotion_product = None
                cart_item.save(update_fields=["promotion_product", "updated_at"])

    effective_price = (
        Decimal(promotion_product.promotion_price)
        if promotion_product
        else Decimal(product.discount_price or product.price or "0.00")
    )
    quantity = int(cart_item.quantity or 0)
    discount_per_unit = max(Decimal("0.00"), original_price - effective_price) if promotion_product else Decimal("0.00")
    
    return {
        "original_price": original_price,
        "effective_price": effective_price,
        "discount_per_unit": discount_per_unit,
        "discount_amount": discount_per_unit * quantity,
        "quantity": quantity,
        "line_subtotal": effective_price * quantity,
        "promotion_ended": promotion_ended,
        "promotion_product": promotion_product,
        "is_promotion": bool(promotion_product),
    }


def get_cart_totals(user: Any, cart_items: QuerySet[CartItem] | None = None) -> dict[str, Any]:
    """Calculate absolute totals and shipping distributions across a user's cart."""
    cart = get_or_create_cart(user)
    items = cart_items if cart_items is not None else cart.items.select_related(
        "product", "product__seller", "product__seller__settings", "promotion_product__promotion"
    )

    original_subtotal = Decimal("0.00")
    discount = Decimal("0.00")
    shipping_fee = Decimal("0.00")
    payable_subtotal = Decimal("0.00")

    pricing = []
    promotion_ended = False
    shipping_sellers = set()

    for item in items:
        line = get_cart_item_pricing(item)
        item.pricing = line

        original_subtotal += (line["original_price"] if line["is_promotion"] else line["effective_price"]) * line["quantity"]
        discount += line["discount_amount"]
        payable_subtotal += line["line_subtotal"]
        promotion_ended = promotion_ended or line["promotion_ended"]

        seller = item.product.seller
        if seller and seller.id not in shipping_sellers:
            shipping_fee += seller.settings.shipping_fee
            shipping_sellers.add(seller.id)

        pricing.append((item, line))

    total = payable_subtotal + shipping_fee

    return {
        "original_subtotal": original_subtotal,
        "discount": discount,
        "subtotal": payable_subtotal,
        "shipping_fee": shipping_fee,
        "total": total,
        "pricing": pricing,
        "promotion_ended": promotion_ended,
    }


def add_to_cart(user: Any, product_slug: str, promotion_product_id: int | str | None = None, quantity: int | str = 1) -> CartItem:
    """Add a product securely to a user's cart."""
    product = get_object_or_404(Product.objects.select_related("seller"), slug=product_slug, status=Product.Status.PUBLISHED)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a positive number.")
    if quantity < 1:
        raise ValueError("Quantity must be a positive number.")
        
    promotion_product = _promotion_product_for_purchase(product, promotion_product_id)
    if product.stock_quantity < quantity:
        raise ValueError(f"Only {product.stock_quantity} units of '{product.name}' are available.")
        
    cart = get_or_create_cart(user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, promotion_product=promotion_product, defaults={"quantity": quantity}
    )

    if not created:
        next_quantity = (cart_item.quantity or 0) + quantity
        if product.stock_quantity < next_quantity:
            raise ValueError(f"Only {product.stock_quantity} units of '{product.name}' are available.")
        cart_item.quantity = next_quantity
        cart_item.save()
        
    return cart_item


def add_frequently_bought_products(user: Any, body: str | bytes) -> Cart:
    """Bulk-add suggested products to the user's cart from a JSON payload."""
    data = json.loads(body)
    product_ids = data.get("products", [])
    cart, _ = Cart.objects.get_or_create(user=user)

    for product_id in product_ids:
        try:
            product = Product.objects.get(id=int(product_id), status=Product.Status.PUBLISHED)
            cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": 1})
            if not created:
                cart_item.quantity += 1
                cart_item.save(update_fields=["quantity", "updated_at"])
        except (Product.DoesNotExist, ValueError, TypeError):
            continue

    return cart


def remove_from_cart(user: Any, product_slug: str) -> bool:
    """Remove a product entirely from the user's cart."""
    cart = get_or_create_cart(user)
    cart_item = CartItem.objects.filter(cart=cart, product__slug=product_slug).first()
    if cart_item:
        cart_item.delete()
        return True
    return False


def update_quantity(user: Any, product_slug: str, quantity: int | str) -> CartItem | None:
    """Override a product's exact cart quantity, deleting if set below 1."""
    cart = get_or_create_cart(user)
    cart_item = CartItem.objects.filter(cart=cart, product__slug=product_slug).first()
    if not cart_item:
        return None

    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        return None

    if qty <= 0:
        cart_item.delete()
        return None

    cart_item.quantity = qty
    cart_item.save()
    return cart_item


def increment_quantity(user: Any, product_slug: str) -> CartItem:
    """Increase a cart item quantity by one, subject to stock constraints."""
    cart = get_or_create_cart(user)
    cart_item = CartItem.objects.filter(cart=cart, product__slug=product_slug).first()
    if not cart_item:
        return add_to_cart(user, product_slug)
        
    if cart_item.product.stock_quantity < (cart_item.quantity or 0) + 1:
        raise ValueError(f"Only {cart_item.product.stock_quantity} units of '{cart_item.product.name}' are available.")
        
    cart_item.quantity = (cart_item.quantity or 0) + 1
    cart_item.save(update_fields=["quantity", "updated_at"])
    return cart_item


def decrement_quantity(user: Any, product_slug: str) -> CartItem | None:
    """Decrease a cart item quantity by one, deleting if dropping below 1."""
    cart = get_or_create_cart(user)
    cart_item = CartItem.objects.filter(cart=cart, product__slug=product_slug).first()
    if not cart_item:
        return None

    if (cart_item.quantity or 0) <= 1:
        cart_item.delete()
        return None

    cart_item.quantity -= 1
    cart_item.save()
    return cart_item


def clear_cart(user: Any) -> bool:
    """Empty the user's cart entirely."""
    cart = get_or_create_cart(user)
    CartItem.objects.filter(cart=cart).delete()
    return True


def cart_total(user: Any) -> Decimal:
    """Return the calculated final total string/decimal for a user's cart."""
    return get_cart_totals(user)["total"]


def cart_subtotal(user: Any) -> Decimal:
    """Return the original undiscounted subtotal for a user's cart."""
    return get_cart_totals(user)["original_subtotal"]


def cart_count(user: Any) -> int:
    """Calculate the absolute number of items in a user's cart."""
    cart = get_or_create_cart(user)
    return CartItem.objects.filter(cart=cart).aggregate(total_quantity=Sum("quantity"))["total_quantity"] or 0


def get_user_cart(user: Any) -> Cart | None:
    """Retrieve the populated user cart object."""
    if not getattr(user, "is_authenticated", False):
        return None
    return Cart.objects.filter(user=user).prefetch_related("items__product", "items__promotion_product__promotion").first()