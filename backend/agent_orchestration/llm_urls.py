"""
LLM Configuration URL Routing - Phase 3 Workflow Integration

URL patterns for multi-provider LLM configuration API endpoints.
Supports OpenAI, Anthropic Claude, and Google Gemini providers.
"""

from django.urls import path, include
from . import llm_views

app_name = 'agent_llm'

urlpatterns = [
    # LLM Providers and Models
    path('providers/', llm_views.get_llm_providers, name='get_providers'),
    path('models/', llm_views.get_llm_models, name='get_models'),
    
    # Agent-specific LLM Configuration
    path('projects/<str:project_id>/agents/<str:agent_id>/config/', 
         llm_views.get_agent_llm_config, name='get_agent_config'),
    path('projects/<str:project_id>/agents/<str:agent_id>/config/update/', 
         llm_views.update_agent_llm_config, name='update_agent_config'),
    
    # Configuration Validation and Utilities
    path('validate/', llm_views.validate_llm_config, name='validate_config'),
    path('defaults/<str:agent_type>/', llm_views.get_default_agent_config, name='get_default_config'),
    path('cost-estimate/', llm_views.calculate_cost_estimate, name='calculate_cost'),
    
    # Bulk Loading and Caching for Agent Orchestration
    path('bulk-load/', llm_views.bulk_load_all_models, name='bulk_load_models'),
    path('refresh/<str:provider_id>/', llm_views.refresh_provider_models, name='refresh_provider'),
    path('clear-cache/', llm_views.clear_model_cache, name='clear_cache'),
]
