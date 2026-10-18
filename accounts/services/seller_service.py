from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import DecimalField, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import (
    Address, Seller, SellerApplication, SellerApplicationDocument,
    SellerProfile, SellerSettings, User
)
from notifications.emails.sellers import (
    send_application_incomplete_email, send_application_received_email,
    send_seller_rejected_email, send_seller_verified_email
)
from orders.models import Order
from services.cloudinary_service import store_seller_asset


def reject_seller_application_service(
    application_id: int, reason: str, notes: str
) -> SellerApplication:
    """Reject a seller application and notify the seller."""
    application = SellerApplication.objects.get(pk=application_id)
    application.status = SellerApplication.Status.REJECTED
    application.rejection_reason = reason
    application.admin_notes = notes
    application.reviewed_at = timezone.now()

    application.save(update_fields=["status", "rejection_reason", "admin_notes", "reviewed_at"])
    transaction.on_commit(lambda: send_seller_rejected_email(application, reason))

    return application


@transaction.atomic
def request_application_changes_service(
    application_id: int, requested_changes: list[str], notes: str
) -> SellerApplication:
    """Push an application back to pending to request changes from the seller."""
    application = SellerApplication.objects.select_related("seller").get(pk=application_id)
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
    application.save(update_fields=["status", "admin_notes", "reviewed_at"])

    seller.status = Seller.Status.PENDING
    seller.save(update_fields=["status"])
    transaction.on_commit(lambda: send_seller_rejected_email(application, notes))

    return application


@transaction.atomic
def approve_seller_application_service(application_id: int) -> SellerApplication:
    """Fully approve a seller application and promote their account status."""
    application = SellerApplication.objects.select_related("seller", "seller__user").get(
        pk=application_id
    )
    seller = application.seller

    application.status = SellerApplication.Status.APPROVED
    application.reviewed_at = timezone.now()
    application.save(update_fields=["status", "reviewed_at"])

    seller.status = Seller.Status.VERIFIED
    seller.save(update_fields=["status"])
    transaction.on_commit(lambda seller=seller: send_seller_verified_email(seller), robust=True)

    return application


@transaction.atomic
def delete_seller_account_service(seller_id: int) -> None:
    """Permanently remove a seller's profile and dependencies."""
    seller = Seller.objects.get(pk=seller_id)
    seller.delete()


def flag_seller_document_service(
    *, document_id: int, issue: str, note: str
) -> SellerApplicationDocument:
    """Mark a seller document as invalid or problematic."""
    document = SellerApplicationDocument.objects.get(pk=document_id)
    document.verified = False
    message = issue

    if note:
        message += f"\n\n{note}"

    document.verification_note = message
    document.save(update_fields=["verified", "verification_note"])
    return document


def verify_seller_document_service(document_id: int, document_type: str) -> SellerApplicationDocument:
    """Mark a specific seller application document as verified."""
    document = get_object_or_404(
        SellerApplicationDocument, id=document_id, document_type=document_type
    )
    document.verified = True
    document.verification_note = ""
    document.save(update_fields=["verified", "verification_note"])
    return document


def request_missing_document_service(
    application_id: int, document_type: str, reason: str, note: str
) -> SellerApplicationDocument:
    """Create a placeholder for a missing document to prompt the seller to upload it."""
    seller = get_object_or_404(Seller, id=application_id)
    application = seller.application

    document, _ = SellerApplicationDocument.objects.get_or_create(
        application=application, document_type=document_type
    )
    document.verified = False
    document.verification_note = f"{reason}\n\n{note}"
    document.save(update_fields=["verified", "verification_note"])
    return document


def save_application_notes_service(application_id: int, notes: str) -> SellerApplication:
    """Save private administrator notes for an application review."""
    application = get_object_or_404(SellerApplication, pk=application_id)
    application.admin_notes = notes
    application.save(update_fields=["admin_notes"])
    return application


