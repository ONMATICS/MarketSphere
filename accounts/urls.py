from django.urls import path
from .views import (
    admin_views,
    auth_views,
    mfa_views,
    profile_views,
    seller_views,
)

urlpatterns = [
    # Auth
    path("login/", auth_views.login_view, name="login"),
    path("logout", auth_views.logout_user, name="logout"),
    path("signup/", auth_views.signup_view, name="signup"),
    path("change-password/", auth_views.change_password, name="change_password"),
    path(
        "email/resend/",
        auth_views.resend_verification_email_view,
        name="resend_verification_email",
    ),

    # MFA
    path(
        "2fa/authenticate/",
        mfa_views.MarketSphereMFAAuthenticateView.as_view(),
        name="mfa_authenticate",
    ),
    path(
        "2fa/reauthenticate/",
        mfa_views.MarketSphereMFAReauthenticateView.as_view(),
        name="mfa_reauthenticate",
    ),
    path("profile/2fa/", mfa_views.profile_2fa_redirect, name="profile_2fa_redirect"),
    path(
        "profile/2fa/activate/",
        mfa_views.ProfileActivateTOTPView.as_view(),
        name="profile_activate_totp",
    ),
    path(
        "profile/2fa/deactivate/",
        mfa_views.ProfileDeactivateTOTPView.as_view(),
        name="profile_deactivate_totp",
    ),
    path(
        "profile/2fa/recovery/",
        mfa_views.ProfileViewRecoveryCodesView.as_view(),
        name="profile_2fa_recovery",
    ),

    # Buyer Profile
    path("profile/", profile_views.profile_view, name="profile"),
    path("profile/update/", profile_views.update_my_profile_view, name="update_my_profile"),
    path(
        "preferences/update/",
        profile_views.update_user_preferences,
        name="update_user_preferences",
    ),
    path("save-address/", profile_views.save_user_address, name="save-address"),
    path(
        "buyer/address/update/",
        profile_views.update_user_address,
        name="update_user_address",
    ),
    path(
        "buyer/address/delete/",
        profile_views.delete_user_address_view,
        name="delete_user_address",
    ),

    # Seller
    path(
        "update-notification-preferences/",
        seller_views.update_notification_preferences_view,
        name="update_notification_preferences",
    ),
    path(
        "update-shipping-preferences/",
        seller_views.update_shipping_preferences_view,
        name="update_shipping_preferences",
    ),
    path("seller-signup/", seller_views.seller_signup_view, name="seller-signup"),
    path("seller-account/", seller_views.seller_account, name="seller-account"),
    path(
        "update-seller-profile/",
        seller_views.update_seller_profile,
        name="update_seller_profile",
    ),
    path(
        "update-seller-info/",
        seller_views.update_seller_info,
        name="update_seller_info",
    ),
    path(
        "update-seller-address/",
        seller_views.update_seller_address,
        name="update_seller_address",
    ),
    path(
        "update-seller-document/",
        seller_views.update_seller_document,
        name="update_seller_document",
    ),
    path(
        "deactivate-seller-account",
        seller_views.deactivate_seller_account,
        name="deactivate_seller_account",
    ),
    path(
        "reactivate-seller-account",
        seller_views.reactivate_seller_account,
        name="reactivate_seller_account",
    ),

    # Admin
    path(
        "change-seller-status/",
        admin_views.change_seller_status,
        name="change-seller-status",
    ),
    path(
        "<int:seller_id>/update-store/",
        admin_views.update_store_information,
        name="update_store_information",
    ),
    path(
        "change-store-banner/",
        admin_views.change_store_banner,
        name="change-store-banner",
    ),
]