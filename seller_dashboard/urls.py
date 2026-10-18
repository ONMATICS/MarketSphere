from django.urls import path

from .views import (
    dashboard_views,
    order_views,
    product_views,
)

urlpatterns = [
    # Dashboard & Settings
    path("", dashboard_views.dashboard, name="dashboard"),
    path("settings/", dashboard_views.dashboard_settings, name="dashboard-settings"),

    # Products (Global Actions & Management)
    path("products/", product_views.products, name="products-list"),
    path("products/add-product/", product_views.add_product, name="add-product"),
    path("products/save-draft/", product_views.draft_product, name="save-draft"),
    path("products/hide-product", product_views.hide_product, name="hide-product"),
    path("products/unhide-product", product_views.unhide_product, name="unhide-product"),
    path("products/delete-product", product_views.delete_product, name="delete-product"),
    path(
        "products/toggle-archive/",
        product_views.toggle_product_archive_view,
        name="toggle-product-archive",
    ),
    path(
        "products/toggle-featured/",
        product_views.toggle_product_featured_view,
        name="toggle-product-featured",
    ),

    # Products (Specific Item Operations)
    path(
        "products/<slug:product_slug>/detail/",
        product_views.product_detail,
        name="seller-product-detail",
    ),
    # Keep the seller route distinct from the admin route that also uses
    # ``edit-product`` in the project-wide URL resolver.
    path(
        "products/edit-product/<slug:product_slug>",
        product_views.edit_products,
        name="seller-edit-product",
    ),
    path(
        "products/<slug:product_slug>/pricing/",
        product_views.product_update_pricing,
        name="seller-product-pricing",
    ),
    path(
        "products/<slug:product_slug>/discount/remove/",
        product_views.product_remove_discount,
        name="seller-product-remove-discount",
    ),
    path(
        "products/<slug:product_slug>/stock/adjust/",
        product_views.product_adjust_stock,
        name="seller-product-adjust-stock",
    ),
    path(
        "products/<slug:product_slug>/stock/out-of-stock/",
        product_views.product_mark_out_of_stock,
        name="seller-product-out-of-stock",
    ),
    path(
        "products/<slug:product_slug>/stock/restore/",
        product_views.product_restore_stock,
        name="seller-product-restore-stock",
    ),
    path(
        "products/<slug:product_slug>/visibility/",
        product_views.product_visibility,
        name="seller-product-visibility",
    ),

    # Orders
    path("orders/", order_views.orders, name="orders-list"),
    path(
        "orders/export/",
        order_views.export_seller_orders_csv_view,
        name="export_seller_orders",
    ),
    path("orders/<str:order_no>", order_views.order_detail, name="order-detail"),
    path(
        "orders/<str:order_no>/<str:status>/",
        order_views.update_user_order_status,
        name="update-order-status",
    ),
]