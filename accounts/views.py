from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import Http404
import json
import logging
from pathlib import Path
import cloudinary.exceptions
from allauth.account.forms import LoginForm
from allauth.core.exceptions import ImmediateHttpResponse

from accounts.seller_pdf import export_seller_profile_snapshot
from .decorators import verified_seller, verified_user, only_seller
from django.http import JsonResponse
from django.utils import timezone

User = get_user_model()
from . import validator
from . import services
from admin_panel.marketplace import get_marketplace_settings
from services.cloudinary_service import store_profile_image

logger = logging.getLogger(__name__)

# Create your views here.


def login_view(request):
    # Use allauth's LoginForm even though the page is custom.  Calling
    # django.contrib.auth.login() directly skips allauth's login stages,
    # including the MFA challenge for users with TOTP enabled.
    form_data = None
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip().lower()
        form_data = request.POST.copy()
        form_data["login"] = identifier

    form = LoginForm(request=request, data=form_data)
    if request.method == "POST" and form.is_valid():
        valid_status, message = validator.validate_account_status(form.user)
        if not valid_status:
            form.add_error(None, message)
        else:
            try:
                # This returns the normal redirect or allauth's MFA-stage
                # response.  It must not be replaced with a direct login().
                return form.login(request, redirect_url=settings.LOGIN_REDIRECT_URL)
            except ImmediateHttpResponse as exc:
                return exc.response

    return render(request, "login.html", {"form": form})


def signup_view(request):
    if not get_marketplace_settings().buyer_registration:
        messages.info(request, "Buyer registration is currently unavailable.")
        return redirect("home")

    if request.method == "POST":
        user = {
            "first_name": request.POST.get("first_name"),
            "last_name": request.POST.get("last_name"),
            "email": request.POST.get("email").lower(),
            "username": request.POST.get("username").lower(),
            "contact": request.POST.get("contact"),
            "password": request.POST.get("password"),
        }
        if validator.validate_user_email(user["email"]) == False:
            messages.error(request, "Email Already Exists.")
            return redirect("signup")

        if validator.validate_username(user["username"]) == False:
            messages.error(request, "Username Already Exists.")
            return redirect("signup")

        if validator.validate_password(user["password"]) == False:
            messages.error(request, "Enter a valid password")
            return redirect("signup")
        user = services.create_user(user)
        services.send_verification_email(request, user, signup=True)

        messages.success(
            request,
            "Your account has been created successfully. We've sent a verification email to your inbox. Please verify your email before accessing all features.",
        )

        return redirect("login")

    return render(request, "signup.html")


@login_required
@verified_user
def seller_signup_view(request):
    marketplace_settings = get_marketplace_settings()
    if not marketplace_settings.seller_registration:
        messages.info(request, "Seller registration is currently unavailable.")
        return redirect("home")

    print(request.POST)
    print(request.FILES)
    if request.method == "POST":
        seller = services.create_seller_application(
            request.user,
            request.POST,
            request.FILES,
        )
        if not marketplace_settings.seller_approval_required:
            seller.status = seller.Status.VERIFIED
            seller.save(update_fields=["status"])
            seller.application.status = seller.application.Status.APPROVED
            seller.application.reviewed_at = timezone.now()
            seller.application.save(update_fields=["status", "reviewed_at"])
        return redirect("seller-account")
    return render(request, "seller_signup.html")


@only_seller
def update_seller_info(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )
    try:
        services.update_seller_information(
            request.user,
            request.POST,
            request.FILES,
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Store information updated successfully.",
            }
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e),
            },
            status=400,
        )


from . import services
from .decorators import only_seller


@login_required
@only_seller
def deactivate_seller_account(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid request."},
            status=405,
        )

    services.deactivate_seller_account(request.user.seller_profile)

    return JsonResponse(
        {
            "status": "success",
            "message": "Seller account deactivated successfully.",
        }
    )


@login_required
@only_seller
def reactivate_seller_account(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid request."},
            status=405,
        )

    services.reactivate_seller_account(request.user.seller_profile)

    return JsonResponse(
        {
            "status": "success",
            "message": "Seller account activated successfully.",
        }
    )


@login_required
@only_seller
def update_seller_address(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    try:
        services.update_seller_address(
            request.user,
            request.POST,
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Business address updated successfully.",
            }
        )

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e),
            },
            status=400,
        )

