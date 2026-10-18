from .buyer_views import (
    admin_reset_password,
    change_state,
    export_buyer_profile,
    export_order_history,
    send_user_email,
    update_buyer_profile_view,
    user_buyer,
    user_buyers,
    user_management,
)
from .dashboard_views import admin_settings, dashboard, logout_all_devices
from .order_views import payment_management, sales_order, sales_orders
from .product_views import (
    adjust_product_stock_view,
    admin_toggle_product_featured_view,
    approve_product_view,
    catalog_product,
    catalog_products,
    delete_product_image_view,
    edit_product_view,
    hide_product_view,
    mark_product_out_of_stock_view,
    publish_product_view,
    reject_product_view,
    remove_product_discount_view,
    reorder_product_images_view,
    restore_product_stock_view,
    set_primary_product_image_view,
    unhide_product_view,
    update_product_pricing_view,
    upload_product_image_view,
)
from .promotion_views import (
    admin_create_promotion,
    admin_edit_promotion,
    admin_manage_promotion_products,
    admin_promotion_detail,
    admin_promotions,
    remove_promotion_product,
    toggle_promotion_product_featured,
    update_promotion_product_price,
)
from .seller_views import (
    approve_seller_application,
    delete_seller_application,
    export_revenue_report_view,
    export_seller_orders,
    export_seller_profile,
    flag_seller_document,
    reject_seller_application,
    request_application_changes,
    request_missing_document,
    save_application_notes,
    seller_application,
    user_seller,
    user_sellers,
    verify_seller_document,
)
from .taxonomy_views import (
    brand_api,
    brand_api_detail,
    brand_export_api,
    brand_import_api,
    catalog_brands,
    catalog_categories,
    category_api,
    category_api_detail,
    export_categories_api,
)

__all__ = [
    # Dashboard
    "dashboard", "admin_settings", "logout_all_devices",
    # Buyers
    "user_management", "user_buyers", "user_buyer", "update_buyer_profile_view", 
    "admin_reset_password", "send_user_email", "export_buyer_profile", "export_order_history", "change_state",
    # Sellers
    "user_sellers", "user_seller", "seller_application", "reject_seller_application", 
    "request_application_changes", "approve_seller_application", "delete_seller_application", 
    "flag_seller_document", "verify_seller_document", "request_missing_document", 
    "save_application_notes", "export_seller_orders", "export_revenue_report_view", "export_seller_profile",
    # Taxonomy
    "catalog_categories", "export_categories_api", "category_api", "category_api_detail", 
    "catalog_brands", "brand_api", "brand_api_detail", "brand_import_api", "brand_export_api",
    # Products
    "catalog_products", "catalog_product", "approve_product_view", "hide_product_view", 
    "unhide_product_view", "reject_product_view", "admin_toggle_product_featured_view",
    "publish_product_view", "upload_product_image_view", "delete_product_image_view", 
    "reorder_product_images_view", "set_primary_product_image_view", "update_product_pricing_view", 
    "remove_product_discount_view", "adjust_product_stock_view", "mark_product_out_of_stock_view", 
    "restore_product_stock_view", "edit_product_view",
    # Orders
    "sales_orders", "sales_order", "payment_management",
    # Promotions
    "admin_promotions", "admin_create_promotion", "admin_promotion_detail", 
    "admin_edit_promotion", "admin_manage_promotion_products", "update_promotion_product_price", 
    "toggle_promotion_product_featured", "remove_promotion_product",
]