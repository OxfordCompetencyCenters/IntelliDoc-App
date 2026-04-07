# templates/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
import time
import logging
from .serializers import (
    TemplateSerializer,
    TemplateConfigSerializer,
    TemplateDuplicationSerializer,
    EnhancedIntelliDocProjectSerializer
)
from .discovery import TemplateDiscoverySystem
from .cache import TemplateDiscoveryCache, TemplateConfigurationCache
from .security.security_manager import TemplateSecurityManager
from .simple_duplication import SimpleTemplateDuplicationService
from api.permissions import IsAdminUser

# Additional serializers for missing types
class DiscoveryResponseSerializer:
    def __init__(self, data):
        self.data = data

class CacheStatisticsSerializer:
    def __init__(self, data):
        self.data = data

logger = logging.getLogger(__name__)

class ProjectTemplateViewSet(viewsets.GenericViewSet):
    """ViewSet for folder-based template management"""
    
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['duplicate', 'cache_stats', 'cache_management']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]
    
    def list(self, request):
        """List all available templates from folder-based discovery"""
        start_time = time.time()
        
        try:
            # Use simple duplication service for consistent template listing
            duplication_service = SimpleTemplateDuplicationService()
            templates = duplication_service.get_available_templates()
            
            # If no templates found, fall back to discovery system
            if not templates:
                templates = TemplateDiscoverySystem.list_available_templates()
            
            # Serialize templates
            serializer = TemplateSerializer(templates, many=True)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return Response({
                'count': len(templates),
                'templates': serializer.data,
                'response_time_ms': round(response_time_ms, 2),
                'cache_hit': response_time_ms < 50  # Likely cache hit if < 50ms
            })
            
        except Exception as e:
            logger.error(f"Error listing templates: {str(e)}")
            return Response(
                {'error': 'Failed to load templates', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def retrieve(self, request, pk=None):
        """Get specific template details"""
        try:
            # Get template configuration
            template_config = TemplateDiscoverySystem.get_template_configuration(pk)
            
            if not template_config:
                return Response(
                    {'error': f'Template "{pk}" not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Serialize configuration
            serializer = TemplateConfigSerializer(template_config)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error retrieving template {pk}: {str(e)}")
            return Response(
                {'error': 'Failed to load template', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def discover(self, request):
        """Force template discovery and sync"""
        start_time = time.time()
        
        try:
            # Clear cache and force discovery
            TemplateDiscoveryCache.clear_cache()
            templates = TemplateDiscoverySystem.discover_templates(force_refresh=True)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            discovery_response = {
                'discovered_count': len(templates),
                'synced_count': len(templates),
                'templates': list(templates.keys()),
                'cache_refreshed': True,
                'response_time_ms': round(response_time_ms, 2)
            }
            
            serializer = DiscoveryResponseSerializer(discovery_response)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error during template discovery: {str(e)}")
            return Response(
                {'error': 'Template discovery failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def configuration(self, request, pk=None):
        """Get complete template configuration for project creation"""
        logger.info(f"Loading configuration for template: {pk}")
        
        try:
            # Get template configuration directly from discovery system (no cache to avoid recursion)
            template_data = TemplateDiscoverySystem.get_template_configuration(pk)
            
            if not template_data:
                logger.warning(f"Template configuration not found for: {pk}")
                return Response(
                    {'error': f'Template "{pk}" configuration not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Extract the configuration object (this contains the name field)
            template_config = template_data.get('configuration', {})
            
            # If configuration is empty, try metadata as fallback
            if not template_config:
                metadata = template_data.get('metadata', {})
                template_config = {
                    'name': metadata.get('name', pk.title()),
                    'description': metadata.get('description', f'Template for {pk}'),
                    'template_type': metadata.get('template_type', pk),
                    'version': metadata.get('version', '1.0.0'),
                    'author': metadata.get('author', 'Unknown'),
                    'analysis_focus': metadata.get('analysis_focus', 'Document analysis'),
                    'icon_class': metadata.get('ui_assets', {}).get('icon', 'fa-file-alt'),
                    'color_theme': metadata.get('color_theme', 'oxford-blue'),
                    'navigation_pages': [],
                    'processing_capabilities': metadata.get('processing_capabilities', {}),
                    'features': metadata.get('features', {}),
                    'ui_configuration': {},
                    'validation_rules': {}
                }
            
            logger.info(f"Successfully loaded configuration for template: {pk}")
            logger.info(f"Configuration keys: {list(template_config.keys())}")
            
            # Serialize configuration - now the name field should be available
            serializer = TemplateConfigSerializer(template_config)
            
            return Response({
                'template_id': pk,
                'configuration': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error loading template configuration for {pk}: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return Response(
                {'error': 'Failed to load template configuration', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def duplicate(self, request):
        """Duplicate template using the simple duplication service"""
        logger.info("Starting template duplication request")
        logger.info(f"Request data: {request.data}")
        
        serializer = TemplateDuplicationSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.error(f"Invalid duplication request: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get validated data
            source_template = serializer.validated_data['source_template']
            new_template_id = serializer.validated_data['new_template_id']
            new_name = serializer.validated_data['new_name']
            new_description = serializer.validated_data['new_description']
            version = serializer.validated_data['version']
            author = serializer.validated_data['author']
            
            logger.info(f"Duplicating template: {source_template} -> {new_template_id}")
            
            # Use the simple duplication service
            duplication_service = SimpleTemplateDuplicationService()
            
            # Perform duplication
            success, errors = duplication_service.duplicate_template(
                source_template_id=source_template,
                new_template_id=new_template_id,
                new_name=new_name,
                new_description=new_description,
                version=version,
                author=author
            )
            
            if not success:
                logger.error(f"Template duplication failed: {errors}")
                return Response({
                    'success': False,
                    'errors': errors,
                    'message': 'Template duplication failed'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Clear cache to refresh template list
            TemplateDiscoveryCache.clear_cache()
            
            logger.info(f"Template duplication completed successfully: {new_template_id}")
            
            return Response({
                'success': True,
                'new_template_id': new_template_id,
                'message': f'Template "{new_template_id}" created successfully',
                'errors': []
            })
            
        except Exception as e:
            logger.error(f"Error during template duplication: {str(e)}")
            return Response({
                'success': False,
                'errors': [str(e)],
                'message': 'Template duplication failed due to system error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def cache_stats(self, request):
        """Get cache statistics (admin only)"""
        try:
            stats = TemplateDiscoveryCache.get_cache_statistics()
            serializer = CacheStatisticsSerializer(stats)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {str(e)}")
            return Response(
                {'error': 'Failed to get cache statistics', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def cache_management(self, request):
        """Cache management operations (admin only)"""
        action_type = request.data.get('action')
        
        if action_type == 'clear':
            TemplateDiscoveryCache.clear_cache()
            return Response({'message': 'Cache cleared successfully'})
        
        elif action_type == 'refresh':
            TemplateDiscoveryCache.get_cached_templates(force_refresh=True)
            return Response({'message': 'Cache refreshed successfully'})
        
        elif action_type == 'preload':
            TemplateDiscoveryCache.preload_cache()
            return Response({'message': 'Cache preloaded successfully'})
        
        elif action_type == 'start_updater':
            TemplateDiscoveryCache.start_background_updater()
            return Response({'message': 'Background updater started'})
        
        elif action_type == 'stop_updater':
            TemplateDiscoveryCache.stop_background_updater()
            return Response({'message': 'Background updater stopped'})
        
        else:
            return Response(
                {'error': 'Invalid cache action', 'valid_actions': ['clear', 'refresh', 'preload', 'start_updater', 'stop_updater']},
                status=status.HTTP_400_BAD_REQUEST
            )


class IntelliDocProjectViewSet(viewsets.ModelViewSet):
    """Enhanced ViewSet for IntelliDoc projects with hierarchical template support"""
    
    serializer_class = EnhancedIntelliDocProjectSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return projects accessible to current user based on permissions"""
        from users.models import IntelliDocProject
        from django.db.models import Q
        user = self.request.user
        
        # Superusers and admin users can see all projects
        if user.is_superuser or user.is_admin:
            return IntelliDocProject.objects.all().order_by('-created_at')
        
        # Regular users see projects they created + projects they have permission to access
        return IntelliDocProject.objects.filter(
            Q(created_by=user) | 
            Q(user_permissions__user=user) | 
            Q(group_permissions__group__in=user.groups.all())
        ).distinct().order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        """Create project with complete template configuration cloning"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                # Create project with cloned template configuration
                project = serializer.save()
                
                logger.info(f"✅ Enhanced project created: {project.name} with template {project.template_type}")
                
                # Initialize vector collection if processing capabilities support it
                try:
                    from users.models import ProjectVectorCollection
                    
                    if project.processing_capabilities.get('supports_vector_search', False):
                        collection_name = project.generate_collection_name()
                        
                        ProjectVectorCollection.objects.get_or_create(
                            project=project,
                            defaults={
                                'collection_name': collection_name,
                                'status': 'PENDING'
                            }
                        )
                        
                        logger.info(f"🔄 Vector collection '{collection_name}' initialized")
                
                except Exception as e:
                    logger.warning(f"Failed to initialize vector collection: {str(e)}")
                
                # Return complete project data
                response_serializer = self.get_serializer(project)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"❌ Project creation validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"❌ Project creation failed: {e}")
            return Response(
                {'error': 'Project creation failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve project with enhanced configuration details"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            data = serializer.data
            
            # Add runtime configuration status
            data['runtime_status'] = {
                'vector_collection_exists': hasattr(instance, 'vector_collection'),
                'documents_count': instance.documents.count(),
                'ready_documents_count': instance.documents.filter(upload_status='ready').count(),
                'processing_documents_count': instance.documents.filter(upload_status='processing').count(),
                'error_documents_count': instance.documents.filter(upload_status='error').count()
            }
            
            # Add available endpoints based on capabilities
            processing_capabilities = instance.processing_capabilities or {}
            data['available_endpoints'] = self._get_available_endpoints(instance, processing_capabilities)
            
            return Response(data)
            
        except Exception as e:
            logger.error(f"❌ Project retrieval failed: {e}")
            return Response(
                {'error': 'Project retrieval failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_available_endpoints(self, project, processing_capabilities):
        """Get available endpoints based on project capabilities"""
        endpoints = {
            'basic_processing': f'/api/projects/{project.project_id}/digest/',
            'basic_search': f'/api/projects/{project.project_id}/search/',
            'vector_status': f'/api/projects/{project.project_id}/vector-status/'
        }
        
        # Enhanced unified processing (always available)
        endpoints.update({
            'enhanced_unified_processing': f'/api/projects/{project.project_id}/process-enhanced-unified/',
            'enhanced_unified_search': f'/api/projects/{project.project_id}/search-enhanced-unified/',
            'enhanced_capabilities': f'/api/projects/{project.project_id}/capabilities-enhanced/',
            'enhanced_status': f'/api/projects/{project.project_id}/processing-status-enhanced/'
        })
        
        # Hierarchical processing endpoints
        if processing_capabilities.get('supports_hierarchical_processing'):
            endpoints.update({
                'hierarchical_processing': f'/api/projects/{project.project_id}/digest-enhanced/',
                'hierarchical_search': f'/api/projects/{project.project_id}/search-enhanced/',
                'hierarchy_overview': f'/api/projects/{project.project_id}/hierarchy-overview/',
                'category_search': f'/api/projects/{project.project_id}/search-by-category/',
                'advanced_search': f'/api/projects/{project.project_id}/advanced-search/',
                'document_reconstruction': f'/api/projects/{project.project_id}/documents/{{document_id}}/full-content/',
                'categories_list': f'/api/projects/{project.project_id}/categories-enhanced/',
                'processing_capabilities_detailed': f'/api/projects/{project.project_id}/processing-capabilities/'
            })
        
        return endpoints
    
    @action(detail=True, methods=['get'])
    def configuration_summary(self, request, pk=None):
        """Get comprehensive configuration summary for a project"""
        try:
            project = self.get_object()
            
            summary = {
                'project_id': str(project.project_id),
                'project_name': project.name,
                'template_info': {
                    'template_name': project.template_name,
                    'template_type': project.template_type,
                    'icon_class': project.icon_class,
                    'color_theme': project.color_theme
                },
                'navigation_config': {
                    'has_navigation': project.has_navigation,
                    'total_pages': project.total_pages,
                    'navigation_pages': project.navigation_pages or []
                },
                'processing_config': {
                    'capabilities': project.processing_capabilities or {},
                    'hierarchical_enabled': bool(project.processing_capabilities and 
                                               project.processing_capabilities.get('supports_hierarchical_processing')),
                    'enhanced_enabled': bool(project.processing_capabilities and 
                                           project.processing_capabilities.get('supports_enhanced_processing')),
                    'content_preservation': project.processing_capabilities.get('content_preservation', 'basic') if project.processing_capabilities else 'basic'
                },
                'ui_config': project.ui_configuration or {},
                'validation_rules': project.validation_rules or {},
                'configuration_status': {
                    'complete': all([
                        project.template_name,
                        project.template_type,
                        project.processing_capabilities,
                        project.ui_configuration
                    ]),
                    'cloned_fields_count': sum(1 for field in [
                        project.template_name,
                        project.template_type,
                        project.processing_capabilities,
                        project.ui_configuration,
                        project.validation_rules
                    ] if field)
                }
            }
            
            return Response(summary)
            
        except Exception as e:
            logger.error(f"❌ Configuration summary failed: {e}")
            return Response(
                {'error': 'Configuration summary failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
