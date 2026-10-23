from django.urls import path
from .views import (
    buyer_views,
    dashboard_views,
    order_views,
    product_views,
    promotion_views,
    seller_views,
    taxonomy_views,
    support_views,
)

urlpatterns = [
    # Dashboard & Settings
    path("", dashboard_views.dashboard, name="admin-dasboard"),
    path("settings", dashboard_views.admin_settings, name="admin-settings"),
    path("logout-all-devices/", dashboard_views.logout_all_devices, name="logout-all-devices"),

    # Buyers & Users
    path("change-account-state/", buyer_views.change_state, name="change-account-state"),
    path("user/", buyer_views.user_management, name="user-management"),
    path("user/<int:user_id>/send-email/", buyer_views.send_user_email, name="send_user_email"),
    path("user/buyers/", buyer_views.user_buyers, name="user-buyers"),
    path("user/buyers/<int:userId>", buyer_views.user_buyer, name="user-buyer"),
    path("user/buyers/<int:user_id>/reset-password/", buyer_views.admin_reset_password, name="admin_reset_password"),
    path("user/buyers/<int:buyer_id>/update-profile/", buyer_views.update_buyer_profile_view, name="update_buyer_profile"),
    path("buyers/<int:user_id>/export/", buyer_views.export_buyer_profile, name="export_buyer_profile"),
    path("buyers/<int:user_id>/export-orders/", buyer_views.export_order_history, name="export-order-history"),

    # Sellers
    path("user/sellers/", seller_views.user_sellers, name="user-sellers"),
    path("user/sellers/<int:sellerId>", seller_views.user_seller, name="user-seller"),
    path("user/sellers/<int:sellerId>/application", seller_views.seller_application, name="seller-application"),
    path("sellers/<int:seller_id>/export/", seller_views.export_seller_profile, name="export_seller_profile"),
    path("sellers/<int:seller_id>/export-orders/", seller_views.export_seller_orders, name="export_seller_orders"),
    path("sellers/<int:seller_id>/export-revenue/", seller_views.export_revenue_report_view, name="export_revenue_report"),
    path("user/seller/application/save-notes/", seller_views.save_application_notes, name="save_application_notes"),
    path("user/seller/<int:application_id>/application/approve/", seller_views.approve_seller_application, name="approve_seller_application"),
    path("user/seller/<int:application_id>/application/reject/", seller_views.reject_seller_application, name="reject_seller_application"),
    path("user/seller/<int:application_id>/application/request-changes/", seller_views.request_application_changes, name="request_application_changes"),
    path("user/seller/<int:seller_id>/delete/", seller_views.delete_seller_application, name="delete_seller_application"),
    path("user/seller/document/request/", seller_views.request_missing_document, name="request_missing_document"),
    path("user/seller/document/<int:document_id>/flag/", seller_views.flag_seller_document, name="flag_seller_document"),
    path("user/seller/document/<int:document_id>/verify/", seller_views.verify_seller_document, name="verify_seller_document"),

    # Taxonomy (Categories & Brands)
    path("catalog/categories", taxonomy_views.catalog_categories, name="catalog-categories"),
    path("catalog/categories/api/", taxonomy_views.category_api, name="admin-category-api"),
    path("catalog/categories/api/<int:category_id>/", taxonomy_views.category_api_detail, name="admin-category-api-detail"),
    path("catalog/categories/export/", taxonomy_views.export_categories_api, name="admin-category-export"),
    path("catalog/brands", taxonomy_views.catalog_brands, name="catalog-brands"),
    path("catalog/brands/api/", taxonomy_views.brand_api, name="admin-brand-api"),
    path("catalog/brands/api/<int:brand_id>/", taxonomy_views.brand_api_detail, name="admin-brand-api-detail"),
    path("catalog/brands/import/", taxonomy_views.brand_import_api, name="admin-brand-import"),
    path("catalog/brands/export/", taxonomy_views.brand_export_api, name="admin-brands-export"),

    # Product Management & Moderation
    path("catalog/products/", product_views.catalog_products, name="catalog-products"),
    path("catalog/products/<slug:product_slug>", product_views.catalog_product, name="catalog-product"),
    path("catalog/product-management/<slug:product_slug>/update/", product_views.edit_product_view, name="edit-product"),
    path("catalog/product-management/<slug:product_slug>/approve/", product_views.approve_product_view, name="admin_approve_product"),
    path("catalog/product-management/<slug:product_slug>/reject/", product_views.reject_product_view, name="reject-product"),
    path("catalog/product-management/<slug:product_slug>/hide/", product_views.hide_product_view, name="admin_hide_product"),
    path("catalog/product-management/<slug:product_slug>/unhide/", product_views.unhide_product_view, name="unhide-product"),
    path("catalog/product-management/<slug:product_slug>/publish/", product_views.publish_product_view, name="publish-product"),
    path("catalog/product-management/<slug:product_slug>/toggle-featured/", product_views.admin_toggle_product_featured_view, name="admin-toggle-product-featured"),
    path("catalog/product-management/<slug:product_slug>/images/upload/", product_views.upload_product_image_view, name="upload-product-image"),
    path("catalog/product-management/<slug:product_slug>/images/reorder/", product_views.reorder_product_images_view, name="reorder-product-images"),
    path("catalog/product-management/<slug:product_slug>/images/<int:image_id>/delete/", product_views.delete_product_image_view, name="delete-product-image"),
    path("catalog/product-management/<slug:product_slug>/images/<int:image_id>/set-primary/", product_views.set_primary_product_image_view, name="set-primary-product-image"),
    path("catalog/product-management/<slug:product_slug>/price/", product_views.update_product_pricing_view, name="update-product-pricing"),
    path("catalog/product-management/<slug:product_slug>/price/remove-discount/", product_views.remove_product_discount_view, name="remove-product-discount"),
    path("catalog/product-management/<slug:product_slug>/stock/adjust/", product_views.adjust_product_stock_view, name="adjust-product-stock"),
    path("catalog/product-management/<slug:product_slug>/stock/out-of-stock/", product_views.mark_product_out_of_stock_view, name="mark-product-out-of-stock"),
    path("catalog/product-management/<slug:product_slug>/stock/restore/", product_views.restore_product_stock_view, name="restore-product-stock"),

    # Promotions
    path("promotions/", promotion_views.admin_promotions, name="admin-promotions"),
    path("promotions/create/", promotion_views.admin_create_promotion, name="admin-create-promotion"),
    path("promotions/<slug:promotion_slug>/", promotion_views.admin_promotion_detail, name="admin-promotion-detail"),
    path("promotions/<slug:promotion_slug>/edit/", promotion_views.admin_edit_promotion, name="admin-edit-promotion"),
    path("promotions/<slug:promotion_slug>/products/", promotion_views.admin_manage_promotion_products, name="admin-manage-promotion-products"),
    path("promotions/products/<int:promotion_product_id>/price/", promotion_views.update_promotion_product_price, name="admin-update-promotion-product-price"),
    path("promotions/products/<int:promotion_product_id>/remove/", promotion_views.remove_promotion_product, name="admin-remove-promotion-product"),
    path("promotions/products/<int:promotion_product_id>/toggle-featured/", promotion_views.toggle_promotion_product_featured, name="admin-toggle-promotion-product-featured"),

    # Sales & Orders
    path("sales/orders", order_views.sales_orders, name="sales-orders"),
    path("sales/order/<str:order_number>", order_views.sales_order, name="sales-order"),
    path("sales/payments", order_views.payment_management, name="payment-management"),

        # Help & Support
    path("support/", support_views.support_requests, name="admin-support"),
    path("support/<int:request_id>/", support_views.support_request_detail, name="admin-support-detail"),
    path("support/<int:request_id>/reply/", support_views.support_request_reply, name="admin-support-reply"),
    path("support/<int:request_id>/status/", support_views.support_request_status, name="admin-support-status"),
]