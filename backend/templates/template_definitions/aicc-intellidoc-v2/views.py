# templates/template_definitions/aicc-intellidoc/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
import logging
import uuid

# Template-specific logger
logger = logging.getLogger('templates.aicc-intellidoc')

class AICCIntelliDocViewSet(viewsets.ViewSet):
    """Template-specific API endpoints for AICC-IntelliDoc template management"""
    
    permission_classes = [IsAuthenticated]
    template_id = 'aicc-intellidoc'
    template_name = 'AICC-IntelliDoc'
    template_version = '2.0.0'
    
    def _log_request_start(self, action, request_data=None):
        """Log the start of a template operation"""
        logger.info(f"Starting template operation: {action} for template {self.template_id}")
        # Safe user access without getattr or hasattr
        try:
            user = self.request.user
        except AttributeError:
            user = 'Anonymous'
        logger.info(f"User: {user}")
        if request_data:
            logger.info(f"Request data: {request_data}")
    
    def _log_request_success(self, action, response_data=None):
        """Log successful completion of template operation"""
        logger.info(f"Successfully completed template operation: {action} for template {self.template_id}")
        if response_data:
            logger.info(f"Response data size: {len(str(response_data))} characters")
    
    def _log_request_error(self, action, error):
        """Log error in template operation"""
        logger.error(f"Error in template operation: {action} for template {self.template_id}")
        logger.error(f"Error details: {type(error).__name__}: {str(error)}")
    
    @action(detail=False, methods=['get'])
    def discover(self, request):
        """Discover AICC-IntelliDoc template capabilities"""
        self._log_request_start('discover_template')
        
        try:
            logger.info(f"Processing template discovery for {self.template_id}")
            
            # Get template metadata
            from .definition import AICCIntelliDocTemplate
            template_instance = AICCIntelliDocTemplate()
            
            logger.info(f"Loading template configuration for {self.template_id}")
            
            discovery_data = {
                'template_id': self.template_id,
                'template_name': self.template_name,
                'version': self.template_version,
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
                'endpoints': self._get_template_endpoints(),
                'independence_level': 'complete'
            }
            
            logger.info(f"Template discovery completed for {self.template_id}")
            self._log_request_success('discover_template', discovery_data)
            
            return Response({
                'status': 'success',
                'discovery': discovery_data
            })
            
        except Exception as e:
            self._log_request_error('discover_template', e)
            return Response(
                {'error': 'Template discovery failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    
    
    @action(detail=False, methods=['get'])
    def configuration(self, request):
        """Get AICC-IntelliDoc template configuration"""
        self._log_request_start('get_configuration')
        
        try:
            logger.info(f"Loading template configuration for {self.template_id}")
            
            from .definition import AICCIntelliDocTemplate
            template_instance = AICCIntelliDocTemplate()
            
            config_data = {
                'template_id': self.template_id,
                'template_name': self.template_name,
                'version': self.template_version,
                'configuration': template_instance.get_configuration(),
                'hierarchical_config': template_instance.get_hierarchical_config(),
                'processing_capabilities': template_instance.get_processing_capabilities()
            }
            
            logger.info(f"Template configuration loaded successfully for {self.template_id}")
            self._log_request_success('get_configuration', config_data)
            
            return Response({
                'status': 'success',
                'configuration': config_data
            })
            
        except Exception as e:
            self._log_request_error('get_configuration', e)
            return Response(
                {'error': 'Failed to load template configuration', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_workflow(self, request):
        """Validate agent workflow for AICC-IntelliDoc-v2 template"""
        self._log_request_start('validate_workflow', request.data)
        
        try:
            workflow_data = request.data
            project_id = workflow_data.get('project_id')
            
            if not project_id:
                return Response(
                    {'error': 'project_id is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Validating workflow for project {project_id} using template {self.template_id}")
            
            from .services import AICCIntelliDocWorkflowValidationService
            validation_service = AICCIntelliDocWorkflowValidationService()
            
            validation_result = validation_service.validate_agent_workflow(project_id, workflow_data)
            
            logger.info(f"Workflow validation completed for project {project_id}")
            self._log_request_success('validate_workflow', validation_result)
            
            return Response({
                'status': 'success',
                'validation': validation_result
            })
            
        except Exception as e:
            self._log_request_error('validate_workflow', e)
            return Response(
                {'error': 'Workflow validation failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def workflow_recommendations(self, request):
        """Get workflow optimization recommendations for AICC-IntelliDoc-v2 template"""
        self._log_request_start('workflow_recommendations', request.data)
        
        try:
            workflow_data = request.data
            project_id = workflow_data.get('project_id')
            
            if not project_id:
                return Response(
                    {'error': 'project_id is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Generating workflow recommendations for project {project_id} using template {self.template_id}")
            
            from .services import AICCIntelliDocWorkflowValidationService
            validation_service = AICCIntelliDocWorkflowValidationService()
            
            recommendations_result = validation_service.get_workflow_recommendations(project_id, workflow_data)
            
            logger.info(f"Workflow recommendations generated for project {project_id}")
            self._log_request_success('workflow_recommendations', recommendations_result)
            
            return Response({
                'status': 'success',
                'recommendations': recommendations_result
            })
            
        except Exception as e:
            self._log_request_error('workflow_recommendations', e)
            return Response(
                {'error': 'Workflow recommendations failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get AICC-IntelliDoc template status and health"""
        self._log_request_start('get_status')
        
        try:
            logger.info(f"Checking template status for {self.template_id}")
            
            # Check template services availability
            services_status = self._check_template_services()
            
            from datetime import datetime
            
            status_data = {
                'template_id': self.template_id,
                'template_name': self.template_name,
                'version': self.template_version,
                'status': 'healthy',
                'services': services_status,
                'endpoints': self._get_template_endpoints(),
                'last_checked': datetime.now().isoformat()
            }
            
            logger.info(f"Template status check completed for {self.template_id}")
            
            self._log_request_success('get_status', status_data)
            
            return Response({
                'status': 'success',
                'template_status': status_data
            })
            
        except Exception as e:
            self._log_request_error('get_status', e)
            return Response(
                {'error': 'Failed to get template status', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_template_endpoints(self):
        """Get list of template-specific endpoints"""
        base_url = f'/api/templates/{self.template_id}'
        return {
            'discover': f'{base_url}/discover/',
            'configuration': f'{base_url}/configuration/',
            'status': f'{base_url}/status/'
        }
    
    
    
    def _check_template_services(self):
        """Check template services availability"""
        logger.info(f"Checking template services for {self.template_id}")
        
        services_status = {}
        
        try:
            from .services import (
                AICCIntelliDocProcessingService,
                AICCIntelliDocSearchService,
                AICCIntelliDocHierarchyService,
                AICCIntelliDocNavigationService,
                AICCIntelliDocReconstructionService
            )
            
            services = {
                'processing': AICCIntelliDocProcessingService,
                'search': AICCIntelliDocSearchService,
                'hierarchy': AICCIntelliDocHierarchyService,
                'navigation': AICCIntelliDocNavigationService,
                'reconstruction': AICCIntelliDocReconstructionService
            }
            
            for service_name, service_class in services.items():
                try:
                    service_instance = service_class()
                    services_status[service_name] = {
                        'available': True,
                        'class': service_class.__name__
                    }
                except Exception as e:
                    services_status[service_name] = {
                        'available': False,
                        'error': str(e)
                    }
                    
        except ImportError as e:
            logger.warning(f"Template services import failed for {self.template_id}: {e}")
            services_status['import_error'] = str(e)
        
        logger.info(f"Template services check completed for {self.template_id}")
        return services_status
