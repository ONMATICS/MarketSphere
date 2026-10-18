from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.paginator import Page, Paginator
from django.db.models import IntegerField, Prefetch, Q, Sum, QuerySet
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404

from accounts.models import Seller
from admin_panel.catalog import get_catalog_settings
from orders.models import Order
from products.models import Brand, Category, Product


def get_all_categories() -> QuerySet[Category]:
    """Retrieve all active root categories with their nested active children."""
    return Category.objects.filter(parent=None, is_active=True).prefetch_related(
        Prefetch(
            "children",
            queryset=Category.objects.filter(is_active=True).prefetch_related(
                Prefetch("children", queryset=Category.objects.filter(is_active=True))
            ),
        )
    )


def get_all_brands() -> QuerySet[Brand]:
    """Retrieve all active brands."""
    return Brand.objects.filter(is_active=True).all()


def get_featured_products() -> QuerySet[Product]:
    """Retrieve all featured, published products from verified sellers."""
    return (
        Product.objects.select_related("category", "brand")
        .prefetch_related("images")
        .annotate(
            total_sold=Coalesce(
                Sum("order_items__quantity", filter=Q(order_items__order__status=Order.Status.DELIVERED)),
                0,
                output_field=IntegerField(),
            )
        )
        .filter(status=Product.Status.PUBLISHED, is_featured=True, seller__status=Seller.Status.VERIFIED)
    )


def get_new_products(limit: int = 8) -> QuerySet[Product]:
    """Retrieve the most recently added published products."""
    return (
        Product.objects.select_related("category", "brand", "seller")
        .prefetch_related("images")
        .annotate(
            total_sold=Coalesce(
                Sum("order_items__quantity", filter=Q(order_items__order__status=Order.Status.DELIVERED)),
                0,
                output_field=IntegerField(),
            )
        )
        .filter(status=Product.Status.PUBLISHED, seller__status=Seller.Status.VERIFIED)
        .order_by("-created_at")[:limit]
    )


def get_frequent_products(product: Product) -> QuerySet[Product]:
    """Retrieve up to two other products from the same category and seller."""
    return Product.objects.filter(
        category=product.category, seller=product.seller, status=Product.Status.PUBLISHED
    ).exclude(id=product.id)[:2]


def get_related_products(product: Product) -> QuerySet[Product]:
    """Retrieve all other products from the same category and seller."""
    return Product.objects.filter(
        category=product.category, seller=product.seller, status=Product.Status.PUBLISHED
    ).exclude(id=product.id)


def get_product_by_slug(product_slug: str) -> Product:
    """Retrieve a published product by its slug."""
    return get_object_or_404(
        Product.objects.select_related("category", "brand").prefetch_related("images"),
        slug=product_slug,
        status=Product.Status.PUBLISHED,
    )


def get_edit_product_by_slug(product_slug: str, seller: Seller) -> Product:
    """Retrieve a product by its slug for a specific seller, disregarding its publication status."""
    return get_object_or_404(
        Product.objects.select_related("category", "brand").prefetch_related("images"),
        slug=product_slug,
        seller=seller,
    )


def get_brand_products(brand_slug: str) -> QuerySet[Product]:
    """Retrieve all published products associated with a specific brand slug."""
    return (
        Product.objects.select_related("brand", "category")
        .prefetch_related("images")
        .filter(brand__slug=brand_slug, status=Product.Status.PUBLISHED)
    )


def get_category_products(category_slug: str) -> QuerySet[Product]:
    """Retrieve all published products associated with a specific category slug."""
    return (
        Product.objects.select_related("brand", "category")
        .prefetch_related("images")
        .filter(category__slug=category_slug, status=Product.Status.PUBLISHED)
    )


