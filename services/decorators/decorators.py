"""Opt-in access-control decorators for MarketSphere.

MarketSphere has no separate business-role model. User roles therefore remain
Django authentication flags and Django groups/permissions, while seller
eligibility remains the real ``accounts.Seller`` relationship and status.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse


View = TypeVar("View", bound=Callable[..., HttpResponse])
ResourceResolver = Callable[..., Any]
OwnerResolver = Callable[[Any], Any]


def _account_is_active(user: Any) -> bool:
    """Apply the project's account-wide status policy, failing closed."""
    if not getattr(user, "is_active", False):
        return False

    # AuthenticationMiddleware supplies request.user as a SimpleLazyObject;
    # access the proxied attribute instead of inspecting its wrapper type.
    status_enum = getattr(user, "AccountStatus", None)
    if status_enum is None:
        return False

    return getattr(user, "account_status", None) in {
        status_enum.UNVERIFIED,
        status_enum.VERIFIED,
    }


def _seller(user: Any) -> Any | None:
    """Return the actual seller relationship, never a client-supplied ID."""
    return getattr(user, "seller_profile", None)


def _protected(view_func: View, check: Callable[[Any], bool]) -> View:
    """Compose Django's normal login redirect with a fail-closed check."""
    @login_required
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not _account_is_active(request.user) or not check(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def _email_is_verified(user: Any) -> bool:
    """Require both the project's verified status and allauth verification."""
    status_enum = getattr(user, "AccountStatus", None)
    if status_enum is None or getattr(user, "account_status", None) != status_enum.VERIFIED:
        return False

    # Delayed import avoids an allauth/model import during package loading.
    from allauth.account.models import EmailAddress

    return EmailAddress.objects.filter(user=user, primary=True, verified=True).exists()


def authenticated(view_func: View) -> View:
    """Require an authenticated, active, non-suspended account."""
    return _protected(view_func, lambda user: True)


def verified_email_required(view_func: View) -> View:
    """Require an active account with a persisted verified email address."""
    return _protected(view_func, _email_is_verified)


def verified_user(view_func: View) -> View:
    """Backward-compatible alias for :func:`verified_email_required`."""
    return verified_email_required(view_func)


def buyer_required(view_func: View) -> View:
    """Require an active buyer account.

    The project has no buyer role field; every active ``User`` is buyer-eligible.
    """
    return authenticated(view_func)


def verified_buyer_required(view_func: View) -> View:
    """Require an active buyer account with a verified email address."""
    return verified_email_required(view_func)


def seller_required(view_func: View) -> View:
    """Require an active account with an actual ``seller_profile`` relation."""
    return _protected(view_func, lambda user: _seller(user) is not None)


def only_seller(view_func: View) -> View:
    """Backward-compatible alias for :func:`seller_required`."""
    return seller_required(view_func)


def verified_seller(view_func: View) -> View:
    """Require an active, approved seller; seller suspension is denied."""
    def is_verified(user: Any) -> bool:
        seller = _seller(user)
        status = getattr(seller, "Status", None) if seller is not None else None
        return status is not None and getattr(seller, "status", None) == status.VERIFIED

    return _protected(view_func, is_verified)


def permission_required(*permissions: str, any_permission: bool = False) -> Callable[[View], View]:
    """Require explicit Django permissions, directly or through groups."""
    if not permissions or any(not isinstance(permission, str) or not permission for permission in permissions):
        raise ValueError("At least one non-empty permission string is required.")

    def decorator(view_func: View) -> View:
        def has_required_permissions(user: Any) -> bool:
            checks = [user.has_perm(permission) for permission in permissions]
            return any(checks) if any_permission else all(checks)

        return _protected(view_func, has_required_permissions)

    return decorator


def admin_required(view_func: View) -> View:
    """Require Django admin access without granting every admin permission."""
    return _protected(
        view_func,
        lambda user: bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False)),
    )


ADMIN_ROLE_PERMISSIONS = {
    "Seller Admin": (
        "accounts.view_seller", "accounts.change_seller",
        "accounts.view_sellerapplication", "accounts.change_sellerapplication",
        "accounts.view_sellerapplicationdocument", "accounts.change_sellerapplicationdocument",
        "accounts.view_sellerapplicationflag", "accounts.change_sellerapplicationflag",
        "accounts.view_sellerprofile", "accounts.change_sellerprofile",
        "accounts.view_sellersettings", "accounts.change_sellersettings",
    ),
    "Buyer Admin": (
        "accounts.view_user", "accounts.change_user",
        "accounts.view_address", "accounts.change_address",
        "accounts.view_userpreferences", "accounts.change_userpreferences",
    ),
    "Product Admin": (
        "products.view_product", "products.add_product", "products.change_product", "products.delete_product",
        "products.view_productimage", "products.add_productimage", "products.change_productimage",
        "products.delete_productimage",
    ),
    "Order Admin": (
        "orders.view_order", "orders.change_order",
        "orders.view_orderitem", "orders.change_orderitem",
        "orders.view_sellerorder", "orders.change_sellerorder",
    ),
    "Catalog Admin": (
        "products.view_product", "products.add_product", "products.change_product", "products.delete_product",
        "products.view_productimage", "products.add_productimage", "products.change_productimage",
        "products.delete_productimage", "products.view_category", "products.add_category",
        "products.change_category", "products.delete_category", "products.view_brand", "products.add_brand",
        "products.change_brand", "products.delete_brand",
    ),
    "Payment Admin": (
        "orders.view_order", "orders.change_order",
    ),
    "Customer Support Admin": (
        "support.view_supportrequest", "support.change_supportrequest",
        "support.view_supportmessage", "support.change_supportmessage",
        "support.view_review", "support.change_review",
        "support.view_reviewreport", "support.change_reviewreport",
    ),
}

CATALOG_PERMISSIONS = ADMIN_ROLE_PERMISSIONS["Catalog Admin"]


def catalog_admin_required(view_func: View) -> View:
    """Require superuser or an explicit catalog permission.

    No Catalog Admin group is configured in this repository, so access is
    based on Django permissions rather than an untrusted group name.
    """
    return _protected(
        view_func,
        lambda user: bool(getattr(user, "is_superuser", False))
        or any(user.has_perm(permission) for permission in CATALOG_PERMISSIONS),
    )


def ownership_required(
    resource_resolver: ResourceResolver,
    owner_resolver: OwnerResolver,
) -> Callable[[View], View]:
    """Require ownership of a server-resolved resource.

    ``resource_resolver`` must retrieve the resource from route arguments or a
    server-side query. ``owner_resolver`` must return its actual related user,
    such as ``lambda order: order.user`` or ``lambda item: item.cart.user``.
    Client-supplied ``user_id`` values are never authorization evidence.
    """
    if not callable(resource_resolver) or not callable(owner_resolver):
        raise TypeError("Both resource_resolver and owner_resolver must be callable.")

    def decorator(view_func: View) -> View:
        @login_required
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            resource = resource_resolver(request, *args, **kwargs)
            owner = owner_resolver(resource) if resource is not None else None
            if not _account_is_active(request.user) or owner is None or owner != request.user:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "ADMIN_ROLE_PERMISSIONS", "CATALOG_PERMISSIONS", "admin_required", "authenticated", "buyer_required",
    "catalog_admin_required", "only_seller", "ownership_required",
    "permission_required", "seller_required", "verified_buyer_required",
    "verified_email_required", "verified_seller", "verified_user",
]