@only_seller
def seller_account(request):
    seller = request.user.seller_profile

    business_address = services.get_bussiness_address(seller)

    documents = services.get_seller_application_documents(seller)

    application_progress = services.calculate_application_progress(seller)

    context = {
        "seller": seller,
        "business_address": business_address,
        "documents": documents,
        "application_progress": application_progress,
    }

    return render(request, "seller_account.html", context)

from django.shortcuts import redirect
from allauth.mfa.utils import is_mfa_enabled


@login_required
def profile_2fa_redirect(request):
    if is_mfa_enabled(request.user):
        return redirect("profile_deactivate_totp")

    return redirect("profile_activate_totp")


# ==============================================================================
# BUYER PROFILE — TWO-FACTOR AUTHENTICATION (custom UI over allauth.mfa)
# ==============================================================================
#
# These three views are thin wrappers around allauth's own TOTP / recovery-
# codes views. They exist ONLY to:
#   1. render MarketSphere-branded templates instead of allauth's defaults,
#   2. keep the redirect chain inside MarketSphere's own named URLs.
#
# Everything security-relevant — TOTP secret generation, code validation,
# reauthentication enforcement, recovery-code generation/masking — is left
# entirely to allauth's forms/flows and is NOT reimplemented here.
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseRedirect
from allauth.mfa.totp.views import ActivateTOTPView, DeactivateTOTPView
from allauth.mfa.recovery_codes.views import ViewRecoveryCodesView
from allauth.mfa.base.views import AuthenticateView, ReauthenticateView


class MarketSphereMFAAuthenticateView(AuthenticateView):
    """Use the branded MFA sign-in challenge for allauth's MFA stage."""

    template_name = "mfa/authenticate.html"


class MarketSphereMFAReauthenticateView(ReauthenticateView):
    """Use the branded identity confirmation page for protected actions."""

    template_name = "mfa/reauthenticate.html"


class ProfileActivateTOTPView(ActivateTOTPView):
    """
    Custom-templated TOTP activation.

    QR code, manual secret, and code validation all come from allauth's
    ActivateTOTPForm/get_context_data() (totp_svg_data_uri, form.secret,
    form.code) — this class only swaps the template and success routing.
    """

    template_name = "profile_2fa_activate.html"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)

        # allauth's own dispatch() redirects here if TOTP is already
        # active. Keep the user on MarketSphere's own deactivation page
        # instead of allauth's stock one.
        if (
            isinstance(response, HttpResponseRedirect)
            and response.url == reverse("mfa_deactivate_totp")
        ):
            return redirect("profile_deactivate_totp")

        return response

    def get_success_url(self):
        # `did_generate_recovery_codes` is set in ActivateTOTPView.form_valid().
        # Recovery codes are auto-generated by allauth only the FIRST time
        # TOTP is activated for a user — this is what makes the mandatory
        # recovery-codes step actually mandatory instead of skippable.
        if self.did_generate_recovery_codes:
            return reverse("profile_2fa_recovery")

        return reverse("profile")


class ProfileDeactivateTOTPView(DeactivateTOTPView):
    """Custom-templated TOTP deactivation confirmation."""

    template_name = "profile_2fa_deactivate.html"
    success_url = reverse_lazy("profile")

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)

        # allauth's own dispatch() redirects here if TOTP isn't active.
        # The profile toggle only ever links here when it IS active, but
        # guard the edge case (e.g. a stale tab) by staying in our UI.
        if (
            isinstance(response, HttpResponseRedirect)
            and response.url == reverse("mfa_activate_totp")
        ):
            return redirect("profile_activate_totp")

        return response


class ProfileViewRecoveryCodesView(ViewRecoveryCodesView):
    """
    Custom-templated recovery-codes display.

    The one-time "show once" masking behaviour driven by
    MFA_RECOVERY_CODES_SHOW_ONCE lives entirely in allauth's
    view_recovery_codes() flow (see ViewRecoveryCodesView.get_context_data).
    This class only swaps the template so that behaviour is reused, not
    reimplemented.
    """

    template_name = "profile_2fa_recovery.html"


@login_required
def profile_view(request):
    """
    Buyer-facing "My Profile" / My Account page.

    Kept intentionally thin — all data-gathering (orders, addresses,
    wishlist preview, profile completion, activity, notifications)
    lives in services.get_buyer_profile_context() so this view stays
    easy to read and the template stays fully driven by context data.
    """
    context = services.get_buyer_profile_context(request.user)

    return render(request, "buyer_profile.html", context)

