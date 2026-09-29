from decimal import Decimal

from allauth.account.models import EmailAddress
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum, Q, DecimalField, Value, Count
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from notifications.emails.sellers import (
    send_application_received_email,
    send_application_incomplete_email,
    send_seller_verified_email,
    send_seller_rejected_email,
)
from notifications.emails.account import (
    send_welcome_email,
    send_verification_email as send_successfully_verification_email,
)
from notifications.models import ActivityLog
from orders.models import Order
from . import validator
from .models import (
    User,
    Address,
    Seller,
    SellerApplication,
    SellerApplicationDocument,
    SellerSettings,
    SellerProfile,
)
from services.cloudinary_service import store_seller_asset

# ==============================================================================
# USER SERVICES
# ==============================================================================


def create_user(user):
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


from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def change_user_password(user, current_password, new_password, confirm_password):
    if not current_password:
        raise ValueError("Please enter your current password.")

    if not new_password:
        raise ValueError("Please enter a new password.")

    if not confirm_password:
        raise ValueError("Please confirm your new password.")

    if not user.check_password(current_password):
        raise ValueError("Your current password is incorrect.")

    if user.check_password(new_password):
        raise ValueError(
            "Your new password must be different from your current password."
        )

    if new_password != confirm_password:
        raise ValueError("New password and confirmation don't match.")

    try:
        validate_password(new_password, user)
    except ValidationError as error:
        raise ValueError(" ".join(error.messages))

    user.set_password(new_password)
    user.save(update_fields=["password"])

    return user


def get_user_by_identifier(identifier):
    try:
        if validator.validate_identifier(identifier):
            return User.objects.get(email=identifier)
        return User.objects.get(username=identifier)
    except User.DoesNotExist:
        return None


def get_or_create_primary_email_address(user):
    email = (user.email or "").strip().lower()
    if not email:
        raise ValueError(
            "User must have an email address before verification can be sent."
        )

    email_address, created = EmailAddress.objects.get_or_create(
        user=user,
        email=email,
        defaults={
            "primary": True,
            "verified": False,
        },
    )

    if created:
        return email_address

    if not email_address.primary:
        email_address.set_as_primary()

    return email_address


def send_verification_email(request, user, signup=False):
    email_address = get_or_create_primary_email_address(user)

    if email_address.verified:
        return False

    email_address.send_confirmation(request, signup=signup)
    return True


def get_all_buyers():
    return User.objects.all()


def change_account_state(user_id, state):
    user = get_object_or_404(User, id=user_id)
    user.account_status = state
    user.save(update_fields=["account_status"])


from django.contrib.auth import get_user_model
from django.db import transaction
from allauth.account.models import EmailAddress

User = get_user_model()


@transaction.atomic
def update_buyer_profile(
    *,
    user,
    first_name=None,
    last_name=None,
    username=None,
    email=None,
    contact=None,
    account_status=None,
    profile_image=None,
    allow_status_change=False,
    request=None,
):
    errors = {}

    if username is not None:
        username = username.strip()

        if not username:
            errors["username"] = ["Username is required."]
        elif (
            User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists()
        ):
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
        EmailAddress.objects.filter(user=user).update(
            primary=False,
        )

        email_address, created = EmailAddress.objects.get_or_create(
            user=user,
            email=email,
            defaults={
                "primary": True,
                "verified": False,
            },
        )

        if not created:
            email_address.primary = True
            email_address.verified = False
            email_address.save(update_fields=["primary", "verified"])

        user.account_status = User.AccountStatus.UNVERIFIED
        user.save(update_fields=["account_status"])

        if request is not None:
            email_address.send_confirmation(
                request,
                signup=False,
            )

    message = (
        "Profile updated successfully."
        if not email_changed
        else "Your email address was changed. " "Please verify your new email address."
    )

    return True, message, user, email_changed, {}


# ==============================================================================
# ADDRESS SERVICES
# ==============================================================================


