# templates/template_definitions/aicc-intellidoc/__init__.py

"""
AICC-IntelliDoc Template - Complete Backend Independence

This package provides complete backend independence for the AICC-IntelliDoc template,
including template-specific views, serializers, URLs, and services.

Template Features:
- Hierarchical document processing with 35K chunk support
- Complete content preservation
- Multi-page navigation (4 pages)
- Advanced AI analysis and categorization
- Enhanced search capabilities
- Document reconstruction

Independence Level: Complete
Version: 2.0.0
"""

from .definition import AICCIntelliDocTemplate
from .serializers import (
    AICCIntelliDocTemplateDiscoverySerializer,
    AICCIntelliDocTemplateConfigurationSerializer,
    AICCIntelliDocTemplateDuplicationSerializer,
    AICCIntelliDocTemplateStatusSerializer,
    AICCIntelliDocDuplicationResultSerializer
)

__all__ = [
    # Template definition
    'AICCIntelliDocTemplate',
    
    # Serializers
    'AICCIntelliDocTemplateDiscoverySerializer',
    'AICCIntelliDocTemplateConfigurationSerializer',
    'AICCIntelliDocTemplateDuplicationSerializer',
    'AICCIntelliDocTemplateStatusSerializer',
    'AICCIntelliDocDuplicationResultSerializer',
]

# Template metadata
TEMPLATE_INFO = {
    'template_id': 'aicc-intellidoc',
    'template_name': 'AICC-IntelliDoc',
    'version': '2.0.0',
    'description': 'Advanced AI-powered document analysis with hierarchical processing',
    'independence_level': 'complete',
    'backend_components': {
        'serializers': 'Template-specific serializers for discovery and configuration',
        'urls': 'Template-specific URL patterns',
        'definition': 'Template configuration class'
    },
    'capabilities': [
        'hierarchical_processing',
        'enhanced_search',
        'content_reconstruction',
        'navigation',
        'ai_analysis',
        'categorization'
    ]
}
