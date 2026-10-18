import logging

from allauth.mfa.base.views import AuthenticateView, ReauthenticateView
from allauth.mfa.recovery_codes.views import ViewRecoveryCodesView
from allauth.mfa.totp.views import ActivateTOTPView, DeactivateTOTPView
from allauth.mfa.utils import is_mfa_enabled

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy

logger = logging.getLogger(__name__)


@login_required
def profile_2fa_redirect(request: HttpRequest) -> HttpResponse:
    """Redirect to the appropriate MFA activation/deactivation page."""
    if is_mfa_enabled(request.user):
        return redirect("profile_deactivate_totp")
    return redirect("profile_activate_totp")


class MarketSphereMFAAuthenticateView(AuthenticateView):
    """Use the branded MFA sign-in challenge for allauth's MFA stage."""
    template_name = "mfa/authenticate.html"


class MarketSphereMFAReauthenticateView(ReauthenticateView):
    """Use the branded identity confirmation page for protected actions."""
    template_name = "mfa/reauthenticate.html"


class ProfileActivateTOTPView(ActivateTOTPView):
    """Custom-templated TOTP activation logic."""
    template_name = "profile_2fa_activate.html"

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, HttpResponseRedirect) and response.url == reverse("mfa_deactivate_totp"):
            return redirect("profile_deactivate_totp")
        return response

    def get_success_url(self) -> str:
        if self.did_generate_recovery_codes:
            return reverse("profile_2fa_recovery")
        return reverse("profile")


class ProfileDeactivateTOTPView(DeactivateTOTPView):
    """Custom-templated TOTP deactivation confirmation."""
    template_name = "profile_2fa_deactivate.html"
    success_url = reverse_lazy("profile")

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, HttpResponseRedirect) and response.url == reverse("mfa_activate_totp"):
            return redirect("profile_activate_totp")
        return response


class ProfileViewRecoveryCodesView(ViewRecoveryCodesView):
    """Custom-templated recovery-codes display."""
    template_name = "profile_2fa_recovery.html"