from .services import get_all_categories, get_all_brands, wishlist_count, cart_count
from admin_panel.catalog import categories_are_visible, get_catalog_settings



def categories(request):
    user = request.user

    return {
        "categories": get_all_categories() if categories_are_visible() else get_all_categories().none(),
        "category_visibility": categories_are_visible(),
        "brands": (
            get_all_brands()
            if get_catalog_settings().brand_visibility
            else get_all_brands().none()
        ),
        "wishlist_count": wishlist_count(user) if user.is_authenticated else 0,
        "cart_count": cart_count(user) if user.is_authenticated else 0,
    }
