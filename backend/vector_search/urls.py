# backend/vector_search/urls.py
from django.urls import path
from . import api_views
from . import consolidated_api_views

urlpatterns = [
    # CONSOLIDATED PROCESSING ENDPOINTS (Phase 2 - Primary)
    path('projects/<str:project_id>/processing/start/', consolidated_api_views.start_processing_consolidated, name='start_processing_consolidated'),
    path('projects/<str:project_id>/processing/stop/', consolidated_api_views.stop_processing_consolidated, name='stop_processing_consolidated'),
    path('projects/<str:project_id>/processing/status/', consolidated_api_views.get_vector_status_consolidated, name='get_processing_status_consolidated'),
    
    # LEGACY PROCESSING ENDPOINTS (Phase 1 - For backward compatibility)
    path('projects/<str:project_id>/processing/start-legacy/', api_views.start_processing, name='start_processing_legacy'),
    path('projects/<str:project_id>/processing/stop-legacy/', api_views.stop_processing, name='stop_processing_legacy'),
    path('projects/<str:project_id>/processing/status-legacy/', api_views.get_processing_status, name='get_processing_status_legacy'),
    path('projects/<str:project_id>/documents/statuses/', api_views.get_document_statuses, name='get_document_statuses'),
    path('health/', api_views.health_check, name='health_check'),
    
    # MAINTENANCE ENDPOINTS
    path('projects/<str:project_id>/fix-documents/', api_views.fix_documents_api, name='fix_documents_project'),
    path('fix-documents/', api_views.fix_documents_api, name='fix_documents_all'),
    path('processing-modes/', api_views.get_processing_modes, name='get_processing_modes'),
]
