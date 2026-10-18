from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from support import services as support_services


@require_POST
def mark_review_helpful_api(request: HttpRequest, review_id: int) -> JsonResponse:
    """Record a helpful 'like' onto a specific product review."""
    if not request.user.is_authenticated:
        return JsonResponse({
            'status': 'error', 
            'message': 'Please log in to mark reviews as helpful.'
        }, status=401)
        
    session_key = f'has_liked_review_{review_id}'
    
    if request.session.get(session_key):
        return JsonResponse({
            'status': 'error', 
            'message': 'You have already marked this review as helpful.'
        }, status=400)
        
    success, result = support_services.mark_review_helpful(request.user, review_id)
    
    if success:
        request.session[session_key] = True 
        return JsonResponse({'status': 'success', 'new_count': result})
        
    return JsonResponse({'status': 'error', 'message': result}, status=400)