def save_user_address(user, address_data):
    address_id = address_data.get("addressId")

    if address_id in (None, "", "null"):
        address = Address(
            user=user,
        )
    else:
        address = get_object_or_404(
            Address,
            id=address_id,
            user=user,
        )

    address.address_type = address_data["label"]
    address.full_name = address_data["fullName"]
    address.phone = address_data["phoneNumber"]
    address.address_line_1 = address_data["address"]
    address.address_line_2 = address_data.get("addressLine2", "")
    address.city = address_data["city"]
    address.postal_code = address_data["ptCode"]
    address.is_default = address_data.get(
        "isDefault",
        False,
    )

    address.save()

    return address


def delete_address(user, address_id):
    address = get_object_or_404(
        Address,
        id=address_id,
        user=user,
    )
    address.delete()


def get_user_addresses(user):
    return user.addresses.all()


def get_default_address(user):
    return user.addresses.filter(
        is_default=True,
    ).first()


@transaction.atomic
def update_user_address(user, data):
    address_id = data.get("addressId", "").strip()

    try:
        user_address = Address.objects.get(
            id=address_id,
            user=user,
        )
    except Address.DoesNotExist:
        raise ValueError("Address not found.")

    user_address.full_name = data.get("fullName", "").strip()
    user_address.phone = data.get("phone", "").strip()
    user_address.address_line_1 = data.get("address", "").strip()
    user_address.address_line_2 = data.get("addressLine2", "").strip()
    user_address.city = data.get("city", "").strip()
    user_address.postal_code = data.get("postalCode", "").strip()
    user_address.address_type = data.get("type", "").strip()

    is_default = data.get("isDefault") is True

    if is_default:
        Address.objects.filter(user=user).exclude(id=user_address.id).update(
            is_default=False
        )

    user_address.is_default = is_default
    user_address.save()

    return user_address


@transaction.atomic
def delete_user_address(user, data):
    address_id = data.get("addressId", "").strip()

    try:
        address = Address.objects.get(id=address_id, user=user)
    except Address.DoesNotExist:
        raise ValueError("Address not found.")

    if address.is_default:
        next_address = Address.objects.filter(user=user).exclude(id=address.id).first()

        if next_address:
            next_address.is_default = True
            next_address.save(update_fields=["is_default"])

    address.delete()
    return True


def get_bussiness_address(seller):
    business_address = seller.user.addresses.filter(
        address_type=Address.BUSINESS
    ).first()
    return business_address


def update_seller_address(user, data):
    seller = user.seller_profile
    seller_address = get_bussiness_address(seller)

    if seller_address is None:
        raise ValueError("Business address not found.")

    seller_address.full_name = data.get("fullName", "").strip()
    seller_address.phone = data.get("phone", "").strip()
    seller_address.address_line_1 = data.get("address", "").strip()
    seller_address.city = data.get("city", "").strip()
    seller_address.postal_code = data.get("postalCode", "").strip()

    seller_address.save()
    update_application_progress(seller)
    return seller_address


# ==============================================================================
# SELLER APPLICATION & MANAGEMENT SERVICES
# ==============================================================================


def reject_seller_application_service(application_id, reason, notes):
    application = SellerApplication.objects.get(pk=application_id)

    application.status = SellerApplication.Status.REJECTED
    application.rejection_reason = reason
    application.admin_notes = notes
    application.reviewed_at = timezone.now()

    application.save(
        update_fields=[
            "status",
            "rejection_reason",
            "admin_notes",
            "reviewed_at",
        ]
    )

    transaction.on_commit(lambda: send_seller_rejected_email(application, reason))

    return application


@transaction.atomic
def request_application_changes_service(application_id, requested_changes, notes):
    application = SellerApplication.objects.select_related("seller").get(
        pk=application_id
    )

    seller = application.seller
    message = notes.strip()

    if requested_changes:
        checklist = "\n".join(f"• {item}" for item in requested_changes)

        if message:
            message = f"{message}\n\nRequested Changes:\n{checklist}"
        else:
            message = f"Requested Changes:\n{checklist}"

    application.status = SellerApplication.Status.CHANGES_REQUESTED
    application.admin_notes = message
    application.reviewed_at = timezone.now()

    application.save(
        update_fields=[
            "status",
            "admin_notes",
            "reviewed_at",
        ]
    )

    seller.status = Seller.Status.PENDING
    seller.save(update_fields=["status"])
    transaction.on_commit(lambda: send_seller_rejected_email(application, notes))
    return application


