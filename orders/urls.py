from django.urls import path
from . import views

urlpatterns = [
    path("", views.orders, name="orders"),
    path("<str:order_number>", views.order, name="order"),
    path("checkout/", views.checkout, name="checkout"),
    path(
        "checkout/item/<int:cart_item_id>/",
        views.checkout,
        name="checkout_item",
    ),
    path("place-order/", views.place_new_order, name="place-order"),
    path(
        "confirmation/<str:order_number>/",
        views.order_confirmation,
        name="order_confirmation",
    ),
    path(
        "<str:order_number>/invoice/",
        views.download_invoice,
        name="download_invoice",
    ),
    path(
        "<str:order_number>/update-note/",
        views.update_seller_note_view,
        name="update-seller-note",
    ),
    path(
        "<str:order_number>/shipping-label/",
        views.download_shipping_label,
        name="download-shipping-label",
    ),
    path(
        "<str:order_number>/packing-slip/",
        views.download_packing_slip,
        name="download-packing-slip",
    ),
    path(
        "<str:order_number>/shipping/",
        views.update_shipping,
        name="update_shipping",
    ),
    path(
        "cancel-order/<str:order_number>/", views.order_cancelation, name="cancel-order"
    ),
    path("reorder/<str:order_number>/", views.reorder, name="reorder"),
]
