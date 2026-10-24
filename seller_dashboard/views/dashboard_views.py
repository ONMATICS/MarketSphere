from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from services.decorators.decorators import verified_seller
from accounts.services import get_seller_application_documents


@verified_seller
def dashboard(request: HttpRequest) -> HttpResponse:
    """Render the main seller dashboard overview."""
    seller = request.user.seller_profile
    return render(request, "dashboard.html", {"seller": seller})


@verified_seller
def dashboard_settings(request: HttpRequest) -> HttpResponse:
    """Render the seller settings and application documents page."""
    seller = request.user.seller_profile
    documents = get_seller_application_documents(seller)
    return render(request, "settings.html", {"seller": seller, "documents": documents})
