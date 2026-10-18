from django.db.models import OuterRef, Subquery
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from accounts.models import Seller
from products import services as product_services
from products.models import Product
from promotions.models import Promotion, PromotionProduct


def promotion_detail(request: HttpRequest, promotion_slug: str) -> HttpResponse:
    """
    Render a public promotion landing page.
    
    Displays the promotion details, featured items, and a filtered/paginated grid 
    of all participating products annotated with their specific promotional pricing.
    """
    promotion = get_object_or_404(Promotion, slug=promotion_slug)

    is_upcoming = promotion.is_upcoming
    is_ended = promotion.is_ended
    is_active = promotion.is_running

    # Annotate products with promo_price so the product-card price block can
    # prefer the promotion price over the product's own discount_price
    # without requiring a second query per card during template rendering.
    promo_price_subquery = PromotionProduct.objects.filter(
        promotion=promotion, product=OuterRef("pk")
    ).values("promotion_price")[:1]
    
    promo_id_subquery = PromotionProduct.objects.filter(
        promotion=promotion, product=OuterRef("pk")
    ).values("id")[:1]

    base_products = (
        Product.objects.select_related("category", "brand")
        .prefetch_related("images")
        .filter(
            status=Product.Status.PUBLISHED,
            seller__status=Seller.Status.VERIFIED,
            promotion_products__promotion=promotion,
        )
        .distinct()
        .annotate(
            promo_price=Subquery(promo_price_subquery),
            promotion_product_id=Subquery(promo_id_subquery),
        )
    )

    product_count = promotion.product_count
    has_any_products = product_count > 0

    # Extract user filters from the GET request
    category_slugs = request.GET.getlist("category")
    brand_slugs = request.GET.getlist("brand")
    max_price = request.GET.get("max_price")
    availability = request.GET.getlist("availability")
    discount_only = request.GET.get("discount") == "1"
    sort_value = request.GET.get("sort", "newest")
    page_number = request.GET.get("page", 1)

    categories = promotion.get_display_categories()
    brands = product_services.get_search_brands(base_products)

    # Apply user filters
    filtered_products = product_services.filter_products(
        base_products,
        category_slugs=category_slugs,
        brand_slugs=brand_slugs,
        max_price=max_price,
        availability=availability,
        discount_only=discount_only,
    )
    
    # Sort annotated promotional pricing
    filtered_products = product_services.sort_products_by_price(
        filtered_products, sort_value, price_field="promo_price"
    )

    # Pagination handling
    paginator, page_obj = product_services.paginate_products(filtered_products, page_number)
    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)

    featured_promotion_products = promotion.featured_promotion_products(limit=4)

    context = {
        "promotion": promotion,
        "is_upcoming": is_upcoming,
        "is_active": is_active,
        "is_ended": is_ended,
        "product_count": product_count,
        "has_any_products": has_any_products,
        "featured_promotion_products": featured_promotion_products,
        "products": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": pagination_query,
        "categories": categories,
        "brands": brands,
        "selected_categories": category_slugs,
        "selected_brands": brand_slugs,
        "selected_availability": availability,
        "wishlist_ids": (
            product_services.get_wishlist_ids(request.user)
            if request.user.is_authenticated
            else set()
        ),
    }

    return render(request, "promotion_detail.html", context)