@transaction.atomic
def approve_seller_application_service(application_id):
    application = SellerApplication.objects.select_related(
        "seller",
        "seller__user",
    ).get(pk=application_id)

    seller = application.seller

    application.status = SellerApplication.Status.APPROVED
    application.reviewed_at = timezone.now()
    application.save(
        update_fields=[
            "status",
            "reviewed_at",
        ]
    )

    seller.status = Seller.Status.VERIFIED
    seller.save(update_fields=["status"])

    transaction.on_commit(
        lambda seller=seller: send_seller_verified_email(seller),
        robust=True,
    )

    return application


@transaction.atomic
def delete_seller_account_service(seller_id):
    seller = Seller.objects.get(pk=seller_id)
    seller.delete()


def flag_seller_document_service(*, document_id, issue, note):
    document = SellerApplicationDocument.objects.get(pk=document_id)
    document.verified = False
    message = issue

    if note:
        message += f"\n\n{note}"

    document.verification_note = message
    document.save(
        update_fields=[
            "verified",
            "verification_note",
        ]
    )

    return document


def verify_seller_document_service(document_id, document_type):
    document = get_object_or_404(
        SellerApplicationDocument,
        id=document_id,
        document_type=document_type,
    )

    document.verified = True
    document.verification_note = ""
    document.save(
        update_fields=[
            "verified",
            "verification_note",
        ]
    )

    return document


def request_missing_document_service(application_id, document_type, reason, note):
    seller = get_object_or_404(Seller, id=application_id)
    application = seller.application

    document, created = SellerApplicationDocument.objects.get_or_create(
        application=application,
        document_type=document_type,
    )

    document.verified = False
    document.verification_note = f"{reason}\n\n{note}"

    document.save(
        update_fields=[
            "verified",
            "verification_note",
        ]
    )

    return document


def save_application_notes_service(application_id, notes):
    application = get_object_or_404(SellerApplication, pk=application_id)
    application.admin_notes = notes
    application.save(
        update_fields=[
            "admin_notes",
        ]
    )

    return application


def calculate_application_progress(seller):
    completed = 0
    total = 0
    missing = []

    profile = getattr(seller, "profile", None)
    address = seller.business_address
    application = getattr(seller, "application", None)

    documents = {}

    if application:
        documents = {
            document.document_type: document for document in application.documents.all()
        }

    def check(condition, label):
        nonlocal completed, total
        total += 1
        if condition:
            completed += 1
        else:
            missing.append(label)

    # Store Information
    check(bool(seller.store_name), "Store Name")
    check(bool(seller.store_email), "Store Email")
    check(bool(seller.store_description), "Store Description")
    check(bool(seller.store_logo), "Store Logo")

    # Business Address
    check(address and address.full_name, "Business Contact")
    check(address and address.phone, "Business Phone")
    check(address and address.address_line_1, "Business Address")
    check(address and address.city, "City")
    check(address and address.postal_code, "Postal Code")

    # Seller Profile
    check(profile and profile.business_category, "Business Category")
    check(profile and profile.business_type, "Business Type")
    check(profile and profile.national_id_number, "National ID Number")

    # Required Documents
    check(
        SellerApplicationDocument.DocumentType.CNIC_FRONT in documents,
        "CNIC Front",
    )
    check(
        SellerApplicationDocument.DocumentType.CNIC_BACK in documents,
        "CNIC Back",
    )
    check(
        SellerApplicationDocument.DocumentType.STORE_PHOTO in documents,
        "Store Photo",
    )

    progress = round((completed / total) * 100) if total else 0

    return {
        "progress": progress,
        "completed": completed,
        "total": total,
        "missing": missing,
        "is_complete": progress == 100,
    }