@login_required
def save_user_address(request):
    if request.method != "POST":
        return JsonResponse(
            {"success": False},
            status=405,
        )

    data = json.loads(request.body)

    address = services.save_user_address(
        request.user,
        data,
    )

    return JsonResponse({
        "success": True,
        "message": "Address added successfully.",
        "address": {
            "id": address.id,
            "address_type": address.address_type,
            "address_type_display": address.get_address_type_display(),
            "full_name": address.full_name,
            "phone": address.phone,
            "address_line_1": address.address_line_1,
            "address_line_2": address.address_line_2,
            "city": address.city,
            "postal_code": address.postal_code,
            "is_default": address.is_default,
        },
    })
import json

@login_required
def update_user_address(request):
    try:
        data = json.loads(request.body)

        address = services.update_user_address(
            request.user,
            data,
        )

        return JsonResponse({
            "success": True,
            "message": "Address updated successfully.",
            "address": {
                "id": address.id,
                "address_type": address.address_type,
                "address_type_display": address.get_address_type_display(),
                "full_name": address.full_name,
                "phone": address.phone,
                "address_line_1": address.address_line_1,
                "address_line_2": address.address_line_2,
                "city": address.city,
                "postal_code": address.postal_code,
                "is_default": address.is_default,
            },
        })

    except ValueError as e:
        return JsonResponse(
            {
                "success": False,
                "message": str(e),
            },
            status=400,
        )

    except Exception:
        return JsonResponse(
            {
                "success": False,
                "message": "Something went wrong. Please try again.",
            },
            status=500,
        )

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .services import delete_user_address


@login_required
def delete_user_address_view(request):
    try:
        data = json.loads(request.body)

        delete_user_address(request.user, data)

        return JsonResponse(
            {"success": True, "message": "Address deleted successfully."}
        )

    except ValueError as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)

    except Exception:
        return JsonResponse(
            {"success": False, "message": "Something went wrong. Please try again."},
            status=500,
        )

import json
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
def change_password(request):
    try:
        data = json.loads(request.body or "{}")

        current_password = data.get("current_password", "").strip()
        new_password = data.get("new_password", "")
        confirm_password = data.get("confirm_password", "")
        services.change_user_password(
            user=request.user,
            current_password=current_password,
            new_password=new_password,
            confirm_password=confirm_password,
        )

        logout(request)

        return JsonResponse({
            "success": True,
            "message": "Your password has been changed successfully.",
        })

    except ValueError as error:
        return JsonResponse({
            "success": False,
            "message": str(error),
        }, status=400)

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid request data.",
        }, status=400)

    except Exception:
        return JsonResponse({
            "success": False,
            "message": "Something went wrong. Please try again.",
        }, status=500)
    
@login_required
def update_shipping_preferences_view(request):

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request.",
            },
            status=405,
        )

    seller = request.user.seller_profile

    services.update_shipping_preferences(seller, request.POST)

    return JsonResponse(
        {
            "success": True,
            "message": "Shipping preferences updated successfully.",
        }
    )


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from . import services


