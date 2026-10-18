from .admin_views import (
    change_seller_status,
    change_store_banner,
    update_store_information,
)
from .auth_views import (
    change_password,
    login_view,
    logout_user,
    resend_verification_email_view,
    signup_view,
)
from .mfa_views import (
    MarketSphereMFAAuthenticateView,
    MarketSphereMFAReauthenticateView,
    ProfileActivateTOTPView,
    ProfileDeactivateTOTPView,
    ProfileViewRecoveryCodesView,
    profile_2fa_redirect,
)
from .profile_views import (
    delete_user_address_view,
    profile_view,
    save_user_address,
    update_my_profile_view,
    update_user_address,
    update_user_preferences,
)
from .seller_views import (
    deactivate_seller_account,
    reactivate_seller_account,
    seller_account,
    seller_signup_view,
    update_notification_preferences_view,
    update_seller_address,
    update_seller_document,
    update_seller_info,
    update_seller_profile,
    update_shipping_preferences_view,
)

__all__ = [
    # Auth Views
    "login_view",
    "signup_view",
    "logout_user",
    "resend_verification_email_view",
    "change_password",
    # MFA Views
    "profile_2fa_redirect",
    "MarketSphereMFAAuthenticateView",
    "MarketSphereMFAReauthenticateView",
    "ProfileActivateTOTPView",
    "ProfileDeactivateTOTPView",
    "ProfileViewRecoveryCodesView",
    # Buyer Profile Views
    "profile_view",
    "update_my_profile_view",
    "save_user_address",
    "update_user_address",
    "delete_user_address_view",
    "update_user_preferences",
    # Seller Views
    "seller_signup_view",
    "seller_account",
    "update_seller_info",
    "update_seller_address",
    "update_seller_profile",
    "update_seller_document",
    "update_shipping_preferences_view",
    "update_notification_preferences_view",
    "deactivate_seller_account",
    "reactivate_seller_account",
    # Admin Views
    "update_store_information",
    "change_store_banner",
    "change_seller_status",
]