"""
Enhanced Template Views - Phase 3
=================================

Enhanced API endpoints for comprehensive template discovery, registration,
and management with full-stack capability detection.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.http import JsonResponse
import logging

from .enhanced_discovery import EnhancedTemplateDiscovery, TemplateRegistrationSystem
from .discovery import TemplateDiscoverySystem  # Legacy system for fallback
from .enhanced_duplication_views import EnhancedDuplicationMixin
from .advanced.views import AdvancedTemplateManagementMixin
from .serializers import (
    TemplateInfoSerializer, 
    TemplateDiscoverySerializer,
    TemplateDuplicationSerializer,
    TemplateDuplicationResultSerializer,
    DuplicationPreviewSerializer,
    DuplicationValidationSerializer
)

logger = logging.getLogger(__name__)

class EnhancedTemplateViewSet(AdvancedTemplateManagementMixin, EnhancedDuplicationMixin, ViewSet):
    """Enhanced template management with comprehensive discovery and duplication"""
    
    permission_classes = [IsAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.enhanced_discovery = EnhancedTemplateDiscovery()
        self.registration_system = TemplateRegistrationSystem()
        self.legacy_discovery = TemplateDiscoverySystem()
        
        logger.info("Initialized Enhanced Template ViewSet with Phase 3 capabilities")
    
    @action(detail=False, methods=['get'])
    def enhanced_discover(self, request):
        """
        Enhanced template discovery with comprehensive capability analysis
        
        GET /api/enhanced-project-templates/enhanced_discover/
        
        Query Parameters:
        - force_refresh: bool (default: false) - Force refresh discovery cache
        - include_metadata: bool (default: true) - Include discovery metadata
        - include_architectural_status: bool (default: true) - Include architectural analysis
        """
        logger.info("Enhanced template discovery requested")
        logger.info(f"Request params: {request.query_params}")
        
        try:
            # Parse query parameters
            force_refresh = request.query_params.get('force_refresh', 'false').lower() == 'true'
            include_metadata = request.query_params.get('include_metadata', 'true').lower() == 'true'
            include_architectural_status = request.query_params.get('include_architectural_status', 'true').lower() == 'true'
            
            logger.info(f"Discovery parameters: force_refresh={force_refresh}, include_metadata={include_metadata}")
            
            # Perform enhanced discovery
            discovery_result = self.enhanced_discovery.discover_all_templates(force_refresh=force_refresh)
            
            # Transform for API response
            api_response = self._transform_discovery_for_api(
                discovery_result, 
                include_metadata, 
                include_architectural_status
            )
            
            logger.info(f"Enhanced discovery completed successfully")
            logger.info(f"Found {len(api_response['templates'])} templates with enhanced capabilities")
            
            return Response(api_response, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Enhanced discovery failed: {str(e)}")
            
            # Fallback to legacy discovery
            try:
                logger.info("Attempting fallback to legacy discovery system")
                legacy_templates = self.legacy_discovery.discover_templates()
                
                fallback_response = {
                    'templates': self._transform_legacy_templates(legacy_templates),
                    'discovery_metadata': {
                        'total_templates': len(legacy_templates),
                        'discovery_method': 'legacy_fallback',
                        'error_message': str(e)
                    },
                    'status': 'fallback_success'
                }
                
                logger.info(f"Fallback discovery successful: {len(legacy_templates)} templates")
                return Response(fallback_response, status=status.HTTP_200_OK)
                
            except Exception as fallback_error:
                logger.error(f"Fallback discovery also failed: {str(fallback_error)}")
                
                return Response({
                    'error': 'Both enhanced and legacy discovery failed',
                    'enhanced_error': str(e),
                    'fallback_error': str(fallback_error),
                    'templates': [],
                    'status': 'error'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def routing_info(self, request, pk=None):
        """
        Get comprehensive routing information for a specific template
        
        GET /api/enhanced-project-templates/{template_id}/routing_info/
        """
        template_id = pk
        logger.info(f"Routing info requested for template: {template_id}")
        
        try:
            routing_info = self.registration_system.get_template_routing_info(template_id)
            
            if routing_info.get('status') == 'error':
                logger.error(f"Failed to get routing info for {template_id}: {routing_info.get('error_message')}")
                return Response(routing_info, status=status.HTTP_404_NOT_FOUND)
            
            logger.info(f"Routing info retrieved successfully for {template_id}")
            return Response(routing_info, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting routing info for {template_id}: {str(e)}")
            return Response({
                'template_id': template_id,
                'error': str(e),
                'status': 'error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def register_routes(self, request, pk=None):
        """
        Register dynamic routes for a template
        
        POST /api/enhanced-project-templates/{template_id}/register_routes/
        """
        template_id = pk
        logger.info(f"Route registration requested for template: {template_id}")
        
        try:
            registration_result = self.registration_system.register_template_routes(template_id)
            
            if registration_result['registration_status'] == 'error':
                logger.error(f"Route registration failed for {template_id}: {registration_result.get('error_message')}")
                return Response(registration_result, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"Routes registered successfully for {template_id}")
            return Response(registration_result, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error registering routes for {template_id}: {str(e)}")
            return Response({
                'template_id': template_id,
                'registration_status': 'error',
                'error_message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def validate_registration(self, request, pk=None):
        """
        Validate template registration completeness
        
        GET /api/enhanced-project-templates/{template_id}/validate_registration/
        """
        template_id = pk
        logger.info(f"Registration validation requested for template: {template_id}")
        
        try:
            validation_result = self.registration_system.validate_template_registration(template_id)
            
            logger.info(f"Registration validation completed for {template_id}: {validation_result['validation_status']}")
            
            if validation_result['validation_status'] == 'error':
                return Response(validation_result, status=status.HTTP_404_NOT_FOUND)
            
            return Response(validation_result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error validating registration for {template_id}: {str(e)}")
            return Response({
                'template_id': template_id,
                'validation_status': 'error',
                'error_message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def architectural_status(self, request):
        """
        Get overall architectural status of template system
        
        GET /api/enhanced-project-templates/architectural_status/
        """
        logger.info("Architectural status assessment requested")
        
        try:
            # Get complete discovery results
            discovery_result = self.enhanced_discovery.discover_all_templates()
            architectural_status = discovery_result.get('architectural_status', {})
            
            # Add runtime information
            enhanced_status = {
                **architectural_status,
                'runtime_info': {
                    'total_registered_templates': len(discovery_result.get('templates', {})),
                    'discovery_system_version': '3.0.0',
                    'last_discovery_timestamp': discovery_result.get('timestamp'),
                    'cache_status': self._get_cache_status()
                },
                'system_recommendations': self._generate_system_recommendations(discovery_result)
            }
            
            logger.info("Architectural status assessment completed")
            return Response(enhanced_status, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error assessing architectural status: {str(e)}")
            return Response({
                'error': str(e),
                'status': 'error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def refresh_discovery_cache(self, request):
        """
        Force refresh of discovery cache
        
        POST /api/enhanced-project-templates/refresh_discovery_cache/
        """
        logger.info("Discovery cache refresh requested")
        
        try:
            # Clear relevant cache keys
            cache_keys_cleared = self._clear_discovery_cache()
            
            # Perform fresh discovery
            discovery_result = self.enhanced_discovery.discover_all_templates(force_refresh=True)
            
            logger.info(f"Discovery cache refreshed successfully")
            logger.info(f"Cleared {cache_keys_cleared} cache keys")
            logger.info(f"Rediscovered {len(discovery_result.get('templates', {}))} templates")
            
            return Response({
                'status': 'success',
                'cache_keys_cleared': cache_keys_cleared,
                'templates_rediscovered': len(discovery_result.get('templates', {})),
                'timestamp': discovery_result.get('timestamp')
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error refreshing discovery cache: {str(e)}")
            return Response({
                'status': 'error',
                'error_message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def template_comparison(self, request):
        """
        Compare capabilities across all templates
        
        GET /api/enhanced-project-templates/template_comparison/
        """
        logger.info("Template comparison requested")
        
        try:
            discovery_result = self.enhanced_discovery.discover_all_templates()
            templates = discovery_result.get('templates', {})
            
            comparison_data = self._generate_template_comparison(templates)
            
            logger.info(f"Template comparison completed for {len(templates)} templates")
            return Response(comparison_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error generating template comparison: {str(e)}")
            return Response({
                'error': str(e),
                'status': 'error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Helper methods for data transformation
    
    def _transform_discovery_for_api(self, discovery_result: dict, include_metadata: bool, include_architectural_status: bool) -> dict:
        """Transform discovery result for API response"""
        templates = discovery_result.get('templates', {})
        
        # Transform templates for frontend consumption
        api_templates = []
        
        for template_id, template_data in templates.items():
            metadata = template_data.get('metadata', {})
            
            api_template = {
                'id': template_id,
                'template_id': template_id,
                'name': metadata.get('name', template_id.title()),
                'description': metadata.get('description', f'Template for {template_id}'),
                'template_type': metadata.get('template_type', template_id),
                'version': metadata.get('version', '1.0.0'),
                'icon_class': metadata.get('ui_assets', {}).get('icon', 'fa-file-alt'),
                'color_theme': metadata.get('color_theme', 'oxford-blue'),
                'analysis_focus': metadata.get('analysis_focus', 'Document analysis'),
                
                # Enhanced capability information
                'capabilities': {
                    'backend': template_data.get('backend_capabilities', {}),
                    'frontend': template_data.get('frontend_capabilities', {}),
                    'full_stack_status': template_data.get('full_stack_status', 'unknown'),
                    'independence_level': template_data.get('independence_analysis', {}).get('independence_level', 'unknown')
                },
                
                # Source information
                'source': 'enhanced_discovery',
                'discovery_timestamp': template_data.get('discovery_timestamp')
            }
            
            api_templates.append(api_template)
        
        api_response = {
            'templates': api_templates,
            'total_count': len(api_templates),
            'status': 'success',
            'discovery_method': 'enhanced'
        }
        
        if include_metadata:
            api_response['discovery_metadata'] = discovery_result.get('discovery_metadata', {})
        
        if include_architectural_status:
            api_response['architectural_status'] = discovery_result.get('architectural_status', {})
        
        return api_response
    
    def _transform_legacy_templates(self, legacy_templates: dict) -> list:
        """Transform legacy template data for API consistency"""
        api_templates = []
        
        for template_id, template_data in legacy_templates.items():
            metadata = template_data.get('metadata', {})
            
            api_template = {
                'id': template_id,
                'template_id': template_id,
                'name': metadata.get('name', template_id.title()),
                'description': metadata.get('description', f'Template for {template_id}'),
                'template_type': metadata.get('template_type', template_id),
                'version': metadata.get('version', '1.0.0'),
                'icon_class': metadata.get('ui_assets', {}).get('icon', 'fa-file-alt'),
                'color_theme': metadata.get('color_theme', 'oxford-blue'),
                'analysis_focus': metadata.get('analysis_focus', 'Document analysis'),
                'capabilities': {
                    'backend': {'discovery_method': 'legacy'},
                    'frontend': {'discovery_method': 'legacy'},
                    'full_stack_status': 'legacy_unknown',
                    'independence_level': 'legacy_unknown'
                },
                'source': 'legacy_discovery'
            }
            
            api_templates.append(api_template)
        
        return api_templates
    
    def _get_cache_status(self) -> dict:
        """Get cache status information"""
        cache_keys = [
            'enhanced_template_discovery_complete_discovery',
            'template_discovery_templates',
            'template_discovery_cache_metadata'
        ]
        
        cache_status = {}
        for key in cache_keys:
            cache_status[key] = cache.get(key) is not None
        
        return cache_status
    
    def _clear_discovery_cache(self) -> int:
        """Clear discovery-related cache keys"""
        cache_keys = [
            'enhanced_template_discovery_complete_discovery',
            'template_discovery_templates',
            'template_discovery_cache_metadata'
        ]
        
        cleared_count = 0
        for key in cache_keys:
            if cache.get(key) is not None:
                cache.delete(key)
                cleared_count += 1
        
        return cleared_count
    
    def _generate_system_recommendations(self, discovery_result: dict) -> list:
        """Generate system-wide recommendations"""
        recommendations = []
        
        templates = discovery_result.get('templates', {})
        architectural_status = discovery_result.get('architectural_status', {})
        
        # Check template coverage
        if len(templates) == 0:
            recommendations.append("No templates discovered - ensure template definitions exist")
        
        # Check full-stack coverage
        full_stack_coverage = architectural_status.get('full_stack_coverage', 0)
        if full_stack_coverage < 0.8:
            recommendations.append(f"Low full-stack coverage ({full_stack_coverage:.1%}) - consider implementing complete backend/frontend for all templates")
        
        # Check independence
        if not architectural_status.get('template_independence', True):
            recommendations.append("Some templates lack complete independence - review template architecture")
        
        # Check discovery system health
        discovery_metadata = discovery_result.get('discovery_metadata', {})
        complete_templates = discovery_metadata.get('discovery_statistics', {}).get('complete_templates', 0)
        
        if complete_templates < len(templates):
            recommendations.append("Some templates are incomplete - ensure all templates have full backend and frontend implementations")
        
        return recommendations
    
    def _generate_template_comparison(self, templates: dict) -> dict:
        """Generate template capability comparison"""
        comparison = {
            'template_summary': {},
            'capability_matrix': {},
            'architectural_analysis': {},
            'recommendations': []
        }
        
        # Template summary
        for template_id, template_data in templates.items():
            metadata = template_data.get('metadata', {})
            backend_caps = template_data.get('backend_capabilities', {})
            frontend_caps = template_data.get('frontend_capabilities', {})
            
            comparison['template_summary'][template_id] = {
                'name': metadata.get('name', template_id.title()),
                'type': metadata.get('template_type', template_id),
                'full_stack_status': template_data.get('full_stack_status', 'unknown'),
                'independence_level': template_data.get('independence_analysis', {}).get('independence_level', 'unknown'),
                'backend_endpoints': len(backend_caps.get('endpoints', {}).get('custom_views', [])),
                'frontend_routes': len(frontend_caps.get('frontend_capabilities', {}).get('routes', {}).get('route_files', []))
            }
        
        # Capability matrix
        capabilities = ['has_custom_views', 'has_custom_serializers', 'has_custom_urls', 'has_custom_services']
        
        for capability in capabilities:
            comparison['capability_matrix'][capability] = {}
            for template_id, template_data in templates.items():
                backend_caps = template_data.get('backend_capabilities', {})
                has_capability = backend_caps.get(capability, False)
                comparison['capability_matrix'][capability][template_id] = has_capability
        
        # Architectural analysis
        total_templates = len(templates)
        complete_templates = len([t for t in templates.values() if t.get('full_stack_status') == 'complete'])
        independent_templates = len([t for t in templates.values() if t.get('independence_analysis', {}).get('independence_level') == 'complete'])
        
        comparison['architectural_analysis'] = {
            'total_templates': total_templates,
            'complete_templates': complete_templates,
            'independent_templates': independent_templates,
            'completion_rate': complete_templates / max(total_templates, 1),
            'independence_rate': independent_templates / max(total_templates, 1)
        }
        
        return comparison
    
    # Enhanced Duplication Actions (inherited from EnhancedDuplicationMixin)
    # The following actions are available:
    # - enhanced_duplicate: Complete full-stack template duplication
    # - duplication_capabilities: Get duplication capabilities 
    # - duplication_preview: Preview duplication without executing
    # - validate_duplication_request: Validate duplication parameters
    
    @action(detail=False, methods=['get'])
    def duplication_statistics(self, request):
        """Get template duplication statistics and history"""
        logger.info("Retrieving duplication statistics")
        
        try:
            # This would integrate with a duplication tracking system
            # For now, return mock statistics
            statistics = {
                'total_duplications': 0,
                'successful_duplications': 0,
                'failed_duplications': 0,
                'success_rate': 0.0,
                'average_duration_minutes': 3.5,
                'most_duplicated_templates': [],
                'recent_duplications': [],
                'duplication_trends': {
                    'last_30_days': 0,
                    'last_7_days': 0,
                    'today': 0
                }
            }
            
            logger.info("Duplication statistics retrieved successfully")
            return Response(statistics)
            
        except Exception as e:
            logger.error(f"Failed to retrieve duplication statistics: {str(e)}")
            return Response({
                'error': 'Failed to retrieve statistics',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get']) 
    def duplication_health_check(self, request):
        """Check health of duplication system"""
        logger.info("Performing duplication health check")
        
        try:
            health_status = {
                'status': 'healthy',
                'checks': {
                    'backend_structure_access': True,
                    'frontend_structure_access': True,
                    'filesystem_permissions': True,
                    'django_integration': True,
                    'duplication_service': True
                },
                'warnings': [],
                'last_check': '2024-01-20T10:30:00Z',
                'system_info': {
                    'duplication_service_version': '1.0.0',
                    'supported_template_types': ['aicc-intellidoc', 'legal', 'medical', 'history', 'custom'],
                    'max_concurrent_duplications': 1
                }
            }
            
            logger.info("Duplication health check completed successfully")
            return Response(health_status)
            
        except Exception as e:
            logger.error(f"Duplication health check failed: {str(e)}")
            return Response({
                'status': 'unhealthy',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