def get_recently_viewed_products(request: Any, current_product: Product, limit: int = 8) -> list[Product]:
    """Retrieve a user's recently viewed products from their session."""
    recently_viewed_ids = request.session.get("recently_viewed", [])

    products = list(
        Product.objects.select_related("category", "brand", "seller")
        .prefetch_related("images")
        .filter(
            id__in=recently_viewed_ids,
            status=Product.Status.PUBLISHED,
            seller__status=Seller.Status.VERIFIED,
        )
        .exclude(id=current_product.id)
    )

    products.sort(key=lambda p: recently_viewed_ids.index(p.id) if p.id in recently_viewed_ids else 999)
    return products[:limit]


def update_recently_viewed_products(request: Any, product: Product) -> None:
    """Prepend the given product to the user's session history."""
    recently_viewed = request.session.get("recently_viewed", [])

    if product.id in recently_viewed:
        recently_viewed.remove(product.id)

    recently_viewed.insert(0, product.id)
    recently_viewed = recently_viewed[:10]

    request.session["recently_viewed"] = recently_viewed
    request.session.modified = True


def get_search_products(q: str) -> QuerySet[Product]:
    """Query the catalog for products matching a search string."""
    if not q:
        return Product.objects.all()

    return (
        Product.objects.select_related("category", "brand")
        .prefetch_related("images")
        .filter(
            Q(name__icontains=q) | Q(short_description__icontains=q) | Q(description__icontains=q),
            status=Product.Status.PUBLISHED,
        )
    )


def filter_products(
    products: QuerySet[Product],
    category_slugs: list[str] | None = None,
    brand_slugs: list[str] | None = None,
    max_price: str | Decimal | None = None,
    availability: list[str] | None = None,
    discount_only: bool = False,
) -> QuerySet[Product]:
    """Apply category, brand, pricing, and availability filters to a product queryset."""
    if category_slugs:
        products = products.filter(category__slug__in=category_slugs)

    if brand_slugs:
        products = products.filter(brand__slug__in=brand_slugs)

    if max_price:
        try:
            max_price = Decimal(max_price)
            products = products.filter(
                Q(discount_price__isnull=False, discount_price__lte=max_price)
                | Q(discount_price__isnull=True, price__lte=max_price)
            )
        except (InvalidOperation, TypeError):
            pass

    if availability:
        avail_q = Q()
        if "in_stock" in availability:
            avail_q |= Q(stock_quantity__gt=0)
        if "out_of_stock" in availability:
            avail_q |= Q(stock_quantity=0)
        if avail_q:
            products = products.filter(avail_q)

    if discount_only:
        products = products.filter(discount_price__isnull=False)

    return products


def sort_products(products: QuerySet[Product], sort_value: str) -> QuerySet[Product]:
    """Sort a product queryset based on a frontend string constant."""
    return sort_products_by_price(products, sort_value)


def sort_products_by_price(products: QuerySet[Product], sort_value: str, price_field: str | None = None) -> QuerySet[Product]:
    """Apply specific price or popularity sorting logic."""
    effective_price = (
        Coalesce(price_field, "discount_price", "price")
        if price_field
        else Coalesce("discount_price", "price")
    )

    if sort_value == "price_low_high":
        return products.order_by(effective_price)
    if sort_value == "price_high_low":
        return products.order_by(effective_price.desc())
    
    return products.order_by("-created_at")


def paginate_products(products: QuerySet[Product], page_number: int, per_page: int = 12) -> tuple[Paginator, Page]:
    """Generate pagination context for product lists."""
    paginator = Paginator(products, per_page)
    return paginator, paginator.get_page(page_number)


def get_search_categories(products: QuerySet[Product]) -> QuerySet[Category]:
    """Extract distinct active categories intersecting a search result."""
    return Category.objects.filter(products__in=products, is_active=True).distinct()[:5]


def get_search_brands(products: QuerySet[Product]) -> QuerySet[Brand]:
    """Extract distinct active brands intersecting a search result, obeying global settings."""
    if not get_catalog_settings().brand_visibility:
        return Brand.objects.none()
    return Brand.objects.filter(products__in=products, is_active=True).distinct()[:5]