from .dashboard_views import dashboard, dashboard_settings
from .order_views import (
    export_seller_orders_csv_view,
    order_detail,
    orders,
    update_user_order_status,
)
from .product_views import (
    add_product,
    delete_product,
    draft_product,
    edit_products,
    hide_product,
    product_adjust_stock,
    product_detail,
    product_mark_out_of_stock,
    product_remove_discount,
    product_restore_stock,
    product_update_pricing,
    product_visibility,
    products,
    toggle_product_archive_view,
    toggle_product_featured_view,
    unhide_product,
)

__all__ = [
    # Dashboard & Settings
    "dashboard",
    "dashboard_settings",
    # Products
    "products",
    "add_product",
    "draft_product",
    "edit_products",
    "product_detail",
    "hide_product",
    "unhide_product",
    "delete_product",
    "toggle_product_featured_view",
    "toggle_product_archive_view",
    "product_update_pricing",
    "product_remove_discount",
    "product_adjust_stock",
    "product_mark_out_of_stock",
    "product_restore_stock",
    "product_visibility",
    # Orders
    "orders",
    "order_detail",
    "update_user_order_status",
    "export_seller_orders_csv_view",
]