@login_required
def update_notification_preferences_view(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    seller = request.user.seller_profile

    services.update_notification_preferences(seller, request.POST)

    return JsonResponse(
        {
            "success": True,
            "message": "Notification preferences updated successfully.",
        }
    )


@login_required
def logout_user(request):
    logout(request)
    return redirect("login")


@login_required
def resend_verification_email_view(request):
    if request.method != "POST":
        return redirect(settings.LOGIN_REDIRECT_URL)

    sent = services.send_verification_email(request, request.user)

    if sent:
        messages.success(
            request, f"A new verification email has been sent.({request.user.email})"
        )
    else:
        messages.info(request, "Your email address is already verified.")

    return redirect(settings.LOGIN_REDIRECT_URL)


from django.http import JsonResponse


def change_store_banner(request):
    if request.method != "POST":
        return JsonResponse({"success": False}, status=405)

    seller_id = request.POST.get("seller_id")
    banner = request.FILES.get("banner")

    banner_url = services.change_store_banner(
        seller_id=seller_id,
        banner=banner,
    )

    if banner_url:
        return JsonResponse(
            {
                "success": True,
                "banner_url": banner_url,
            }
        )

    return JsonResponse(
        {
            "success": False,
            "message": "Unable to update banner.",
        }
    )


from .models import Seller


def change_seller_status(request):
    if request.method != "POST":
        return JsonResponse({"success": False}, status=405)

    seller = Seller.objects.filter(id=request.POST.get("seller_id")).first()

    if not seller:
        return JsonResponse(
            {
                "success": False,
                "message": "Seller not found.",
            }
        )

    services.update_seller_status(
        seller,
        request.POST.get("status"),
    )

    return JsonResponse({"success": True})


import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required

from accounts.models import Seller
from . import services


@require_POST
def update_store_information(request, seller_id):
    seller = get_object_or_404(Seller, id=seller_id)

    data = json.loads(request.body)

    services.update_store_information(seller, data)

    return JsonResponse(
        {"success": True, "message": "Store information updated successfully."}
    )


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def update_seller_profile(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    success, message = services.update_seller_profile_service(
        request.user,
        request.POST,
    )

    return JsonResponse(
        {
            "success": success,
            "message": message,
        }
    )


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required
@require_POST
def update_my_profile_view(request):
    buyer = request.user

    if request.content_type.startswith("multipart/"):
        data = request.POST
    else:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return JsonResponse(
                {"success": False, "message": "Invalid request data."},
                status=400,
            )

    image_url = None
    profile_image = request.FILES.get("profile_image")
    if profile_image:
        try:
            upload_result = store_profile_image(profile_image, user_id=str(buyer.id))
        except ValueError as error:
            return JsonResponse({"success": False, "message": str(error)}, status=400)
        except cloudinary.exceptions.NotAllowed:
            logger.exception("Cloudinary rejected profile image upload permissions.")
            return JsonResponse(
                {
                    "success": False,
                    "message": "Cloudinary upload permission is missing. Please update the Cloudinary API key permissions.",
                },
                status=502,
            )
        except Exception:
            logger.exception("Profile image upload failed.")
            return JsonResponse(
                {"success": False, "message": "Unable to upload your profile image right now."},
                status=502,
            )

        image_url = upload_result.get("secure_url") or upload_result.get("url")
        if not image_url:
            return JsonResponse(
                {"success": False, "message": "Cloudinary did not return an image URL."},
                status=502,
            )

    success, message, buyer, email_changed, errors = (
        services.update_buyer_profile(
            user=buyer,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            username=data.get("username"),
            email=data.get("email"),
            contact=data.get("phone"),
            profile_image=image_url,
            allow_status_change=False,
            request=request,
        )
    )

    if not success:
        return JsonResponse(
            {
                "success": False,
                "message": message,
                "errors": errors,
            },
            status=400,
        )

    return JsonResponse(
        {
            "success": True,
            "message": message,
            "email_changed": email_changed,
            "user": {
                "id": buyer.id,
                "first_name": buyer.first_name,
                "last_name": buyer.last_name,
                "username": buyer.username,
                "email": buyer.email,
                "contact": buyer.contact,
                "profile_image_url": buyer.profile_image_url,
            },
        }
    )

@login_required
def update_seller_document(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    success, message, document = services.update_seller_document_service(
        user=request.user,
        data=request.POST,
        files=request.FILES,
    )

    response = {
        "success": success,
        "message": message,
    }

    if success:
        response["document_url"] = document.file
        response["uploaded_at"] = document.uploaded_at.strftime("%b %d, %Y")

    return JsonResponse(response)

@login_required
@require_POST
def update_user_preferences(request):
    try:
        data = json.loads(request.body or "{}")

        preferences = services.update_user_preferences(
            user=request.user,
            data=data,
        )

        return JsonResponse({
            "success": True,
            "message": "Preferences saved successfully.",
            "preferences": {
                "order_updates": preferences.order_updates,
                "promotional_emails": preferences.promotional_emails,
                "price_drop_alerts": preferences.price_drop_alerts,
                "wishlist_alerts": preferences.wishlist_alerts,
                "review_reminders": preferences.review_reminders,
                "newsletter": preferences.newsletter,
                "email_notifications": preferences.email_notifications,
                "in_app_notifications": preferences.in_app_notifications,
                "push_notifications": preferences.push_notifications,
            },
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "message": "Invalid request data.",
        }, status=400)

    except ValueError as error:
        return JsonResponse({
            "success": False,
            "message": str(error),
        }, status=400)

    except Exception:
        return JsonResponse({
            "success": False,
            "message": "Something went wrong. Please try again.",
        }, status=500)
