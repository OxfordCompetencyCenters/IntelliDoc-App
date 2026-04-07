# templates/urls.py - Enhanced with Phase 3 capabilities
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectTemplateViewSet, IntelliDocProjectViewSet
from .enhanced_views import EnhancedTemplateViewSet
from .dynamic_urls import get_template_route_patterns, include_template_urls

# Create router for API endpoints
router = DefaultRouter()
router.register(r'project-templates', ProjectTemplateViewSet, basename='project-template')
router.register(r'intellidoc-projects', IntelliDocProjectViewSet, basename='intellidoc-project')
router.register(r'enhanced-project-templates', EnhancedTemplateViewSet, basename='enhanced-template')

# URL patterns for folder-based templates
urlpatterns = [
    # Include router URLs
    path('api/', include(router.urls)),
    
    # Legacy template endpoints for backward compatibility
    path('api/project-templates/', ProjectTemplateViewSet.as_view({'get': 'list'}), name='template-list'),
    path('api/project-templates/discover/', ProjectTemplateViewSet.as_view({'get': 'discover'}), name='template-discover'),
    path('api/project-templates/duplicate/', ProjectTemplateViewSet.as_view({'post': 'duplicate'}), name='template-duplicate'),
    path('api/project-templates/cache-stats/', ProjectTemplateViewSet.as_view({'get': 'cache_stats'}), name='template-cache-stats'),
    path('api/project-templates/cache-management/', ProjectTemplateViewSet.as_view({'post': 'cache_management'}), name='template-cache-management'),
    path('api/project-templates/<str:pk>/', ProjectTemplateViewSet.as_view({'get': 'retrieve'}), name='template-detail'),
    path('api/project-templates/<str:pk>/configuration/', ProjectTemplateViewSet.as_view({'get': 'configuration'}), name='template-configuration'),
    
    # Enhanced template endpoints (Phase 3)
    path('api/enhanced-project-templates/enhanced_discover/', EnhancedTemplateViewSet.as_view({'get': 'enhanced_discover'}), name='enhanced-template-discover'),
    path('api/enhanced-project-templates/architectural_status/', EnhancedTemplateViewSet.as_view({'get': 'architectural_status'}), name='template-architectural-status'),
    path('api/enhanced-project-templates/template_comparison/', EnhancedTemplateViewSet.as_view({'get': 'template_comparison'}), name='template-comparison'),
    path('api/enhanced-project-templates/refresh_discovery_cache/', EnhancedTemplateViewSet.as_view({'post': 'refresh_discovery_cache'}), name='refresh-discovery-cache'),
    path('api/enhanced-project-templates/<str:pk>/routing_info/', EnhancedTemplateViewSet.as_view({'get': 'routing_info'}), name='template-routing-info'),
    path('api/enhanced-project-templates/<str:pk>/register_routes/', EnhancedTemplateViewSet.as_view({'post': 'register_routes'}), name='register-template-routes'),
    path('api/enhanced-project-templates/<str:pk>/validate_registration/', EnhancedTemplateViewSet.as_view({'get': 'validate_registration'}), name='validate-template-registration'),
    
    # IntelliDoc project endpoints
    path('api/intellidoc-projects/', IntelliDocProjectViewSet.as_view({'get': 'list', 'post': 'create'}), name='intellidoc-projects'),
    path('api/intellidoc-projects/<str:pk>/', IntelliDocProjectViewSet.as_view({'get': 'retrieve'}), name='intellidoc-project-detail'),
]

# Add dynamic template-specific routes
try:
    # Get dynamic template route patterns
    dynamic_patterns = get_template_route_patterns()
    urlpatterns.extend(dynamic_patterns)
except Exception as e:
    # Log error but don't break URL configuration
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not load dynamic template routes: {str(e)}")
