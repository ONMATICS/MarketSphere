import json
import logging

import cloudinary.exceptions

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from accounts import services
from services.cloudinary_service import store_profile_image

logger = logging.getLogger(__name__)


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Display the buyer 'My Profile' page."""
    context = services.get_buyer_profile_context(request.user)
    return render(request, "buyer_profile.html", context)


@login_required
@require_POST
def update_my_profile_view(request: HttpRequest) -> JsonResponse:
    """Update buyer profile information and avatar via AJAX or multipart submission."""
    buyer = request.user

    if (request.content_type or "").startswith("multipart/"):
        data = request.POST
    else:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    image_url = None
    profile_image = request.FILES.get("profile_image")
    if profile_image:
        try:
            upload_result = store_profile_image(profile_image, user_id=str(buyer.id))
            image_url = upload_result.get("secure_url") or upload_result.get("url")
            if not image_url:
                return JsonResponse({"success": False, "message": "Cloudinary did not return an image URL."}, status=502)
        except ValueError as error:
            return JsonResponse({"success": False, "message": str(error)}, status=400)
        except cloudinary.exceptions.NotAllowed:
            logger.exception("Cloudinary rejected profile image upload permissions.")
            return JsonResponse(
                {"success": False, "message": "Cloudinary upload permission is missing. Please contact support."}, 
                status=502
            )
        except Exception:
            logger.exception("Profile image upload failed for user_id: %s", buyer.id)
            return JsonResponse({"success": False, "message": "Unable to upload your profile image right now."}, status=502)

    success, message, buyer, email_changed, errors = services.update_buyer_profile(
        user=buyer,
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        username=data.get("username"),
        email=data.get("email"),
        contact=data.get("phone"),
        profile_image=image_url,
        allow_status_change=False,
        request=request,
    )

    if not success:
        return JsonResponse({"success": False, "message": message, "errors": errors}, status=400)

    return JsonResponse({
        "success": True,
        "message": message,
        "email_changed": email_changed,
        "user": {
            "id": buyer.id,
            "first_name": buyer.first_name,
            "last_name": buyer.last_name,
            "username": buyer.username,
            "email": buyer.email,
            "contact": buyer.contact,
            "profile_image_url": buyer.profile_image_url,
        },
    })


@login_required
def save_user_address(request: HttpRequest) -> JsonResponse:
    """Create a new address for the buyer."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
        address = services.save_user_address(request.user, data)
        return JsonResponse({
            "success": True,
            "message": "Address added successfully.",
            "address": {
                "id": address.id,
                "address_type": address.address_type,
                "address_type_display": address.get_address_type_display(),
                "full_name": address.full_name,
                "phone": address.phone,
                "address_line_1": address.address_line_1,
                "address_line_2": address.address_line_2,
                "city": address.city,
                "postal_code": address.postal_code,
                "is_default": address.is_default,
            },
        })
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)
    except ValueError as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)
    except Exception:
        logger.exception("Failed to save user address for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Something went wrong. Please try again."}, status=500)


@login_required
def update_user_address(request: HttpRequest) -> JsonResponse:
    """Update an existing buyer address."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
        address = services.save_user_address(request.user, data)
        return JsonResponse({
            "success": True,
            "message": "Address updated successfully.",
            "address": {
                "id": address.id,
                "address_type": address.address_type,
                "address_type_display": address.get_address_type_display(),
                "full_name": address.full_name,
                "phone": address.phone,
                "address_line_1": address.address_line_1,
                "address_line_2": address.address_line_2,
                "city": address.city,
                "postal_code": address.postal_code,
                "is_default": address.is_default,
            },
        })
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)
    except ValueError as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)
    except Exception:
        logger.exception("Failed to update user address for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Something went wrong. Please try again."}, status=500)


@login_required
def delete_user_address_view(request: HttpRequest) -> JsonResponse:
    """Delete an existing buyer address."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
        services.delete_user_address(request.user, data)
        return JsonResponse({"success": True, "message": "Address deleted successfully."})
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)
    except ValueError as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)
    except Exception:
        logger.exception("Failed to delete user address for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Something went wrong. Please try again."}, status=500)


@login_required
@require_POST
def update_user_preferences(request: HttpRequest) -> JsonResponse:
    """Update global notifications and preferences for a user."""
    try:
        data = json.loads(request.body or "{}")
        preferences = services.update_user_preferences(user=request.user, data=data)
        
        return JsonResponse({
            "success": True,
            "message": "Preferences saved successfully.",
            "preferences": {
                "order_updates": preferences.order_updates,
                "promotional_emails": preferences.promotional_emails,
                "price_drop_alerts": preferences.price_drop_alerts,
                "wishlist_alerts": preferences.wishlist_alerts,
                "review_reminders": preferences.review_reminders,
                "newsletter": preferences.newsletter,
                "email_notifications": preferences.email_notifications,
                "in_app_notifications": preferences.in_app_notifications,
                "push_notifications": preferences.push_notifications,
            },
        })
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)
    except ValueError as error:
        return JsonResponse({"success": False, "message": str(error)}, status=400)
    except Exception:
        logger.exception("Failed to update user preferences for user_id: %s", request.user.id)
        return JsonResponse({"success": False, "message": "Something went wrong. Please try again."}, status=500)