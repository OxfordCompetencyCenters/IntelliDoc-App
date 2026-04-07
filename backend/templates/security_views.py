from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth import get_user_model
from django.utils import timezone
from pathlib import Path
from templates.discovery import TemplateDiscoverySystem
from templates.security import TemplateSecurityManager, TemplateValidator, TemplateOperationManager
from templates.models import TemplateOperation
from api.serializers import ProjectTemplateSerializer, TemplateConfigurationSerializer, TemplateDuplicationSerializer
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class TemplateSecurityViewSet(viewsets.GenericViewSet):
    """Enhanced template management with security and validation"""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def discover(self, request):
        """Discover templates with security validation"""
        try:
            # Force discovery with security validation
            templates = TemplateDiscoverySystem.discover_templates(force_refresh=True)
            
            # Convert to serializable format
            template_list = []
            for template_id, template_info in templates.items():
                if template_info.get('security_validated', False):
                    metadata = template_info.get('metadata', {})
                    template_list.append({
                        'id': template_id,
                        'template_type': metadata.get('template_type'),
                        'name': metadata.get('name'),
                        'description': metadata.get('description'),
                        'icon_class': metadata.get('ui_assets', {}).get('icon', 'fa-file-alt'),
                        'color_theme': 'oxford-blue',
                        'source': 'folder',
                        'version': metadata.get('version'),
                        'author': metadata.get('author'),
                        'features': metadata.get('features', {}),
                        'security_validated': True
                    })
            
            return Response({
                'discovered_count': len(templates),
                'validated_count': len(template_list),
                'templates': template_list
            })
            
        except Exception as e:
            logger.error(f"Template discovery error: {str(e)}")
            return Response({
                'error': 'Failed to discover templates',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def configuration(self, request, pk=None):
        """Get complete template configuration"""
        try:
            template_config = TemplateDiscoverySystem.get_template_configuration(pk)
            
            if not template_config:
                return Response({
                    'error': 'Template not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'template_id': pk,
                'configuration': template_config
            })
            
        except Exception as e:
            logger.error(f"Template configuration error: {str(e)}")
            return Response({
                'error': 'Failed to get template configuration',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Validate template security and integrity"""
        try:
            template_dir = TemplateDiscoverySystem.get_template_definitions_path() / pk
            
            if not template_dir.exists():
                return Response({
                    'error': 'Template not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            validation_level = request.data.get('level', 'comprehensive')
            
            # Run security validation
            security_result = TemplateSecurityManager.validate_template_directory(template_dir)
            
            # Run comprehensive validation
            validator = TemplateValidator(template_dir)
            is_valid, results = validator.validate_template(validation_level)
            
            # Categorize results
            errors = [r for r in results if r.level.value == 'error']
            warnings = [r for r in results if r.level.value == 'warning']
            infos = [r for r in results if r.level.value == 'info']
            
            return Response({
                'template_id': pk,
                'validation_level': validation_level,
                'is_valid': is_valid and security_result['valid'],
                'security_valid': security_result['valid'],
                'results': {
                    'errors': [r.message for r in errors] + security_result.get('errors', []),
                    'warnings': [r.message for r in warnings],
                    'infos': [r.message for r in infos]
                }
            })
            
        except Exception as e:
            logger.error(f"Template validation error: {str(e)}")
            return Response({
                'error': 'Failed to validate template',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def duplicate(self, request):
        """Securely duplicate a template"""
        try:
            serializer = TemplateDuplicationSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            source_template = serializer.validated_data['source_template']
            new_template_id = serializer.validated_data['new_template_id']
            new_name = serializer.validated_data.get('new_name')
            new_description = serializer.validated_data.get('new_description')
            new_author = serializer.validated_data.get('new_author')
            
            # Get template paths
            template_dir = TemplateDiscoverySystem.get_template_definitions_path()
            source_dir = template_dir / source_template
            target_dir = template_dir / new_template_id
            
            # Check if source exists
            if not source_dir.exists():
                return Response({
                    'error': 'Source template not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if target exists
            if target_dir.exists():
                return Response({
                    'error': 'Target template already exists'
                }, status=status.HTTP_409_CONFLICT)
            
            # Use concurrency manager for safe duplication
            with TemplateOperationManager.template_operation(
                'duplicate', 
                source_template, 
                request.user,
                details={
                    'source_template': source_template,
                    'new_template_id': new_template_id,
                    'new_name': new_name,
                    'new_description': new_description,
                    'new_author': new_author
                }
            ) as operation:
                
                # Prepare metadata updates
                metadata_updates = {}
                if new_name:
                    metadata_updates['name'] = new_name
                if new_description:
                    metadata_updates['description'] = new_description
                if new_author:
                    metadata_updates['author'] = new_author
                
                # Perform secure duplication
                success, errors = TemplateSecurityManager.safe_duplicate_template(
                    source_dir=source_dir,
                    target_dir=target_dir,
                    new_template_id=new_template_id,
                    metadata_updates=metadata_updates
                )
                
                if success:
                    # Invalidate cache
                    TemplateDiscoverySystem.discover_templates(force_refresh=True)
                    
                    return Response({
                        'success': True,
                        'new_template_id': new_template_id,
                        'message': 'Template duplicated successfully',
                        'operation_id': str(operation.operation_id)
                    })
                else:
                    raise Exception(f"Duplication failed: {'; '.join(errors)}")
            
        except Exception as e:
            logger.error(f"Template duplication error: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to duplicate template',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def operations(self, request):
        """Get template operations for current user"""
        try:
            # Get operations for current user
            operations = TemplateOperation.objects.filter(user=request.user)
            
            # Filter by status if provided
            status_filter = request.query_params.get('status')
            if status_filter:
                operations = operations.filter(status=status_filter)
            
            # Filter by template_id if provided
            template_id = request.query_params.get('template_id')
            if template_id:
                operations = operations.filter(template_id=template_id)
            
            # Limit results
            operations = operations[:50]
            
            operation_data = []
            for op in operations:
                operation_data.append({
                    'operation_id': str(op.operation_id),
                    'operation_type': op.operation_type,
                    'template_id': op.template_id,
                    'status': op.status,
                    'started_at': op.started_at,
                    'completed_at': op.completed_at,
                    'duration_seconds': op.duration_seconds,
                    'error_message': op.error_message,
                    'details': op.details
                })
            
            return Response({
                'operations': operation_data,
                'count': len(operation_data)
            })
            
        except Exception as e:
            logger.error(f"Operations query error: {str(e)}")
            return Response({
                'error': 'Failed to get operations',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def stats(self, request):
        """Get template operation statistics"""
        try:
            from templates.security.concurrency_manager import TemplateOperationMonitor
            
            hours = int(request.query_params.get('hours', 24))
            stats = TemplateOperationMonitor.get_operation_stats(hours)
            
            return Response({
                'period_hours': hours,
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Stats query error: {str(e)}")
            return Response({
                'error': 'Failed to get statistics',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
