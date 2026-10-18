from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from products import services


@login_required
def wishlist(request: HttpRequest) -> HttpResponse:
    """Render the current user's wishlist page."""
    wishlist_items = services.get_user_wishlist(request.user)
    context = {
        "wishlist_products": wishlist_items,
        "wishlist_count": services.wishlist_count(request.user),
    }
    return render(request, "wishlist.html", context)


@login_required
@require_POST
def toggle_wishlist(request: HttpRequest, product_slug: str) -> JsonResponse:
    """AJAX endpoint to add or remove a product from the wishlist."""
    is_added = services.toggle_wishlist(request.user, product_slug)
    return JsonResponse({
        "success": True,
        "is_added": is_added,
        "wishlist_count": services.wishlist_count(request.user),
    })