def calculate_application_progress(seller: Seller) -> dict[str, Any]:
    """Calculate the completion percentage and required missing fields of a seller application."""
    completed = 0
    total = 0
    missing = []

    profile = getattr(seller, "profile", None)
    address = seller.business_address
    application = getattr(seller, "application", None)

    documents = {}
    if application:
        documents = {document.document_type: document for document in application.documents.all()}

    def check(condition: Any, label: str) -> None:
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
    check(SellerApplicationDocument.DocumentType.CNIC_FRONT in documents, "CNIC Front")
    check(SellerApplicationDocument.DocumentType.CNIC_BACK in documents, "CNIC Back")
    check(SellerApplicationDocument.DocumentType.STORE_PHOTO in documents, "Store Photo")

    progress = round((completed / total) * 100) if total else 0

    return {
        "progress": progress,
        "completed": completed,
        "total": total,
        "missing": missing,
        "is_complete": progress == 100,
    }


def update_application_progress(seller: Seller) -> dict[str, Any]:
    """Re-evaluate application completeness and progress application statuses."""
    progress = calculate_application_progress(seller)
    application = seller.application

    if progress["is_complete"]:
        seller.status = Seller.Status.PENDING
        seller.save(update_fields=["status"])

        application.status = SellerApplication.Status.SUBMITTED
        application.save(update_fields=["status"])
        transaction.on_commit(lambda: send_application_received_email(application))
    else:
        seller.status = Seller.Status.DRAFT
        seller.save(update_fields=["status"])

        application.status = SellerApplication.Status.DRAFT
        application.save(update_fields=["status"])

    return progress


