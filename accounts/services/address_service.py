from typing import Any

from django.db import transaction
from django.db.models import QuerySet

from accounts.models import Address, Seller, User
from .seller_service import update_application_progress


@transaction.atomic
def save_user_address(
    user: User,
    address_data: dict[str, Any],
) -> Address:
    """Create or update a user's address using supported payload formats."""
    address_id = str(address_data.get("addressId") or "").strip()

    if address_id and address_id.lower() != "null":
        try:
            address = Address.objects.get(
                id=address_id,
                user=user,
            )
        except (Address.DoesNotExist, ValueError):
            raise ValueError("Address not found.")
    else:
        address = Address(user=user)

    address.full_name = str(
        address_data.get("fullName", "")
    ).strip()

    address.phone = str(
        address_data.get("phoneNumber", address_data.get("phone", ""))
    ).strip()

    address.address_line_1 = str(
        address_data.get("address", "")
    ).strip()

    address.address_line_2 = str(
        address_data.get("addressLine2", "")
    ).strip()

    address.city = str(
        address_data.get("city", "")
    ).strip()

    address.postal_code = str(
        address_data.get("ptCode", address_data.get("postalCode", ""))
    ).strip()

    address.address_type = str(
        address_data.get("label", address_data.get("type", ""))
    ).strip()

    is_default = address_data.get("isDefault", False) is True

    if not address.pk and not user.addresses.exists():
        is_default = True

    if is_default:
        Address.objects.filter(user=user).exclude(
            pk=address.pk
        ).update(is_default=False)

    address.is_default = is_default
    address.save()

    return address


def get_user_addresses(user: User) -> QuerySet[Address]:
    """Retrieve all addresses associated with a user."""
    return user.addresses.all()


def get_default_address(user: User) -> Address | None:
    """Retrieve the user's default active address."""
    return user.addresses.filter(is_default=True).first()


@transaction.atomic
def delete_user_address(
    user: User,
    address_id: int | str | dict[str, Any] | None,
) -> bool:
    """Delete a user's address and preserve the default-address behavior."""
    if isinstance(address_id, dict):
        address_id = address_id.get("addressId")

    if address_id is None:
        raise ValueError("Address not found.")

    try:
        address = Address.objects.get(
            id=address_id,
            user=user,
        )
    except (Address.DoesNotExist, ValueError, TypeError):
        raise ValueError("Address not found.")

    was_default = address.is_default

    address.delete()

    if was_default:
        next_address = user.addresses.first()

        if next_address:
            next_address.is_default = True
            next_address.save(update_fields=["is_default"])

    return True


def get_bussiness_address(seller: Seller) -> Address | None:
    """Retrieve the main business address for a seller.

    Note: The method name intentionally preserves a historical typo 
    ("bussiness") to avoid breaking existing service consumers.
    """
    return seller.user.addresses.filter(address_type=Address.BUSINESS).first()


def update_seller_address(user: User, data: dict[str, Any]) -> Address:
    """Update a seller's business address parameters."""
    seller = user.seller_profile
    seller_address = get_bussiness_address(seller)

    if seller_address is None:
        raise ValueError("Business address not found.")

    seller_address.full_name = str(data.get("fullName", "")).strip()
    seller_address.phone = str(data.get("phone", "")).strip()
    seller_address.address_line_1 = str(data.get("address", "")).strip()
    seller_address.city = str(data.get("city", "")).strip()
    seller_address.postal_code = str(data.get("postalCode", "")).strip()

    seller_address.save()
    update_application_progress(seller)
    return seller_address