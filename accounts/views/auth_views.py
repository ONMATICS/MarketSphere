import json
import logging

from allauth.account.forms import LoginForm
from allauth.core.exceptions import ImmediateHttpResponse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from accounts import services, validator
from admin_panel.marketplace import get_marketplace_settings
from services.decorators.decorators import authenticated, verified_email_required

logger = logging.getLogger(__name__)


def login_view(request: HttpRequest) -> HttpResponse:
    """Handle user login, including Multi-Factor Authentication routing."""
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
                return form.login(request, redirect_url=settings.LOGIN_REDIRECT_URL)
            except ImmediateHttpResponse as exc:
                return exc.response

    return render(request, "login.html", {"form": form})


def signup_view(request: HttpRequest) -> HttpResponse:
    """Handle new buyer registration."""
    if not get_marketplace_settings().buyer_registration:
        messages.info(request, "Buyer registration is currently unavailable.")
        return redirect("home")

    if request.method == "POST":
        user_data = {
            "first_name": request.POST.get("first_name"),
            "last_name": request.POST.get("last_name"),
            "email": request.POST.get("email", "").lower(),
            "username": request.POST.get("username", "").lower(),
            "contact": request.POST.get("contact"),
            "password": request.POST.get("password"),
        }
        
        if not validator.validate_user_email(user_data["email"]):
            messages.error(request, "Email Already Exists.")
            return redirect("signup")

        if not validator.validate_username(user_data["username"]):
            messages.error(request, "Username Already Exists.")
            return redirect("signup")

        if not validator.validate_password(user_data["password"]):
            messages.error(request, "Enter a valid password.")
            return redirect("signup")
            
        user = services.create_user(user_data)
        services.send_verification_email(request, user, signup=True)

        messages.success(
            request,
            "Your account has been created successfully. We've sent a verification email to your inbox. Please verify your email before accessing all features.",
        )
        return redirect("login")

    return render(request, "signup.html")


@authenticated
def logout_user(request: HttpRequest) -> HttpResponse:
    """Log the current user out and redirect to the login page."""
    logout(request)
    return redirect("login")


@authenticated
def resend_verification_email_view(request: HttpRequest) -> HttpResponse:
    """Resend the email verification link to the current user."""
    if request.method != "POST":
        return redirect(settings.LOGIN_REDIRECT_URL)

    try:
        sent = services.send_verification_email(request, request.user)
        if sent:
            messages.success(request, f"A new verification email has been sent to {request.user.email}.")
        else:
            messages.info(request, "Your email address is already verified.")
    except Exception:
        logger.exception("Failed to resend verification email for user_id: %s", request.user.id)
        messages.error(request, "Unable to send verification email at this time. Please try again later.")

    return redirect(settings.LOGIN_REDIRECT_URL)


@verified_email_required
def change_password(request: HttpRequest) -> JsonResponse:
    """Change the authenticated user's password via an AJAX request."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

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
        return JsonResponse({"success": True, "message": "Your password has been changed successfully."})

    except ValueError as error:
        return JsonResponse({"success": False, "message": str(error)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)
    except Exception:
        logger.exception("Failed to change password for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Something went wrong. Please try again."}, status=500)