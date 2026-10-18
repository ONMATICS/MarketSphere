from typing import Any

from allauth.account.models import EmailAddress

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from accounts import validator
from accounts.models import User, UserPreferences
from notifications.emails.account import send_welcome_email


def create_user(user: dict[str, str]) -> User:
    """Create a new unverified user and send a welcome email."""
    new_user = User.objects.create_user(
        first_name=user["first_name"],
        last_name=user["last_name"],
        username=user["username"],
        email=user["email"],
        contact=user["contact"],
        password=user["password"],
        account_status=User.AccountStatus.UNVERIFIED,
    )
    transaction.on_commit(lambda: send_welcome_email(new_user))
    return new_user


def change_user_password(
    user: User, current_password: str, new_password: str, confirm_password: str
) -> User:
    """Update a user's password after validating the current and new passwords."""
    if not current_password:
        raise ValueError("Please enter your current password.")
    if not new_password:
        raise ValueError("Please enter a new password.")
    if not confirm_password:
        raise ValueError("Please confirm your new password.")
    if not user.check_password(current_password):
        raise ValueError("Your current password is incorrect.")
    if user.check_password(new_password):
        raise ValueError("Your new password must be different from your current password.")
    if new_password != confirm_password:
        raise ValueError("New password and confirmation don't match.")

    try:
        validate_password(new_password, user)
    except ValidationError as error:
        raise ValueError(" ".join(error.messages))

    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user


def get_user_by_identifier(identifier: str) -> User | None:
    """Retrieve a user by either email or username."""
    try:
        if validator.validate_identifier(identifier):
            return User.objects.get(email=identifier)
        return User.objects.get(username=identifier)
    except User.DoesNotExist:
        return None


def get_or_create_primary_email_address(user: User) -> EmailAddress:
    """Ensure the user has a primary EmailAddress record for verification."""
    email = (user.email or "").strip().lower()
    if not email:
        raise ValueError("User must have an email address before verification can be sent.")

    email_address, created = EmailAddress.objects.get_or_create(
        user=user,
        email=email,
        defaults={"primary": True, "verified": False},
    )

    if created:
        return email_address

    if not email_address.primary:
        email_address.set_as_primary()

    return email_address


def send_verification_email(request: HttpRequest | None, user: User, signup: bool = False) -> bool:
    """Send an email verification link to the user."""
    email_address = get_or_create_primary_email_address(user)
    if email_address.verified:
        return False

    email_address.send_confirmation(request, signup=signup)
    return True


def get_all_buyers() -> QuerySet[User]:
    """Retrieve all standard users in the system."""
    return User.objects.all()


def change_account_state(user_id: int, state: str) -> None:
    """Update a user's top-level account status."""
    user = get_object_or_404(User, id=user_id)
    user.account_status = state
    user.save(update_fields=["account_status"])


@transaction.atomic
def update_buyer_profile(
    *,
    user: User,
    first_name: str | None = None,
    last_name: str | None = None,
    username: str | None = None,
    email: str | None = None,
    contact: str | None = None,
    account_status: str | None = None,
    profile_image: str | None = None,
    allow_status_change: bool = False,
    request: HttpRequest | None = None,
) -> tuple[bool, str, User | None, bool, dict[str, list[str]]]:
    """Update a buyer's profile information."""
    errors: dict[str, list[str]] = {}

    if username is not None:
        username = username.strip()
        if not username:
            errors["username"] = ["Username is required."]
        elif User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
            errors["username"] = ["This username is already taken."]

    email_changed = False
    if email is not None:
        email = email.strip()
        if not email:
            errors["email"] = ["Email address is required."]
        else:
            current_email = (user.email or "").strip().lower()
            new_email = email.lower()
            email_changed = current_email != new_email

            if email_changed:
                email_in_use = (
                    EmailAddress.objects.filter(email__iexact=email)
                    .exclude(user=user)
                    .exists()
                )
                if email_in_use:
                    errors["email"] = ["This email address is already in use."]

    if errors:
        return False, "Please correct the errors.", None, False, errors

    if first_name is not None:
        user.first_name = first_name.strip()
    if last_name is not None:
        user.last_name = last_name.strip()
    if username is not None:
        user.username = username
    if contact is not None:
        user.contact = contact.strip()
    if allow_status_change and account_status is not None:
        user.account_status = account_status.strip()
    if profile_image is not None:
        user.profile_image_url = profile_image
    if email_changed:
        user.email = email

    user.save()

    if email_changed:
        EmailAddress.objects.filter(user=user).update(primary=False)
        email_address, created = EmailAddress.objects.get_or_create(
            user=user,
            email=email,
            defaults={"primary": True, "verified": False},
        )

        if not created:
            email_address.primary = True
            email_address.verified = False
            email_address.save(update_fields=["primary", "verified"])

        user.account_status = User.AccountStatus.UNVERIFIED
        user.save(update_fields=["account_status"])

        if request is not None:
            email_address.send_confirmation(request, signup=False)

    message = (
        "Profile updated successfully."
        if not email_changed
        else "Your email address was changed. Please verify your new email address."
    )

    return True, message, user, email_changed, {}


@transaction.atomic
def update_user_preferences(user: User, data: dict[str, Any]) -> UserPreferences:
    """Update general communication and platform preferences for a user."""
    preferences_data = data.get("preferences", {})
    channels_data = data.get("channels", {})

    if not isinstance(preferences_data, dict):
        raise ValueError("Invalid preferences data.")
    if not isinstance(channels_data, dict):
        raise ValueError("Invalid notification channels data.")

    preferences, _ = UserPreferences.objects.get_or_create(user=user)

    preference_fields = {
        "order_updates",
        "promotional_emails",
        "price_drop_alerts",
        "wishlist_alerts",
        "review_reminders",
        "newsletter",
    }
    channel_fields = {
        "email": "email_notifications",
        "in_app": "in_app_notifications",
        "push": "push_notifications",
    }

    for field in preference_fields:
        if field in preferences_data:
            value = preferences_data[field]
            if not isinstance(value, bool):
                raise ValueError(f"Invalid value for {field}.")
            setattr(preferences, field, value)

    for channel_key, field in channel_fields.items():
        if channel_key in channels_data:
            value = channels_data[channel_key]
            if not isinstance(value, bool):
                raise ValueError(f"Invalid value for {channel_key}.")
            setattr(preferences, field, value)

    preferences.save()
    return preferences