from django.shortcuts import render
from . import services
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Count
from accounts.models import Seller
from admin_panel.marketplace import get_marketplace_settings
from admin_panel.catalog import categories_are_visible, get_catalog_settings
from promotions.services import get_current_homepage_promotion
from promotions.models import PromotionProduct

# Create your views here.
def home(request):
    homepage_promotion = get_current_homepage_promotion()
    marketplace_settings = get_marketplace_settings()
    catalog_settings = get_catalog_settings()
    categories = services.get_all_categories() if categories_are_visible() else services.get_all_categories().none()
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
            marketplace_settings.featured_brands
            and catalog_settings.brand_visibility
        ),
        "show_featured_sellers": marketplace_settings.featured_sellers,
        "show_categories": categories_are_visible(),
        "new_products": new_products,
        "wishlist_ids": services.get_wishlist_ids(request.user),
        "homepage_promotion": homepage_promotion,
    }
    return render(request, "home.html", context)


from django.shortcuts import render
from django.http import JsonResponse

from . import services


def search(request):
    catalog_settings = get_catalog_settings()
    q = request.GET.get("q", "").strip()
    category_slugs = request.GET.getlist("category")
    brand_slugs = request.GET.getlist("brand")
    max_price = request.GET.get("max_price")
    availability = request.GET.getlist("availability")
    discount_only = request.GET.get("discount") == "1"
    sort_value = request.GET.get("sort", "newest")
    page_number = request.GET.get("page", 1)

    # Base set: query only. Sidebar options are computed from THIS,
    # so the sidebar doesn't shrink as filters are applied.
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
    # Full set: query + every active filter, for the actual grid.
    filtered_products = services.filter_products(
        base_products,
        category_slugs=category_slugs,
        brand_slugs=brand_slugs,
        max_price=max_price,
        availability=availability,
        discount_only=discount_only,
    )
    filtered_products = services.sort_products(filtered_products, sort_value)

    paginator, page_obj = services.paginate_products(filtered_products, page_number)
    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)

    context = {
        "q": q,
        "products": page_obj,  # Page objects support |length and iteration
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


from products.models import Category


def search_categories(request):

    query = request.GET.get("q", "")

    if not get_catalog_settings().search_visibility:
        return JsonResponse({"categories": []})

    categories = Category.objects.filter(name__icontains=query).order_by("name")[:10]

    return JsonResponse(
        {
            "categories": [
                {
                    "name": category.name,
                    "slug": category.slug,
                }
                for category in categories
            ]
        }
    )


from django.http import JsonResponse

from products.models import Brand


def search_brands(request):

    query = request.GET.get("q", "")
    catalog_settings = get_catalog_settings()

    if not catalog_settings.search_visibility or not catalog_settings.brand_visibility:
        return JsonResponse({"brands": []})

    brands = Brand.objects.filter(name__icontains=query).order_by("name")[:10]

    data = []

    for brand in brands:

        data.append(
            {
                "slug": brand.slug,
                "name": brand.name,
            }
        )

    return JsonResponse({"brands": data})

from support import services as support_services
def product(request, product_slug, promotion_slug=None):
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
    recently_viewed_products = services.get_recently_viewed_products(
        request,
        product,
    )

    # --- Fetch Product Reviews with Pagination ---
    page_number = request.GET.get('page', 1)
    reviews = support_services.get_product_reviews(product, page_number)
    
    # --- NEW: Get Review Distribution for Progress Bars ---
    review_distribution = support_services.get_review_distribution(product)

    context = {
        "product": product,
        "promotion_product": promotion_product,
        "frequent_products": frequent_products,
        "related_products": related_products,
        "recently_viewed_products": recently_viewed_products,
        "reviews": reviews, 
        "review_distribution": review_distribution, # Passed to the template
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

from django.core.exceptions import PermissionDenied

from products.models import Product
from .product_pdf import export_product_report
from django.shortcuts import get_object_or_404


@login_required
def export_product_pdf(request, slug):
    if not request.user.is_staff:
        raise PermissionDenied

    product = get_object_or_404(
        Product.objects.select_related(
            "category",
            "brand",
            "seller",
        ).prefetch_related(
            "images",
            "order_items__seller_order__order",
        ),
        slug=slug,
    )

    return export_product_report(
        product=product,
        admin_user=request.user,
    )


def export_product_orders_view(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("seller", "category", "brand"),
        slug=slug,
    )

    return services.export_product_orders(product)


@login_required
def wishlist(request):
    wishlist_items = services.get_user_wishlist(request.user)

    context = {
        "wishlist_products": wishlist_items,
        "wishlist_count": services.wishlist_count(request.user),
    }

    return render(request, "wishlist.html", context)


@login_required
def toggle_wishlist(request, product_slug):
    is_added = services.toggle_wishlist(request.user, product_slug)

    return JsonResponse(
        {
            "success": True,
            "is_added": is_added,
            "wishlist_count": services.wishlist_count(request.user),
        }
    )


from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404

from accounts.models import Seller


# @staff_member_required
def export_products_csv(request, seller_id):
    seller = get_object_or_404(Seller, id=seller_id)
    return services.export_products_csv(seller)


@login_required
def cart(request):
    cart = services.get_user_cart(request.user)
    totals = services.get_cart_totals(request.user)
    pricing_by_id = {item.id: pricing for item, pricing in totals["pricing"]}
    for item in cart.items.all():
        item.pricing = pricing_by_id[item.id]

    context = {
        "cart": cart,
        "cart_count": services.cart_count(request.user),
        "subtotal": totals["subtotal"],
        "total": totals["total"],
        "original_subtotal": totals["original_subtotal"],
        "shipping_cost": totals["shipping_fee"],
        "discount": totals["discount"],
        "cart_pricing": totals["pricing"],
        "promotion_ended": totals["promotion_ended"],
    }

    return render(request, "cart.html", context)


@login_required
def add_to_cart(request, product_slug):
    try:
        cart_item = services.add_to_cart(
            request.user,
            product_slug,
            request.GET.get("promotion_product_id") or request.POST.get("promotion_product_id"),
            request.GET.get("quantity") or request.POST.get("quantity") or 1,
        )
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
    totals = services.get_cart_totals(request.user)

    return JsonResponse(
        {
            "success": True,
            "quantity": cart_item.quantity,
            "cart_item_id": cart_item.id,
            "cart_count": services.cart_count(request.user),
            "subtotal": str(totals["subtotal"]),
            "discount": str(totals["discount"]),
            "total": str(totals["total"]),
        }
    )


def add_frequently_bought_products_view(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request.",
            },
            status=405,
        )

    cart = services.add_frequently_bought_products(
        request.user,
        request.body,
    )

    return JsonResponse(
        {
            "success": True,
            "cart_count": services.cart_count(request.user),
        }
    )


@login_required
def remove_from_cart(request, product_slug):
    success = services.remove_from_cart(request.user, product_slug)

    return JsonResponse(
        {
            "success": success,
            "cart_count": services.cart_count(request.user),
            "subtotal": str(services.cart_subtotal(request.user)),
            "total": str(services.cart_total(request.user)),
        }
    )


@login_required
def increment_quantity(request, product_slug):
    print("esssss")
    cart_item = services.increment_quantity(request.user, product_slug)

    return JsonResponse(
        {
            "success": True,
            "quantity": cart_item.quantity,
            "item_subtotal": str(services.get_cart_item_pricing(cart_item)["line_subtotal"]),
            "cart_count": services.cart_count(request.user),
            "subtotal": str(services.cart_subtotal(request.user)),
            "total": str(services.cart_total(request.user)),
        }
    )


@login_required
def decrement_quantity(request, product_slug):
    cart_item = services.decrement_quantity(request.user, product_slug)

    if cart_item is None:
        return JsonResponse(
            {
                "success": True,
                "removed": True,
                "cart_count": services.cart_count(request.user),
                "subtotal": str(services.cart_subtotal(request.user)),
                "total": str(services.cart_total(request.user)),
            }
        )

    return JsonResponse(
        {
            "success": True,
            "removed": False,
            "quantity": cart_item.quantity,
            "item_subtotal": str(services.get_cart_item_pricing(cart_item)["line_subtotal"]),
            "cart_count": services.cart_count(request.user),
            "subtotal": str(services.cart_subtotal(request.user)),
            "total": str(services.cart_total(request.user)),
        }
    )


@login_required
def update_quantity(request, product_slug):
    import json

    quantity = json.loads(request.body or b"{}").get("quantity")
    cart_item = services.update_quantity(
        request.user,
        product_slug,
        quantity,
    )

    if cart_item is None:
        return JsonResponse(
            {
                "success": True,
                "removed": True,
                "cart_count": services.cart_count(request.user),
                "subtotal": str(services.cart_subtotal(request.user)),
                "total": str(services.cart_total(request.user)),
            }
        )

    return JsonResponse(
        {
            "success": True,
            "removed": False,
            "quantity": cart_item.quantity,
            "item_subtotal": str(services.get_cart_item_pricing(cart_item)["line_subtotal"]),
            "cart_count": services.cart_count(request.user),
            "subtotal": str(services.cart_subtotal(request.user)),
            "total": str(services.cart_total(request.user)),
        }
    )


@login_required
def clear_cart(request):
    services.clear_cart(request.user)

    return JsonResponse(
        {
            "success": True,
            "cart_count": 0,
            "subtotal": "0.00",
            "total": "0.00",
        }
    )


@login_required
def cart_data(request):
    cart = services.get_user_cart(request.user)
    totals = services.get_cart_totals(request.user)

    return JsonResponse(
        {
            "cart": cart,
            "cart_count": services.cart_count(request.user),
            "subtotal": str(totals["subtotal"]),
            "discount": str(totals["discount"]),
            "total": str(totals["total"]),
        }
    )