@transaction.atomic
def create_seller_application(
    user: User, data: dict[str, Any], files: dict[str, Any]
) -> Seller:
    """Initialize a brand-new seller application from a multi-part payload."""
    if hasattr(user, "contact"):
        user.contact = str(data.get("phone", "")).strip()
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

    base_slug = slugify(str(data.get("store_name")))
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
        business_registration_number=data.get("business_registration_number", ""),
        tax_id=data.get("tax_id", ""),
    )

    SellerProfile.objects.create(
        seller=seller,
        business_category=data.get("business_category", ""),
        business_type=data.get("business_type", ""),
        national_id_number=data.get("national_id_number", ""),
        years_in_business=data.get("years_in_business") or None,
        expected_monthly_volume=data.get("expected_monthly_volume", ""),
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


def get_all_sellers() -> QuerySet[Seller]:
    """Retrieve all sellers annotated with total sales figures for delivered orders."""
    return Seller.objects.annotate(
        total_sales=Coalesce(
            Sum("orders__total", filter=Q(orders__status=Order.Status.DELIVERED)),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )


def update_seller_information(user: User, data: dict[str, Any], files: dict[str, Any]) -> Seller:
    """Update core store information and branding assets."""
    seller = user.seller_profile

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

    store_email = data.get("store_email")
    if store_email is not None:
        seller.store_email = store_email

    store_description = data.get("store_description")
    if store_description is not None:
        seller.store_description = store_description

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


def update_store_information(seller: Seller, data: dict[str, Any]) -> Seller:
    """Update comprehensive store metadata including external links and addresses."""
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

    address, _ = Address.objects.get_or_create(user=seller.user, address_type=Address.BUSINESS)
    address.city = data.get("city", "")
    address.address_line_1 = data.get("address_line_1", "")
    address.postal_code = data.get("postal_code", "")
    address.save()

    update_application_progress(seller)
    return seller


def update_seller_status(seller: Seller, status: str) -> None:
    """Modify the operational status flag of a seller."""
    seller.status = status
    seller.save(update_fields=["status"])


def change_store_banner(seller_id: int, banner: Any) -> str | None:
    """Upload and swap out a seller's store banner directly."""
    seller = Seller.objects.filter(id=seller_id).first()
    if not seller:
        return None

    result = store_seller_asset(banner, str(seller.id), "store_banner", "image")
    seller.store_banner = result.get("secure_url") or result.get("url")
    seller.save(update_fields=["store_banner"])
    return seller.store_banner


def update_shipping_preferences(seller: Seller, data: dict[str, Any]) -> SellerSettings:
    """Configure shipping options and handling times for a store."""
    settings, _ = SellerSettings.objects.get_or_create(seller=seller)
    
    settings.default_courier = data.get("default_courier", "")
    settings.default_handling_time = int(data.get("handling_time", SellerSettings.HandlingTime.TWO_DAYS))
    settings.return_address = str(data.get("return_address", "")).strip()
    settings.shipping_notes = str(data.get("shipping_notes", "")).strip()
    settings.auto_mark_shipped = str(data.get("auto_mark_shipped")).lower() == "true"
    settings.shipping_fee = float(data.get("shipping_fee", 0.0))
    settings.save()

    return settings


def update_notification_preferences(seller: Seller, data: dict[str, Any]) -> SellerSettings:
    """Configure which store events trigger alerts to the seller."""
    settings, _ = SellerSettings.objects.get_or_create(seller=seller)

    settings.email_new_order = str(data.get("email_new_order")).lower() == "true"
    settings.email_cancelled_order = str(data.get("email_cancelled_order")).lower() == "true"
    settings.email_delivered_order = str(data.get("email_delivered_order")).lower() == "true"
    settings.email_low_stock = str(data.get("email_low_stock")).lower() == "true"
    settings.weekly_sales_summary = str(data.get("weekly_sales_summary")).lower() == "true"
    settings.monthly_store_report = str(data.get("monthly_store_report")).lower() == "true"
    settings.save()

    return settings


def deactivate_seller_account(seller: Seller) -> None:
    """Deactivate a seller's profile, pausing new orders and visibility."""
    seller.status = Seller.Status.DEACTIVATED
    seller.save(update_fields=["status"])


def reactivate_seller_account(seller: Seller) -> None:
    """Reactivate a previously deactivated seller account."""
    seller.status = Seller.Status.VERIFIED
    seller.save(update_fields=["status"])


def update_seller_profile_service(user: User, data: dict[str, Any]) -> tuple[bool, str]:
    """Patch specific business demographics and links for a seller profile."""
    try:
        seller = user.seller_profile
    except Exception:
        return False, "Seller account not found."

    profile, _ = SellerProfile.objects.get_or_create(seller=seller)

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


def update_seller_document_service(
    user: User, data: dict[str, Any], files: dict[str, Any]
) -> tuple[bool, str, SellerApplicationDocument | None]:
    """Upload or replace a single mandatory application document."""
    try:
        seller = user.seller_profile
    except Exception:
        return False, "Seller account not found.", None

    try:
        application = SellerApplication.objects.get(seller=seller)
    except SellerApplication.DoesNotExist:
        return False, "Seller application not found.", None

    document_type = data.get("document_type")
    uploaded_file = files.get("document")

    if not document_type:
        return False, "Document type is required.", None
    if not uploaded_file:
        return False, "Please select a document.", None

    valid_document_types = {choice[0] for choice in SellerApplicationDocument.DocumentType.choices}
    if document_type not in valid_document_types:
        return False, "Invalid document type.", None

    document, _ = SellerApplicationDocument.objects.get_or_create(
        application=application, document_type=document_type
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


def get_seller_application_documents(seller: Seller) -> dict[str, SellerApplicationDocument | None]:
    """Fetch all uploaded documents tied to a seller's active application."""
    try:
        application = seller.application
    except AttributeError:
        return {}

    uploaded_documents = {
        document.document_type: document for document in application.documents.all()
    }

    return {
        "cnic_front": uploaded_documents.get(SellerApplicationDocument.DocumentType.CNIC_FRONT),
        "cnic_back": uploaded_documents.get(SellerApplicationDocument.DocumentType.CNIC_BACK),
        "business_certificate": uploaded_documents.get(SellerApplicationDocument.DocumentType.BUSINESS_CERTIFICATE),
        "ntn": uploaded_documents.get(SellerApplicationDocument.DocumentType.NTN),
        "bank_statement": uploaded_documents.get(SellerApplicationDocument.DocumentType.BANK_STATEMENT),
        "store_photo": uploaded_documents.get(SellerApplicationDocument.DocumentType.STORE_PHOTO),
    }