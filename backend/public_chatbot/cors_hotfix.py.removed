"""
IMMEDIATE CORS HOTFIX for Public Chatbot API
Apply this fix if CORS headers are not working properly
"""

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from functools import wraps
import logging

logger = logging.getLogger('public_chatbot')

def force_cors_headers(view_func):
    """
    Decorator to force CORS headers on all responses
    Use this as an immediate fix if middleware isn't working
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get origin
        origin = request.META.get('HTTP_ORIGIN')
        
        # Allowed origins
        allowed_origins = [
            'https://oxfordcompetencycenters.github.io',
            'https://aicc.uksouth.cloudapp.azure.com',
            'http://localhost:3000',
            'http://localhost:5173',
            'http://localhost:8080',
            'http://127.0.0.1:3000',
            'http://127.0.0.1:5173',
            'http://127.0.0.1:8080',
        ]
        
        # Handle preflight OPTIONS request immediately
        if request.method == 'OPTIONS':
            logger.info(f"🔥 CORS HOTFIX: Handling preflight from {origin}")
            response = JsonResponse({'status': 'ok'})
        else:
            # Call the actual view
            response = view_func(request, *args, **kwargs)
        
        # Force add CORS headers
        if origin in allowed_origins:
            response['Access-Control-Allow-Origin'] = origin
            response['Vary'] = 'Origin'
            logger.info(f"🔥 CORS HOTFIX: Applied specific origin {origin}")
        else:
            response['Access-Control-Allow-Origin'] = '*'
            logger.info(f"🔥 CORS HOTFIX: Applied wildcard origin for {origin}")
        
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
        response['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept, Authorization, X-Requested-With, X-CSRFToken, Cache-Control'
        response['Access-Control-Allow-Credentials'] = 'false'  # Must be false for wildcard origin
        response['Access-Control-Max-Age'] = '86400'
        
        # Special handling for streaming
        if hasattr(response, 'streaming') and response.streaming:
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
        
        logger.info(f"🔥 CORS HOTFIX: Headers applied to {request.method} {request.path}")
        return response
    
    return wrapper


# Alternative: Direct response creator with CORS
def create_cors_response(data=None, status=200):
    """Create a JsonResponse with CORS headers pre-applied"""
    response = JsonResponse(data or {'status': 'ok'}, status=status)
    
    # Apply CORS headers
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
    response['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept, Authorization, X-Requested-With, X-CSRFToken, Cache-Control'
    response['Access-Control-Allow-Credentials'] = 'false'
    response['Access-Control-Max-Age'] = '86400'
    
    return response


# Test endpoint with forced CORS
@csrf_exempt
@force_cors_headers
def cors_test_endpoint(request):
    """Test endpoint to verify CORS is working"""
    return JsonResponse({
        'status': 'success',
        'message': 'CORS test successful!',
        'origin': request.META.get('HTTP_ORIGIN', 'none'),
        'method': request.method,
        'timestamp': '2025-01-01T00:00:00Z'
    })
