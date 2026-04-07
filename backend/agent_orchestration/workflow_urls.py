# backend/agent_orchestration/workflow_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .workflow_views import AgentWorkflowViewSet
from .docaware_views import DocAwareConfigViewSet
from .prompt_generation_views import PromptGenerationViewSet
from . import human_input_views

# Create router for workflow endpoints
router = DefaultRouter()
router.register(r'docaware', DocAwareConfigViewSet, basename='docaware')
router.register(r'generate-prompt', PromptGenerationViewSet, basename='generate-prompt')

# Note: We'll register this with a custom basename in the main URLs
# to handle the nested project/{id}/workflows/ structure

urlpatterns = [
    # The router URLs will be included by the main URL config
    path('', include(router.urls)),
    
    # ============================================================================
    # PHASE 2: HUMAN INPUT API ENDPOINTS
    # ============================================================================
    path('human-input/pending/', human_input_views.get_pending_human_inputs, name='pending_human_inputs'),
    path('human-input/submit/', human_input_views.submit_human_input, name='submit_human_input'), 
    path('human-input/history/', human_input_views.get_human_input_history, name='human_input_history'),
]
