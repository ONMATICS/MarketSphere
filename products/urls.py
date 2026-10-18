from django.urls import path

from .views import (
    cart_views,
    catalog_views,
    export_views,
    review_views,
    wishlist_views,
)

urlpatterns = [
    # Catalog / Browsing
    path("", catalog_views.home, name="home"),
    path("search", catalog_views.search, name="search"),
    path("api/search-brands/", catalog_views.search_brands, name="search_brands"),
    path("api/search-categories/", catalog_views.search_categories, name="search_categories"),
    path("product/<slug:product_slug>/", catalog_views.product, name="product"),
    path(
        "promotions/<slug:promotion_slug>/products/<slug:product_slug>/",
        catalog_views.product,
        name="promotion_product",
    ),

    # Reviews
    path(
        "reviews/<int:review_id>/helpful/",
        review_views.mark_review_helpful_api,
        name="mark_review_helpful_api",
    ),

    # Wishlist
    path("wishlist/", wishlist_views.wishlist, name="wishlist"),
    path(
        "wishlist/toggle/<slug:product_slug>/",
        wishlist_views.toggle_wishlist,
        name="toggle_wishlist",
    ),

    # Cart
    path("cart/", cart_views.cart, name="cart"),
    path("cart/data/", cart_views.cart_data, name="cart_data"),
    path("cart/clear/", cart_views.clear_cart, name="clear_cart"),
    path(
        "cart/add-frequently-bought/",
        cart_views.add_frequently_bought_products_view,
        name="add-frequently-bought",
    ),
    path("cart/add/<slug:product_slug>/", cart_views.add_to_cart, name="add_to_cart"),
    path("cart/decrement/<slug:product_slug>/", cart_views.decrement_quantity, name="decrement_quantity"),
    path("cart/increment/<slug:product_slug>/", cart_views.increment_quantity, name="increment_quantity"),
    path("cart/remove/<slug:product_slug>/", cart_views.remove_from_cart, name="remove_from_cart"),
    path("cart/update/<slug:product_slug>/", cart_views.update_quantity, name="update_quantity"),

    # Exports
    path(
        "products/<slug:slug>/export-orders/",
        export_views.export_product_orders_view,
        name="export_product_orders",
    ),
    path(
        "products/<slug:slug>/export-pdf/",
        export_views.export_product_pdf,
        name="product_export_pdf",
    ),
    path(
        "seller/<int:seller_id>/export-products/",
        export_views.export_products_csv,
        name="export_products_csv",
    ),
]