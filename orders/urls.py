from django.urls import path

from .views import (
    buyer_order_views,
    checkout_views,
    seller_order_views,
)

urlpatterns = [
    # Checkout
    path("checkout/", checkout_views.checkout, name="checkout"),
    path(
        "checkout/item/<int:cart_item_id>/",
        checkout_views.checkout,
        name="checkout_item",
    ),
    path("place-order/", checkout_views.place_new_order, name="place-order"),
    path(
        "confirmation/<str:order_number>/",
        checkout_views.order_confirmation,
        name="order_confirmation",
    ),

    # Buyer Order Management
    path("", buyer_order_views.orders, name="orders"),
    path("<str:order_number>", buyer_order_views.order, name="order"),
    path(
        "cancel-order/<str:order_number>/",
        buyer_order_views.order_cancelation,
        name="cancel-order",
    ),
    path("reorder/<str:order_number>/", buyer_order_views.reorder, name="reorder"),
    path("submit-review/", buyer_order_views.submit_review_api, name="submit_review_api"),

    # Seller Order Management & PDF Generation
    path(
        "<str:order_number>/invoice/",
        seller_order_views.download_invoice,
        name="download_invoice",
    ),
    path(
        "<str:order_number>/shipping-label/",
        seller_order_views.download_shipping_label,
        name="download-shipping-label",
    ),
    path(
        "<str:order_number>/packing-slip/",
        seller_order_views.download_packing_slip,
        name="download-packing-slip",
    ),
    path(
        "<str:order_number>/shipping/",
        seller_order_views.update_shipping,
        name="update_shipping",
    ),
    path(
        "<str:order_number>/update-note/",
        seller_order_views.update_seller_note_view,
        name="update-seller-note",
    ),
]