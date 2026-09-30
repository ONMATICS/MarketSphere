
from django.core.exceptions import ValidationError
from django.db import transaction

from orders.models import Order

from .models.support import SupportMessage, SupportRequest


@transaction.atomic
def create_support_request(
    *,
    user,
    request_type,
    category,
    subject,
    message,
    related_order=None,
    related_product_name="",
    attachment=None,
    preferred_contact_method=SupportRequest.ContactMethod.EMAIL,
):

    valid_request_types = dict(
        SupportRequest.RequestType.choices
    )

    valid_categories = dict(
        SupportRequest.Category.choices
    )

    valid_contact_methods = dict(
        SupportRequest.ContactMethod.choices
    )

    if request_type not in valid_request_types:
        raise ValidationError(
            "Invalid support request type."
        )

    if category not in valid_categories:
        raise ValidationError(
            "Invalid support request category."
        )

    if preferred_contact_method not in valid_contact_methods:
        raise ValidationError(
            "Invalid contact method."
        )

    if not subject.strip():
        raise ValidationError(
            "Subject is required."
        )

    if not message.strip():
        raise ValidationError(
            "Message is required."
        )

    if len(message.strip()) > SupportRequest._meta.get_field("message").max_length:
        raise ValidationError(
            f"Message cannot exceed {SupportRequest._meta.get_field('message').max_length} characters."
        )

    if related_order:

        if not Order.objects.filter(
            pk=related_order.pk,
            user=user,
        ).exists():

            raise ValidationError(
                "The selected order does not belong "
                "to your account."
            )

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

from django.core.exceptions import ObjectDoesNotExist
from orders.models import OrderItem  # Adjust imports based on your app names
from support.models.product_reviews import Review

def process_product_review(user, order_item_id, rating, title, description, image=None):
    """
    Handles the creation of a product review, ensuring the user owns the order item.
    """
    try:
        # 1. Basic validation
        if not all([order_item_id, rating, title, description]):
            return False, "All required fields must be provided."

        # 2. Fetch the OrderItem and verify it belongs to the requesting user
        # This prevents users from reviewing items they haven't bought
        order_item = OrderItem.objects.select_related('order', 'product').get(
            id=order_item_id,
            order__user=user 
        )

        # 3. Check if a review already exists for this exact order item
        if hasattr(order_item, 'review'):
            return False, "You have already reviewed this product from this order."

        # 4. Create the review
        Review.objects.create(
            user=user,
            product=order_item.product,
            order_item=order_item,
            rating=int(rating),
            title=title.strip(),
            description=description.strip(),
            image=image
        )

        return True, "Review submitted successfully."

    except ObjectDoesNotExist:
        return False, "Order item not found or you are not authorized to review this item."
    except ValueError:
        return False, "Invalid rating format."
    except Exception as e:
        return False, f"An error occurred: {str(e)}"


def get_user_support_requests(user):
    return (
        SupportRequest.objects
        .filter(user=user)
        .select_related("related_order")
        .prefetch_related("messages")
        .order_by("-updated_at")
    )


def get_user_support_request(*, user, request_id):
    return (
        SupportRequest.objects
        .filter(
            pk=request_id,
            user=user,
        )
        .select_related("related_order")
        .prefetch_related(
            "messages__sender"
        )
        .first()
    )


@transaction.atomic
def add_support_message(
    *,
    support_request,
    sender,
    sender_type,
    message,
    attachment=None,
):
    if not message.strip():
        raise ValidationError("Message cannot be empty.")

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

    support_request.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return support_message

from django.core.paginator import Paginator

def get_product_reviews(product, page_number=1, per_page=5):
    """
    Fetches reviews for a given product, ordered by newest first, and paginates them.
    Uses select_related to optimize the database query for the user model.
    """
    # Assuming related_name="reviews" is set on the Product model's ForeignKey
    reviews_qs = product.reviews.select_related('user').all()
    
    paginator = Paginator(reviews_qs, per_page)
    return paginator.get_page(page_number)

from django.db.models import Count

def get_review_distribution(product):
    """Calculates the percentage and count of reviews for each star rating (5 down to 1)."""
    counts = product.reviews.values('rating').annotate(count=Count('id'))
    total = product.reviews.count()

    # Initialize dictionary for 5 to 1 stars in descending order
    distribution = {i: {'count': 0, 'percent': 0} for i in range(5, 0, -1)}

    for c in counts:
        rating = c['rating']
        count = c['count']
        percent = (count / total * 100) if total > 0 else 0
        if rating in distribution:
            distribution[rating] = {'count': count, 'percent': round(percent)}

    return distribution