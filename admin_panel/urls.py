from . import views
from django.urls import path

urlpatterns = [
    path("", views.dashboard, name="admin-dasboard"),
    path("user/", views.user_management, name="user-management"),
    path("user/buyers/", views.user_buyers, name="user-buyers"),
    path("user/sellers/", views.user_sellers, name="user-sellers"),
    path("user/buyers/<int:userId>", views.user_buyer, name="user-buyer"),
    path("user/sellers/<int:sellerId>", views.user_seller, name="user-seller"),
    path(
        "user/sellers/<int:sellerId>/application",
        views.seller_application,
        name="seller-application",
    ),
    path("promotions/", views.admin_promotions, name="admin-promotions"),
    path(
        "promotions/create/",
        views.admin_create_promotion,
        name="admin-create-promotion",
    ),
        path("promotions/", views.admin_promotions, name="admin-promotions"),
    path("promotions/create/", views.admin_create_promotion, name="admin-create-promotion"),
    path("promotions/<slug:promotion_slug>/edit/", views.admin_edit_promotion, name="admin-edit-promotion"),
    path("promotions/<slug:promotion_slug>/", views.admin_promotion_detail, name="admin-promotion-detail"),
        path(
        "promotions/products/<int:promotion_product_id>/price/",
        views.update_promotion_product_price,
        name="admin-update-promotion-product-price",
    ),
    path(
        "promotions/products/<int:promotion_product_id>/toggle-featured/",
        views.toggle_promotion_product_featured,
        name="admin-toggle-promotion-product-featured",
    ),
    path(
        "promotions/products/<int:promotion_product_id>/remove/",
        views.remove_promotion_product,
        name="admin-remove-promotion-product",
    ),
    path(
        "promotions/<slug:promotion_slug>/products/",
        views.admin_manage_promotion_products,
        name="admin-manage-promotion-products",
    ),
    path("catalog/products/", views.catalog_products, name="catalog-products"),
    path(
        "catalog/products/<slug:product_slug>",
        views.catalog_product,
        name="catalog-product",
    ),
    path("catalog/categories", views.catalog_categories, name="catalog-categories"),
    path("catalog/categories/api/", views.category_api, name="admin-category-api"),
    path(
        "catalog/categories/api/<int:category_id>/",
        views.category_api_detail,
        name="admin-category-api-detail",
    ),
    path("catalog/brands", views.catalog_brands, name="catalog-brands"),
    path("catalog/brands/api/", views.brand_api, name="admin-brand-api"),
    path(
        "catalog/brands/api/<int:brand_id>/",
        views.brand_api_detail,
        name="admin-brand-api-detail",
    ),
    path("catalog/brands/import/", views.brand_import_api, name="admin-brand-import"),
    path("catalog/brands/export/", views.brand_export_api, name="admin-brands-export"),
    path("sales/orders", views.sales_orders, name="sales-orders"),
    path("sales/order/<str:order_number>", views.sales_order, name="sales-order"),
    path("sales/payments", views.payment_management, name="payment-management"),
    path("settings", views.admin_settings, name="admin-settings"),
    path("change-account-state/", views.change_state, name="change-account-state"),
    path(
        "user/buyers/<int:user_id>/reset-password/",
        views.admin_reset_password,
        name="admin_reset_password",
    ),
    path(
        "catalog/categories/export/",
        views.export_categories_api,
        name="admin-category-export",
    ),
    path(
        "logout-all-devices/",
        views.logout_all_devices,
        name="logout-all-devices",
    ),
    path(
        "buyers/<int:user_id>/export/",
        views.export_buyer_profile,
        name="export_buyer_profile",
    ),
    path(
        "sellers/<int:seller_id>/export/",
        views.export_seller_profile,
        name="export_seller_profile",
    ),
    path(
        "user/buyers/<int:buyer_id>/update-profile/",
        views.update_buyer_profile_view,
        name="update_buyer_profile",
    ),
    path(
        "user/<int:user_id>/send-email/",
        views.send_user_email,
        name="send_user_email",
    ),
    path(
        "buyers/<int:user_id>/export-orders/",
        views.export_order_history,
        name="export-order-history",
    ),
    path(
        "sellers/<int:seller_id>/export-orders/",
        views.export_seller_orders,
        name="export_seller_orders",
    ),
    path(
        "sellers/<int:seller_id>/export-revenue/",
        views.export_revenue_report_view,
        name="export_revenue_report",
    ),
    path(
        "user/seller/<int:application_id>/application/reject/",
        views.reject_seller_application,
        name="reject_seller_application",
    ),
    path(
        "user/seller/<int:application_id>/application/request-changes/",
        views.request_application_changes,
        name="request_application_changes",
    ),
    path(
        "user/seller/<int:application_id>/application/approve/",
        views.approve_seller_application,
        name="approve_seller_application",
    ),
    path(
        "user/seller/<int:seller_id>/delete/",
        views.delete_seller_application,
        name="delete_seller_application",
    ),
    path(
        "user/seller/document/<int:document_id>/flag/",
        views.flag_seller_document,
        name="flag_seller_document",
    ),
    path(
        "user/seller/document/<int:document_id>/verify/",
        views.verify_seller_document,
        name="verify_seller_document",
    ),
    path(
        "user/seller/document/request/",
        views.request_missing_document,
        name="request_missing_document",
    ),
    path(
        "user/seller/application/save-notes/",
        views.save_application_notes,
        name="save_application_notes",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/approve/",
        views.approve_product_view,
        name="admin_approve_product",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/hide/",
        views.hide_product_view,
        name="admin_hide_product",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/unhide/",
        views.unhide_product_view,
        name="unhide-product",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/reject/",
        views.reject_product_view,
        name="reject-product",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/toggle-featured/",
        views.admin_toggle_product_featured_view,
        name="admin-toggle-product-featured",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/publish/",
        views.publish_product_view,
        name="publish-product",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/images/upload/",
        views.upload_product_image_view,
        name="upload-product-image",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/images/<int:image_id>/delete/",
        views.delete_product_image_view,
        name="delete-product-image",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/images/reorder/",
        views.reorder_product_images_view,
        name="reorder-product-images",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/images/<int:image_id>/set-primary/",
        views.set_primary_product_image_view,
        name="set-primary-product-image",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/price/",
        views.update_product_pricing_view,
        name="update-product-pricing",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/price/remove-discount/",
        views.remove_product_discount_view,
        name="remove-product-discount",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/stock/adjust/",
        views.adjust_product_stock_view,
        name="adjust-product-stock",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/stock/out-of-stock/",
        views.mark_product_out_of_stock_view,
        name="mark-product-out-of-stock",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/stock/restore/",
        views.restore_product_stock_view,
        name="restore-product-stock",
    ),
    path(
        "catalog/product-management/<slug:product_slug>/update/",
        views.edit_product_view,
        name="edit-product",
    ),
]
