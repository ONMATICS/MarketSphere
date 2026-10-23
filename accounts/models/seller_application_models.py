from django.db import models
from django.conf import settings
from .seller_models import Seller


class SellerApplication(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        CHANGES_REQUESTED = "changes_requested", "Changes Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    seller = models.OneToOneField(
        Seller,
        on_delete=models.CASCADE,
        related_name="application",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    submitted_at = models.DateTimeField(null=True, blank=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_applications",
    )

    application_source = models.CharField(
        max_length=100,
        blank=True,
    )

    referral_code = models.CharField(
        max_length=100,
        blank=True,
    )

    admin_notes = models.TextField(blank=True)

    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)


class SellerApplicationDocument(models.Model):

    class DocumentType(models.TextChoices):
        CNIC_FRONT = "cnic_front", "CNIC Front"
        CNIC_BACK = "cnic_back", "CNIC Back"
        BUSINESS_CERTIFICATE = "business_certificate", "Business Registration Certificate"
        NTN = "ntn", "NTN Certificate"
        BANK_STATEMENT = "bank_statement", "Bank Statement"
        STORE_PHOTO = "store_photo", "Store Photo"

    application = models.ForeignKey(
        SellerApplication,
        related_name="documents",
        on_delete=models.CASCADE,
    )

    document_type = models.CharField(
        max_length=50,
        choices=DocumentType.choices,
    )

    # Cloudinary URL for images, PDFs, and other seller application files.
    file = models.URLField(blank=True, null=True, max_length=1000)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    verified = models.BooleanField(default=False)

    verification_note = models.TextField(blank=True)

    @property
    def is_image(self):
        """Keep document previews working for Cloudinary URL-backed files."""
        if not self.file:
            return False
        path = self.file.split("?", 1)[0].lower()
        return path.endswith((".jpg", ".jpeg", ".png", ".webp"))


class SellerApplicationFlag(models.Model):

    class Severity(models.TextChoices):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"

    application = models.ForeignKey(
        SellerApplication,
        related_name="flags",
        on_delete=models.CASCADE,
    )

    title = models.CharField(max_length=200)

    description = models.TextField()

    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
    )

    resolved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)