def update_application_progress(seller):
    progress = calculate_application_progress(seller)

    application = seller.application
    was_submitted = application.status == SellerApplication.Status.SUBMITTED

    if progress["is_complete"]:
        seller.status = Seller.Status.PENDING
        seller.save(update_fields=["status"])

        application.status = SellerApplication.Status.SUBMITTED
        application.save(update_fields=["status"])
        print("Application submitted, sending email...")
        transaction.on_commit(lambda: send_application_received_email(application))

    else:
        seller.status = Seller.Status.DRAFT
        seller.save(update_fields=["status"])

        application.status = SellerApplication.Status.DRAFT
        application.save(update_fields=["status"])

    return progress


@transaction.atomic
def create_seller_application(user, data, files):
    if hasattr(user, "contact"):
        user.contact = data.get("phone", "").strip()
        user.save(update_fields=["contact"])

    Address.objects.update_or_create(
        user=user,
        address_type=Address.BUSINESS,
        defaults={
            "full_name": data.get("fullName"),
            "phone": data.get("phone"),
            "address_line_1": data.get("address_line_1"),
            "address_line_2": data.get("address_line_2", ""),
            "city": data.get("city"),
            "postal_code": data.get("postal_code"),
        },
    )

    base_slug = slugify(data.get("store_name"))
    slug = base_slug
    counter = 1

    while Seller.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    if hasattr(user, "seller_profile"):
        raise ValueError("Seller profile already exists.")

    seller = Seller.objects.create(
        user=user,
        store_name=data.get("store_name"),
        slug=slug,
        store_email=data.get("store_email"),
        store_description=data.get("description"),
    )

    seller_uploads = {}
    for field_name, resource_type in (("store_logo", "image"), ("store_banner", "image")):
        uploaded_file = files.get(field_name)
        if uploaded_file:
            result = store_seller_asset(
                uploaded_file,
                seller_id=str(seller.id),
                asset_type=field_name,
                resource_type=resource_type,
            )
            seller_uploads[field_name] = result.get("secure_url") or result.get("url")

    if seller_uploads:
        seller.store_logo = seller_uploads.get("store_logo")
        seller.store_banner = seller_uploads.get("store_banner")
        seller.save(update_fields=list(seller_uploads))

    application = SellerApplication.objects.create(
        seller=seller,
        status=SellerApplication.Status.DRAFT,
        submitted_at=timezone.now(),
        application_source="Website",
        referral_code=data.get("referral_code", ""),
    )

    document_mapping = {
        SellerApplicationDocument.DocumentType.CNIC_FRONT: "cnic_front",
        SellerApplicationDocument.DocumentType.CNIC_BACK: "cnic_back",
        SellerApplicationDocument.DocumentType.BUSINESS_CERTIFICATE: "business_certificate",
        SellerApplicationDocument.DocumentType.NTN: "ntn_certificate",
        SellerApplicationDocument.DocumentType.BANK_STATEMENT: "bank_statement",
        SellerApplicationDocument.DocumentType.STORE_PHOTO: "store_photo",
    }

    for document_type, input_name in document_mapping.items():
        uploaded_file = files.get(input_name)

        if uploaded_file:
            result = store_seller_asset(
                uploaded_file,
                seller_id=str(seller.id),
                asset_type=document_type,
                resource_type="auto",
            )
            document_url = result.get("secure_url") or result.get("url")
            SellerApplicationDocument.objects.create(
                application=application,
                document_type=document_type,
                file=document_url,
            )

    SellerSettings.objects.create(
        seller=seller,
        business_registration_number=data.get(
            "business_registration_number",
            "",
        ),
        tax_id=data.get("tax_id", ""),
    )

    SellerProfile.objects.create(
        seller=seller,
        business_category=data.get("business_category", ""),
        business_type=data.get("business_type", ""),
        national_id_number=data.get("national_id_number", ""),
        years_in_business=data.get("years_in_business") or None,
        expected_monthly_volume=data.get(
            "expected_monthly_volume",
            "",
        ),
        product_categories=data.get("product_categories", ""),
        website=data.get("website", ""),
        facebook_label=data.get("facebook_label", ""),
        facebook_url=data.get("facebook_url", ""),
        linkedin_label=data.get("linkedin_label", ""),
        linkedin_url=data.get("linkedin_url", ""),
        instagram_label=data.get("instagram_label", ""),
        instagram_url=data.get("instagram_url", ""),
        twitter_label=data.get("twitter_label", ""),
        twitter_url=data.get("twitter_url", ""),
    )

    transaction.on_commit(lambda: send_application_incomplete_email(seller))

    return seller


