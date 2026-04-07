# templates/template_definitions/aicc-intellidoc/urls.py

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

# Template-specific logger
logger = logging.getLogger('templates.aicc-intellidoc')

# Template metadata for URL routing
TEMPLATE_METADATA = {
    'template_id': 'aicc-intellidoc',
    'template_name': 'AICC-IntelliDoc',
    'version': '2.0.0',
    'description': 'Advanced AI-powered document analysis with hierarchical processing',
    'independence_level': 'complete',
    'api_base': '/api/templates/aicc-intellidoc'
}

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def discover_template(request):
    """Discover AICC-IntelliDoc template capabilities"""
    logger.info(f"Processing template discovery for {TEMPLATE_METADATA['template_id']}")
    
    try:
        # Get template metadata
        from .definition import AICCIntelliDocTemplate
        template_instance = AICCIntelliDocTemplate()
        
        logger.info(f"Loading template configuration for {TEMPLATE_METADATA['template_id']}")
        
        discovery_data = {
            'template_id': TEMPLATE_METADATA['template_id'],
            'template_name': TEMPLATE_METADATA['template_name'],
            'version': TEMPLATE_METADATA['version'],
            'description': template_instance.description,
            'capabilities': {
                'hierarchical_processing': True,
                'advanced_navigation': True,
                'ai_analysis': True,
                'multi_document_support': True,
                'category_classification': True
            },
            'configuration': {
                'total_pages': template_instance.total_pages,
                'navigation_pages': template_instance.navigation_pages,
                'processing_modes': ['hierarchical', 'standard'],
                'supported_formats': ['pdf', 'docx', 'txt', 'md']
            },
            'endpoints': {
                'discover': '/api/templates/aicc-intellidoc/discover/',
                'configuration': '/api/templates/aicc-intellidoc/configuration/',
                'status': '/api/templates/aicc-intellidoc/status/'
            },
            'independence_level': 'complete'
        }
        
        logger.info(f"Template discovery completed for {TEMPLATE_METADATA['template_id']}")
        
        return Response({
            'status': 'success',
            'discovery': discovery_data
        })
        
    except Exception as e:
        logger.error(f"Error in template discovery for {TEMPLATE_METADATA['template_id']}: {str(e)}")
        return Response(
            {'error': 'Template discovery failed', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_configuration(request):
    """Get AICC-IntelliDoc template configuration"""
    logger.info(f"Getting configuration for {TEMPLATE_METADATA['template_id']}")
    
    try:
        from .definition import AICCIntelliDocTemplate
        template_instance = AICCIntelliDocTemplate()
        
        configuration_data = {
            'template_id': TEMPLATE_METADATA['template_id'],
            'template_name': TEMPLATE_METADATA['template_name'],
            'version': TEMPLATE_METADATA['version'],
            'total_pages': template_instance.total_pages,
            'navigation_pages': template_instance.navigation_pages,
            'instructions': template_instance.instructions,
            'analysis_focus': template_instance.analysis_focus,
            'suggested_questions': template_instance.suggested_questions,
            'icon_class': template_instance.icon_class,
            'color_theme': template_instance.color_theme,
            'processing_capabilities': template_instance.processing_capabilities
        }
        
        logger.info(f"Configuration retrieved for {TEMPLATE_METADATA['template_id']}")
        
        return Response({
            'status': 'success',
            'configuration': configuration_data
        })
        
    except Exception as e:
        logger.error(f"Error getting configuration for {TEMPLATE_METADATA['template_id']}: {str(e)}")
        return Response(
            {'error': 'Configuration retrieval failed', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_workflow(request):
    """Validate agent workflow for AICC-IntelliDoc-v2 template"""
    logger.info(f"Validating workflow using template {TEMPLATE_METADATA['template_id']}")
    
    try:
        workflow_data = request.data
        project_id = workflow_data.get('project_id')
        
        if not project_id:
            return Response(
                {'error': 'project_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from .services import AICCIntelliDocWorkflowValidationService
        validation_service = AICCIntelliDocWorkflowValidationService()
        
        validation_result = validation_service.validate_agent_workflow(project_id, workflow_data)
        
        logger.info(f"Workflow validation completed for project {project_id}")
        
        return Response({
            'status': 'success',
            'validation': validation_result
        })
        
    except Exception as e:
        logger.error(f"Error validating workflow using template {TEMPLATE_METADATA['template_id']}: {str(e)}")
        return Response(
            {'error': 'Workflow validation failed', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def workflow_recommendations(request):
    """Get workflow optimization recommendations for AICC-IntelliDoc-v2 template"""
    logger.info(f"Generating workflow recommendations using template {TEMPLATE_METADATA['template_id']}")
    
    try:
        workflow_data = request.data
        project_id = workflow_data.get('project_id')
        
        if not project_id:
            return Response(
                {'error': 'project_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from .services import AICCIntelliDocWorkflowValidationService
        validation_service = AICCIntelliDocWorkflowValidationService()
        
        recommendations_result = validation_service.get_workflow_recommendations(project_id, workflow_data)
        
        logger.info(f"Workflow recommendations generated for project {project_id}")
        
        return Response({
            'status': 'success',
            'recommendations': recommendations_result
        })
        
    except Exception as e:
        logger.error(f"Error generating workflow recommendations using template {TEMPLATE_METADATA['template_id']}: {str(e)}")
        return Response(
            {'error': 'Workflow recommendations failed', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_status(request):
    """Get AICC-IntelliDoc template status"""
    logger.info(f"Getting status for {TEMPLATE_METADATA['template_id']}")
    
    try:
        status_data = {
            'template_id': TEMPLATE_METADATA['template_id'],
            'template_name': TEMPLATE_METADATA['template_name'],
            'version': TEMPLATE_METADATA['version'],
            'status': 'active',
            'health': 'healthy',
            'independence_level': 'complete',
            'last_updated': '2025-07-21',
            'capabilities_available': True
        }
        
        logger.info(f"Status retrieved for {TEMPLATE_METADATA['template_id']}")
        
        return Response({
            'status': 'success',
            'template_status': status_data
        })
        
    except Exception as e:
        logger.error(f"Error getting status for {TEMPLATE_METADATA['template_id']}: {str(e)}")
        return Response(
            {'error': 'Status retrieval failed', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Log template URL registration
logger.info(f"Registering URL patterns for template: {TEMPLATE_METADATA['template_id']}")
logger.info(f"Template API base: {TEMPLATE_METADATA['api_base']}")

# AICC-IntelliDoc Template Management URLs
# These endpoints are for TEMPLATE MANAGEMENT operations (discovery, duplication, configuration)
# NOT for project operations (projects use universal endpoints)
urlpatterns = [
    # Template Discovery and Information
    path('discover/', discover_template, name='aicc-intellidoc-discover'),
    
    # Template Configuration Management
    path('configuration/', get_configuration, name='aicc-intellidoc-configuration'),
    
    # Template Status and Health
    path('status/', get_status, name='aicc-intellidoc-status'),
    
    # Workflow Validation Endpoints
    path('validate-workflow/', validate_workflow, name='aicc-intellidoc-validate-workflow'),
    path('workflow-recommendations/', workflow_recommendations, name='aicc-intellidoc-workflow-recommendations'),
]

logger.info(f"Registered {len(urlpatterns)} URL patterns for template {TEMPLATE_METADATA['template_id']}")

# Export template metadata for dynamic routing
__template_metadata__ = TEMPLATE_METADATA
