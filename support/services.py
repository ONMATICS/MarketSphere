from typing import Any, Optional, Tuple
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Page, Paginator
from django.db import transaction
from django.db.models import Count, QuerySet

from orders.models import Order, OrderItem
from services import cloudinary_service

from support.models.review_models import Review
from support.models.support_models import SupportMessage, SupportRequest


# ------------------------------
# Support Request Services
# ------------------------------

@transaction.atomic
def create_support_request(
    *,
    user: Any,
    request_type: str,
    category: str,
    subject: str,
    message: str,
    related_order: Optional[Order] = None,
    related_product_name: str = "",
    attachment: Any = None,
    preferred_contact_method: str = SupportRequest.ContactMethod.EMAIL,
) -> SupportRequest:
    """Create a new support request and initialize its first customer message thread."""
    valid_request_types = dict(SupportRequest.RequestType.choices)
    valid_categories = dict(SupportRequest.Category.choices)
    valid_contact_methods = dict(SupportRequest.ContactMethod.choices)

    if request_type not in valid_request_types:
        raise ValidationError("Invalid support request type.")

    if category not in valid_categories:
        raise ValidationError("Invalid support request category.")

    if preferred_contact_method not in valid_contact_methods:
        raise ValidationError("Invalid contact method.")

    if not subject.strip():
        raise ValidationError("Subject is required.")

    if not message.strip():
        raise ValidationError("Message is required[cite: 5].")

    max_len = SupportRequest._meta.get_field("message").max_length
    if len(message.strip()) > max_len:
        raise ValidationError(f"Message cannot exceed {max_len} characters[cite: 5].")

    if related_order and not Order.objects.filter(pk=related_order.pk, user=user).exists():
        raise ValidationError("The selected order does not belong to your account[cite: 5].")

    support_request = SupportRequest.objects.create(
        user=user,
        request_type=request_type,
        category=category,
        subject=subject.strip(),
        message=message.strip(),
        related_order=related_order,
        related_product_name=related_product_name.strip(),
        attachment=attachment,
        preferred_contact_method=preferred_contact_method,
        status=SupportRequest.Status.OPEN,
    )

    SupportMessage.objects.create(
        request=support_request,
        sender=user,
        sender_type=SupportMessage.SenderType.CUSTOMER,
        message=message.strip(),
        attachment=attachment,
    )

    return support_request


def get_user_support_requests(user: Any) -> QuerySet[SupportRequest]:
    """Retrieve all support requests tied to a specific user account[cite: 5]."""
    return (
        SupportRequest.objects.filter(user=user)
        .select_related("related_order")
        .prefetch_related("messages")
        .order_by("-updated_at")
    )


def get_user_support_request(*, user: Any, request_id: int | str) -> Optional[SupportRequest]:
    """Retrieve a single support request with populated message sender profiles[cite: 5]."""
    return (
        SupportRequest.objects.filter(pk=request_id, user=user)
        .select_related("related_order")
        .prefetch_related("messages__sender")
        .first()
    )


@transaction.atomic
def add_support_message(
    *,
    support_request: SupportRequest,
    sender: Any,
    sender_type: str,
    message: str,
    attachment: Any = None,
) -> SupportMessage:
    """Append a response message to an existing support ticket thread[cite: 5]."""
    if not message.strip():
        raise ValidationError("Message cannot be empty[cite: 5].")

    support_message = SupportMessage.objects.create(
        request=support_request,
        sender=sender,
        sender_type=sender_type,
        message=message.strip(),
        attachment=attachment,
    )

    if sender_type == SupportMessage.SenderType.CUSTOMER:
        support_request.status = SupportRequest.Status.IN_PROGRESS
    else:
        support_request.status = SupportRequest.Status.WAITING_FOR_USER

    support_request.save(update_fields=["status", "updated_at"])
    return support_message


# ------------------------------
# Product Review & Rating Services
# ------------------------------

def process_product_review(
    user: Any,
    order_item_id: int | str,
    rating: int | str,
    title: str,
    description: str,
    image: Any = None,
) -> Tuple[bool, str]:
    """Handle product review creation, verifying item ownership and uploading attachments[cite: 5]."""
    try:
        if not all([order_item_id, rating, title, description]):
            return False, "All required fields must be provided[cite: 5]."

        order_item = OrderItem.objects.select_related("order", "product").get(
            id=order_item_id, order__user=user
        )

        if hasattr(order_item, "review"):
            return False, "You have already reviewed this product from this order[cite: 5]."

        image_url = None
        if image:
            upload_result = cloudinary_service.store_review_image(image, str(order_item.product.id))
            image_url = upload_result.get("secure_url") or upload_result.get("url")

        Review.objects.create(
            user=user,
            product=order_item.product,
            order_item=order_item,
            rating=int(rating),
            title=title.strip(),
            description=description.strip(),
            image=image_url,
        )

        return True, "Review submitted successfully[cite: 5]."

    except ObjectDoesNotExist:
        return False, "Order item not found or you are not authorized to review this item[cite: 5]."
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"An error occurred: {str(e)}[cite: 5]"


def get_product_reviews(product: Any, page_number: int = 1, per_page: int = 5) -> Page:
    """Fetch paginated reviews for a given product ordered by newest first[cite: 5]."""
    reviews_qs = product.reviews.select_related("user").all()
    paginator = Paginator(reviews_qs, per_page)
    return paginator.get_page(page_number)


def get_review_distribution(product: Any) -> dict[int, dict[str, int]]:
    """Calculate percentage and count distributions for star ratings (5 down to 1)[cite: 5]."""
    counts = product.reviews.values("rating").annotate(count=Count("id"))
    total = product.reviews.count()

    distribution = {i: {"count": 0, "percent": 0} for i in range(5, 0, -1)}

    for c in counts:
        rating = c["rating"]
        count = c["count"]
        percent = (count / total * 100) if total > 0 else 0
        if rating in distribution:
            distribution[rating] = {"count": count, "percent": round(percent)}

    return distribution


def mark_review_helpful(user: Any, review_id: int | str) -> Tuple[bool, int | str]:
    """Increment a review's helpful count if the requesting user is not the author[cite: 5]."""
    try:
        review = Review.objects.get(id=review_id)

        if review.user == user:
            return False, "You cannot mark your own review as helpful[cite: 5]."

        review.helpful_count += 1
        review.save(update_fields=["helpful_count"])

        return True, review.helpful_count

    except Review.DoesNotExist:
        return False, "Review not found[cite: 5]."