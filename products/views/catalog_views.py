from django.db.models import Avg, Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render

from accounts.models import Seller
from admin_panel.catalog import categories_are_visible, get_catalog_settings
from admin_panel.marketplace import get_marketplace_settings
from products import services
from products.models import Brand, Category
from promotions.models import PromotionProduct
from promotions.services import get_current_homepage_promotion
from support import services as support_services


def home(request: HttpRequest) -> HttpResponse:
    """Render the main storefront homepage with featured products and categories."""
    homepage_promotion = get_current_homepage_promotion()
    marketplace_settings = get_marketplace_settings()
    catalog_settings = get_catalog_settings()

    categories = (
        services.get_all_categories() 
        if categories_are_visible() 
        else services.get_all_categories().none()
    )
    
    brands = (
        services.get_all_brands().filter(is_featured=True)
        if marketplace_settings.featured_brands and catalog_settings.brand_visibility
        else services.get_all_brands().none()
    )
    
    featured_products = (
        services.get_featured_products()
        if marketplace_settings.featured_products
        else services.get_featured_products().none()
    )
    
    featured_sellers = (
        Seller.objects.filter(status=Seller.Status.VERIFIED)
        .annotate(order_count=Count("orders"))
        .order_by("-order_count", "-created_at")[:8]
        if marketplace_settings.featured_sellers
        else Seller.objects.none()
    )
    
    new_products = services.get_new_products()
    
    context = {
        "categories": categories,
        "brands": brands,
        "featured_products": featured_products,
        "featured_sellers": featured_sellers,
        "show_featured_products": marketplace_settings.featured_products,
        "show_featured_brands": (
            marketplace_settings.featured_brands and catalog_settings.brand_visibility
        ),
        "show_featured_sellers": marketplace_settings.featured_sellers,
        "show_categories": categories_are_visible(),
        "new_products": new_products,
        "wishlist_ids": services.get_wishlist_ids(request.user),
        "homepage_promotion": homepage_promotion,
    }
    
    return render(request, "home.html", context)


def search(request: HttpRequest) -> HttpResponse:
    """Handle product search, filtering, and pagination."""
    catalog_settings = get_catalog_settings()
    q = request.GET.get("q", "").strip()
    category_slugs = request.GET.getlist("category")
    brand_slugs = request.GET.getlist("brand")
    max_price = request.GET.get("max_price")
    availability = request.GET.getlist("availability")
    discount_only = request.GET.get("discount") == "1"
    sort_value = request.GET.get("sort", "newest")
    page_number = request.GET.get("page", 1)
    rating_min = request.GET.get("rating_min")

    # Base set: query only.
    base_products = services.get_search_products(q)
    if not catalog_settings.search_visibility:
        base_products = base_products.none()
        
    featured = request.GET.get("featured") == "1"
    new_arrivals = request.GET.get("new_arrivals") == "1"
    
    if featured:
        base_products = base_products.filter(is_featured=True)
        if not get_marketplace_settings().featured_products:
            base_products = base_products.none()
        q = "Featured Products"
        
    if new_arrivals:
        base_products = base_products.order_by("-created_at")
        q = "New Arrivals"

    if q == "":
        q = (
            (category_slugs[0] if category_slugs else None)
            or (brand_slugs[0] if brand_slugs else None)
            or max_price
            or (availability[0] if availability else None)
            or sort_value
        )
        
    categories = services.get_search_categories(base_products)
    if not categories_are_visible():
        categories = categories.none()
        
    brands = services.get_search_brands(base_products)
    if not catalog_settings.brand_visibility:
        brands = brands.none()
        
    # Full set: query + every active filter
    filtered_products = services.filter_products(
        base_products,
        category_slugs=category_slugs,
        brand_slugs=brand_slugs,
        max_price=max_price,
        availability=availability,
        discount_only=discount_only,
    )
    
    if rating_min and rating_min.isdigit():
        filtered_products = filtered_products.annotate(
            annotated_avg_rating=Avg('reviews__rating')
        ).filter(annotated_avg_rating__gte=int(rating_min))

    filtered_products = services.sort_products(filtered_products, sort_value)

    paginator, page_obj = services.paginate_products(filtered_products, page_number)
    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)

    context = {
        "q": q,
        "products": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": pagination_query,
        "categories": categories,
        "brands": brands,
        "wishlist_ids": (
            services.get_wishlist_ids(request.user)
            if request.user.is_authenticated
            else set()
        ),
    }

    return render(request, "search_results.html", context)


def search_categories(request: HttpRequest) -> JsonResponse:
    """AJAX endpoint for searching active categories."""
    query = request.GET.get("q", "")

    if not get_catalog_settings().search_visibility:
        return JsonResponse({"categories": []})

    categories = Category.objects.filter(name__icontains=query).order_by("name")[:10]
    return JsonResponse({
        "categories": [
            {"name": category.name, "slug": category.slug} 
            for category in categories
        ]
    })


def search_brands(request: HttpRequest) -> JsonResponse:
    """AJAX endpoint for searching active brands."""
    query = request.GET.get("q", "")
    catalog_settings = get_catalog_settings()

    if not catalog_settings.search_visibility or not catalog_settings.brand_visibility:
        return JsonResponse({"brands": []})

    brands = Brand.objects.filter(name__icontains=query).order_by("name")[:10]
    return JsonResponse({
        "brands": [
            {"slug": brand.slug, "name": brand.name} 
            for brand in brands
        ]
    })


def product(request: HttpRequest, product_slug: str, promotion_slug: str = None) -> HttpResponse:
    """Render the individual product detail page."""
    product = services.get_product_by_slug(product_slug)
    promotion_product = None
    
    if promotion_slug:
        promotion_product = get_object_or_404(
            PromotionProduct.objects.select_related("promotion", "product"),
            promotion__slug=promotion_slug,
            product=product,
        )
        
    frequent_products = services.get_frequent_products(product)
    related_products = services.get_related_products(product)
    
    services.update_recently_viewed_products(request, product)
    recently_viewed_products = services.get_recently_viewed_products(request, product)

    page_number = request.GET.get('page', 1)
    reviews = support_services.get_product_reviews(product, page_number)
    review_distribution = support_services.get_review_distribution(product)

    context = {
        "product": product,
        "promotion_product": promotion_product,
        "frequent_products": frequent_products,
        "related_products": related_products,
        "recently_viewed_products": recently_viewed_products,
        "reviews": reviews, 
        "review_distribution": review_distribution,
        "is_in_wishlist": (
            services.is_in_wishlist(request.user, product.slug)
            if request.user.is_authenticated
            else False
        ),
        "wishlist_ids": (
            services.get_wishlist_ids(request.user)
            if request.user.is_authenticated
            else set()
        ),
    }
    return render(request, "product_details.html", context)