# ==============================================================================
# SELLER PROFILE, SETTINGS & ANALYTICS
# ==============================================================================


def get_all_sellers():
    # UPDATED: We now query Order.Status.DELIVERED directly instead of SellerOrder
    return Seller.objects.annotate(
        total_sales=Coalesce(
            Sum(
                "orders__total",
                filter=Q(orders__status=Order.Status.DELIVERED),
            ),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )


def update_seller_information(user, data, files):
    seller = user.seller_profile

    # Update store name and slug if changed
    store_name = (data.get("store_name") or "").strip()
    if store_name and store_name != seller.store_name:
        base_slug = slugify(store_name)
        slug = base_slug
        counter = 1
        while Seller.objects.filter(slug=slug).exclude(pk=seller.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        seller.store_name = store_name
        seller.slug = slug

    # Update other simple fields
    store_email = data.get("store_email")
    if store_email is not None:
        seller.store_email = store_email

    store_description = data.get("store_description")
    if store_description is not None:
        seller.store_description = store_description

    # Update files if provided
    store_logo = files.get("store_logo")
    if store_logo:
        result = store_seller_asset(store_logo, str(seller.id), "store_logo", "image")
        seller.store_logo = result.get("secure_url") or result.get("url")

    store_banner = files.get("store_banner")
    if store_banner:
        result = store_seller_asset(store_banner, str(seller.id), "store_banner", "image")
        seller.store_banner = result.get("secure_url") or result.get("url")

    seller.save()
    update_application_progress(seller)
    return seller


def update_store_information(seller, data):
    seller.store_name = data.get("store_name", "")
    seller.slug = data.get("slug", "")
    seller.store_email = data.get("store_email", "")
    seller.store_description = data.get("store_description", "")
    seller.business_registration_number = data.get("business_registration_number", "")
    seller.tax_id = data.get("tax_id", "")
    seller.save()

    seller.user.contact = data.get("store_phone", "")
    seller.user.save(update_fields=["contact"])

    profile, _ = SellerProfile.objects.get_or_create(seller=seller)
    profile.business_category = data.get("business_category", "")
    profile.website = data.get("website", "")

    profile.facebook_label = data.get("facebook_label", "")
    profile.facebook_url = data.get("facebook_url", "")
    profile.instagram_label = data.get("instagram_label", "")
    profile.instagram_url = data.get("instagram_url", "")
    profile.linkedin_label = data.get("linkedin_label", "")
    profile.linkedin_url = data.get("linkedin_url", "")
    profile.twitter_label = data.get("twitter_label", "")
    profile.twitter_url = data.get("twitter_url", "")
    profile.save()

    address, _ = Address.objects.get_or_create(
        user=seller.user,
        address_type=Address.BUSINESS,
    )
    address.city = data.get("city", "")
    address.address_line_1 = data.get("address_line_1", "")
    address.postal_code = data.get("postal_code", "")
    address.save()

    update_application_progress(seller)
    return seller


def update_seller_status(seller, status):
    seller.status = status
    seller.save(update_fields=["status"])


def change_store_banner(seller_id, banner):
    seller = Seller.objects.filter(id=seller_id).first()
    if not seller:
        return None

    result = store_seller_asset(banner, str(seller.id), "store_banner", "image")
    seller.store_banner = result.get("secure_url") or result.get("url")
    seller.save(update_fields=["store_banner"])
    return seller.store_banner


def update_shipping_preferences(seller, data):
    settings, created = SellerSettings.objects.get_or_create(seller=seller)

    settings.default_courier = data.get("default_courier", "")
    settings.default_handling_time = int(
        data.get("handling_time", SellerSettings.HandlingTime.TWO_DAYS)
    )
    settings.return_address = data.get("return_address", "").strip()
    settings.shipping_notes = data.get("shipping_notes", "").strip()
    settings.auto_mark_shipped = str(data.get("auto_mark_shipped")).lower() == "true"
    settings.shipping_fee = float(data.get("shipping_fee"))

    settings.save()
    return settings


def update_notification_preferences(seller, data):
    settings, _ = SellerSettings.objects.get_or_create(seller=seller)

    settings.email_new_order = str(data.get("email_new_order")).lower() == "true"
    settings.email_cancelled_order = (
        str(data.get("email_cancelled_order")).lower() == "true"
    )
    settings.email_delivered_order = (
        str(data.get("email_delivered_order")).lower() == "true"
    )
    settings.email_low_stock = str(data.get("email_low_stock")).lower() == "true"
    settings.weekly_sales_summary = (
        str(data.get("weekly_sales_summary")).lower() == "true"
    )
    settings.monthly_store_report = (
        str(data.get("monthly_store_report")).lower() == "true"
    )

    settings.save()
    return settings


def deactivate_seller_account(seller):
    seller.status = Seller.Status.DEACTIVATED
    seller.save(update_fields=["status"])


def reactivate_seller_account(seller):
    seller.status = Seller.Status.VERIFIED
    seller.save(update_fields=["status"])


def update_seller_profile_service(user, data):
    try:
        seller = user.seller_profile
    except Exception:
        return False, "Seller account not found."

    profile, _ = SellerProfile.objects.get_or_create(
        seller=seller,
    )

    profile.business_category = data.get("business_category", "")
    profile.business_type = data.get("business_type", "")
    profile.national_id_number = data.get("national_id_number", "")

    years = data.get("years_in_business", "")
    profile.years_in_business = int(years) if years else None

    profile.expected_monthly_volume = data.get("expected_monthly_volume", "")
    profile.product_categories = data.get("product_categories", "")
    profile.website = data.get("website", "")

    profile.facebook_label = data.get("facebook_label", "")
    profile.facebook_url = data.get("facebook_url", "")
    profile.linkedin_label = data.get("linkedin_label", "")
    profile.linkedin_url = data.get("linkedin_url", "")
    profile.instagram_label = data.get("instagram_label", "")
    profile.instagram_url = data.get("instagram_url", "")
    profile.twitter_label = data.get("twitter_label", "")
    profile.twitter_url = data.get("twitter_url", "")

    profile.save()
    update_application_progress(seller)

    return True, "Seller profile updated successfully."


def update_seller_document_service(user, data, files):
    try:
        seller = user.seller_profile
    except Exception:
        return False, "Seller account not found.", None

    try:
        application = SellerApplication.objects.get(
            seller=seller,
        )
    except SellerApplication.DoesNotExist:
        return False, "Seller application not found.", None

    document_type = data.get("document_type")
    uploaded_file = files.get("document")

    if not document_type:
        return False, "Document type is required.", None

    if not uploaded_file:
        return False, "Please select a document.", None

    valid_document_types = {
        choice[0] for choice in SellerApplicationDocument.DocumentType.choices
    }

    if document_type not in valid_document_types:
        return False, "Invalid document type.", None

    document, created = SellerApplicationDocument.objects.get_or_create(
        application=application,
        document_type=document_type,
    )

    result = store_seller_asset(
        uploaded_file,
        seller_id=str(seller.id),
        asset_type=document_type,
        resource_type="auto",
    )
    document.file = result.get("secure_url") or result.get("url")
    document.verified = False
    document.verification_note = ""
    document.save()
    update_application_progress(seller)

    return True, "Document uploaded successfully.", document


def get_seller_application_documents(seller):
    try:
        application = seller.application
    except AttributeError:
        return {}

    uploaded_documents = {
        document.document_type: document for document in application.documents.all()
    }

    return {
        "cnic_front": uploaded_documents.get(
            SellerApplicationDocument.DocumentType.CNIC_FRONT
        ),
        "cnic_back": uploaded_documents.get(
            SellerApplicationDocument.DocumentType.CNIC_BACK
        ),
        "business_certificate": uploaded_documents.get(
            SellerApplicationDocument.DocumentType.BUSINESS_CERTIFICATE
        ),
        "ntn": uploaded_documents.get(SellerApplicationDocument.DocumentType.NTN),
        "bank_statement": uploaded_documents.get(
            SellerApplicationDocument.DocumentType.BANK_STATEMENT
        ),
        "store_photo": uploaded_documents.get(
            SellerApplicationDocument.DocumentType.STORE_PHOTO
        ),
    }


# ==============================================================================
# BUYER PROFILE / MY ACCOUNT SERVICES
# ==============================================================================
#
# NOTE ON ASSUMPTIONS:
# The buyer profile page pulls together data from a few apps whose exact
# schema isn't fully visible from accounts/ alone (orders' three-tier
# Order -> SellerOrder -> OrderItem structure, plus wishlist/reviews/
# notifications models that may live in other apps). Every helper below
# is written defensively with getattr()/hasattr() so the page degrades
# to sensible empty states instead of raising if a related-manager name
# doesn't match your actual models. Search for "ASSUMPTION" and adjust
# the attribute names to match your real schema.
# ==============================================================================


def _order_status_value(order):
    """Returns a lowercase status string, preferring the newer
    `overall_status` computed property and falling back to a flat
    `status` field if that's what exists on this Order instance."""
    value = getattr(order, "overall_status", None)
    if value is None:
        value = getattr(order, "status", "")
    return str(value or "").lower()


def _order_status_display(order):
    if hasattr(order, "get_overall_status_display"):
        try:
            return order.get_overall_status_display()
        except Exception:
            pass
    if hasattr(order, "get_status_display"):
        try:
            return order.get_status_display()
        except Exception:
            pass
    return _order_status_value(order).title() or "—"


def _order_items_count(order):
    """ASSUMPTION: tries the common related_name spellings for an
    order's line items, then falls back to summing items across
    per-seller orders for the three-tier Order -> SellerOrder ->
    OrderItem structure."""
    for attr in ("items", "order_items", "orderitem_set"):
        manager = getattr(order, attr, None)
        if manager is not None and hasattr(manager, "count"):
            try:
                return manager.count()
            except Exception:
                continue

    seller_orders = getattr(order, "seller_orders", None)
    if seller_orders is not None and hasattr(seller_orders, "all"):
        total = 0
        for seller_order in seller_orders.all():
            for attr in ("items", "order_items", "orderitem_set"):
                manager = getattr(seller_order, attr, None)
                if manager is not None and hasattr(manager, "count"):
                    total += manager.count()
                    break
        return total

    return 0


def _get_wishlist_queryset(user):
    """ASSUMPTION: no wishlist model is visible from accounts/, so this
    tries the most likely related-manager names on the user. Update the
    attr list once the wishlist app is finalized, e.g.:
    return user.wishlist_items.select_related('product')
    """
    for attr in ("wishlist_items", "wishlistitem_set", "wishlist_set"):
        manager = getattr(user, attr, None)
        if manager is not None and hasattr(manager, "all"):
            return manager.all()
    return None


def _get_reviews_queryset(user):
    """ASSUMPTION: same caveat as wishlist above — adjust once the
    reviews model/related_name is finalized."""
    for attr in ("review_set", "reviews"):
        manager = getattr(user, attr, None)
        if manager is not None and hasattr(manager, "all"):
            return manager.all()
    return None


def get_buyer_orders_queryset(user):
    return Order.objects.filter(user=user).order_by("-created_at")


def get_buyer_recent_orders(user, limit=5):
    return list(get_buyer_orders_queryset(user)[:limit])


def get_buyer_dashboard_stats(user):
    orders = list(get_buyer_orders_queryset(user))

    total_orders = len(orders)
    completed_orders = sum(
        1
        for order in orders
        if _order_status_value(order) in ("delivered", "completed")
    )
    cancelled_orders = sum(
        1 for order in orders if _order_status_value(order) == "cancelled"
    )
    pending_orders = sum(
        1
        for order in orders
        if _order_status_value(order) in ("pending", "confirmed", "processing")
    )

    total_spent = sum(
        (getattr(order, "total", 0) or 0)
        for order in orders
        if _order_status_value(order) != "cancelled"
    )

    wishlist_qs = _get_wishlist_queryset(user)
    wishlist_count = wishlist_qs.count() if wishlist_qs is not None else 0

    reviews_qs = _get_reviews_queryset(user)
    reviews_count = reviews_qs.count() if reviews_qs is not None else 0

    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "pending_orders": pending_orders,
        "total_spent": total_spent,
        "wishlist_count": wishlist_count,
        "reviews_count": reviews_count,
        "saved_addresses": user.addresses.count(),
    }


def calculate_buyer_profile_completion(user):
    completed = 0
    total = 0
    missing = []

    def check(condition, label):
        nonlocal completed, total
        total += 1
        if condition:
            completed += 1
        else:
            missing.append(label)

    check(bool(user.first_name), "First name")
    check(bool(user.last_name), "Last name")
    check(bool(user.contact), "Phone number")
    check(bool(user.profile_image_url), "Profile photo")
    check(user.addresses.filter(is_default=True).exists(), "Default address")
    check(user.account_status == User.AccountStatus.VERIFIED, "Email verification")

    percentage = round((completed / total) * 100) if total else 0

    return {
        "percentage": percentage,
        "completed": completed,
        "total": total,
        "missing": missing,
        "is_complete": percentage == 100,
    }


from products.models import WishlistItem


def get_buyer_wishlist_preview(user, limit=4):
    return list(
        WishlistItem.objects.filter(user=user)
        .select_related(
            "product",
            "product__brand",
        )
        .prefetch_related(
            "product__images",
        )[:limit]
    )


def get_buyer_recent_activity(user, limit=6):
    order_content_type = ContentType.objects.get_for_model(Order)
    return list(
        ActivityLog.objects.select_related("actor").filter(
            Q(actor=user)
            | Q(
                target_content_type=order_content_type,
                target_object_id__in=user.orders.values("pk"),
            )
        )[:limit]
    )


def get_buyer_notifications(user, limit=5):
    """ASSUMPTION: notifications/models.py has no Notification model
    defined yet (it's currently a placeholder app). Once one is added
    with a FK to the user, this will pick it up automatically via one
    of the related_names below; otherwise it returns an empty list and
    the template falls back to its own static preview."""
    for attr in ("notifications", "notification_set"):
        manager = getattr(user, attr, None)
        if manager is not None and hasattr(manager, "all"):
            qs = manager.order_by("-created_at")
            try:
                unread_count = qs.filter(is_read=False).count()
            except Exception:
                unread_count = 0
            return list(qs[:limit]), unread_count
    return [], 0


from allauth.mfa.models import Authenticator


def get_buyer_profile_context(user):
    """Orchestrator for the buyer profile / my account page. Gathers
    everything the template needs into a single context dict so the
    view itself can stay a thin wrapper."""

    notifications, notifications_unread_count = get_buyer_notifications(user)

    return {
        "addresses": get_user_addresses(user),
        "default_address": get_default_address(user),
        "recent_orders": get_buyer_recent_orders(user),
        "buyer_stats": get_buyer_dashboard_stats(user),
        "profile_completion": calculate_buyer_profile_completion(user),
        "wishlist_items": get_buyer_wishlist_preview(user),
        "activities": get_buyer_recent_activity(user),
        "notifications": notifications,
        "notifications_unread_count": notifications_unread_count,
        "two_factor_enabled": Authenticator.objects.filter(
            user=user,
            type=Authenticator.Type.TOTP,
        ).exists(),
    }

from django.db import transaction

from .models import UserPreferences


@transaction.atomic
def update_user_preferences(user, data):
    preferences_data = data.get("preferences", {})
    channels_data = data.get("channels", {})

    if not isinstance(preferences_data, dict):
        raise ValueError("Invalid preferences data.")

    if not isinstance(channels_data, dict):
        raise ValueError("Invalid notification channels data.")

    preferences, created = UserPreferences.objects.get_or_create(
        user=user
    )

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
