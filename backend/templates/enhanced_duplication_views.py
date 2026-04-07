"""
Enhanced Template Duplication Views

API endpoints for comprehensive template duplication with full-stack coordination
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.utils import timezone
import logging
from .enhanced_duplication import EnhancedTemplateDuplicationService
from .serializers import TemplateDuplicationSerializer, TemplateDuplicationResultSerializer

logger = logging.getLogger('templates.enhanced_duplication_views')

class EnhancedDuplicationMixin:
    """
    Mixin for enhanced template duplication functionality
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplication_service = EnhancedTemplateDuplicationService()
    
    @action(detail=True, methods=['post'], permission_classes=[])
    def enhanced_duplicate(self, request, pk=None):
        """
        Enhanced template duplication with complete full-stack coordination
        
        Performs comprehensive duplication including:
        - Backend structure (views, serializers, URLs, services)
        - Frontend structure (routes, components, services, types)
        - Full-stack integration coordination
        - Template independence verification
        """
        logger.info(f"Starting enhanced template duplication for template: {pk}")
        logger.info(f"Request data: {request.data}")
        
        try:
            # Validate request data
            serializer = TemplateDuplicationSerializer(data=request.data)
            if not serializer.is_valid():
                logger.warning(f"Invalid duplication request: {serializer.errors}")
                return Response({
                    'status': 'error',
                    'message': 'Invalid request data',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            source_template_id = pk
            new_template_id = validated_data['new_template_id']
            new_template_config = validated_data.get('template_config', {})
            
            logger.info(f"Processing duplication: {source_template_id} -> {new_template_id}")
            logger.info(f"New template configuration: {new_template_config}")
            
            # Perform enhanced duplication with transaction
            with transaction.atomic():
                logger.info("Starting enhanced duplication transaction")
                
                duplication_results = self.duplication_service.duplicate_template_complete_fullstack(
                    source_template_id=source_template_id,
                    new_template_id=new_template_id,
                    new_template_config=new_template_config
                )
                
                logger.info("Enhanced duplication transaction completed")
            
            # Serialize results
            result_serializer = TemplateDuplicationResultSerializer(duplication_results)
            
            # Determine response status based on duplication results
            if duplication_results['status'] == 'completed':
                response_status = status.HTTP_201_CREATED
                logger.info(f"Enhanced template duplication completed successfully: {new_template_id}")
            else:
                response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
                logger.error(f"Enhanced template duplication failed: {duplication_results.get('errors', [])}")
            
            return Response(result_serializer.data, status=response_status)
            
        except Exception as e:
            logger.error(f"Enhanced template duplication error: {str(e)}")
            return Response({
                'status': 'error',
                'message': 'Template duplication failed',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def duplication_capabilities(self, request):
        """
        Get enhanced duplication capabilities and requirements
        """
        logger.info("Retrieving duplication capabilities")
        
        capabilities = {
            'supported_features': [
                'complete_backend_duplication',
                'complete_frontend_duplication', 
                'fullstack_integration_coordination',
                'template_independence_verification',
                'comprehensive_logging',
                'transaction_safety',
                'rollback_on_failure'
            ],
            'backend_duplication': {
                'files_duplicated': [
                    'definition.py',
                    'views.py',
                    'serializers.py', 
                    'urls.py',
                    'services.py',
                    'metadata.json',
                    'hierarchical_config.py'
                ],
                'directories_duplicated': [
                    'components/',
                    'assets/'
                ]
            },
            'frontend_duplication': {
                'routes_duplicated': [
                    'template_selection_pages',
                    'template_components'
                ],
                'libraries_duplicated': [
                    'template_services',
                    'template_components',
                    'template_types'
                ],
                'files_updated': [
                    'api_service_endpoints',
                    'type_definitions',
                    'import_references'
                ]
            },
            'integration_coordination': [
                'django_url_registration',
                'api_endpoint_coordination',
                'frontend_backend_integration',
                'type_system_coordination',
                'authentication_flow_verification'
            ],
            'independence_verification': [
                'template_isolation_check',
                'project_independence_check',
                'file_independence_check',
                'api_separation_check',
                'cross_dependency_check'
            ],
            'requirements': {
                'source_template_exists': True,
                'new_template_id_unique': True,
                'valid_template_configuration': True,
                'sufficient_permissions': True
            }
        }
        
        return Response(capabilities)
    
    @action(detail=True, methods=['get'])
    def duplication_preview(self, request, pk=None):
        """
        Preview what would be duplicated without actually performing duplication
        """
        logger.info(f"Generating duplication preview for template: {pk}")
        
        try:
            source_template_id = pk
            
            # Generate preview of what would be duplicated
            preview = {
                'source_template': source_template_id,
                'backend_structure': self._preview_backend_structure(source_template_id),
                'frontend_structure': self._preview_frontend_structure(source_template_id),
                'integration_points': self._preview_integration_points(source_template_id),
                'verification_checks': self._preview_verification_checks(),
                'estimated_duration': '2-5 minutes',
                'complexity_level': 'high'
            }
            
            logger.info(f"Duplication preview generated for template: {source_template_id}")
            return Response(preview)
            
        except Exception as e:
            logger.error(f"Failed to generate duplication preview: {str(e)}")
            return Response({
                'status': 'error',
                'message': 'Failed to generate preview',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def validate_duplication_request(self, request):
        """
        Validate a duplication request without performing the actual duplication
        """
        logger.info("Validating duplication request")
        logger.info(f"Request data: {request.data}")
        
        try:
            # Validate request structure
            serializer = TemplateDuplicationSerializer(data=request.data)
            
            validation_results = {
                'request_valid': serializer.is_valid(),
                'validation_errors': serializer.errors if not serializer.is_valid() else [],
                'requirements_check': {},
                'recommendations': []
            }
            
            if serializer.is_valid():
                validated_data = serializer.validated_data
                source_template_id = validated_data.get('source_template_id')
                new_template_id = validated_data['new_template_id']
                
                # Check requirements
                validation_results['requirements_check'] = self._check_duplication_requirements(
                    source_template_id, new_template_id
                )
                
                # Generate recommendations
                validation_results['recommendations'] = self._generate_duplication_recommendations(
                    source_template_id, new_template_id, validated_data
                )
            
            logger.info(f"Duplication request validation completed: {validation_results['request_valid']}")
            return Response(validation_results)
            
        except Exception as e:
            logger.error(f"Duplication request validation failed: {str(e)}")
            return Response({
                'status': 'error',
                'message': 'Validation failed',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _preview_backend_structure(self, source_template_id: str) -> dict:
        """Preview backend structure that would be duplicated"""
        from pathlib import Path
        from django.conf import settings
        
        templates_root = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
        source_path = templates_root / source_template_id
        
        preview = {
            'source_exists': source_path.exists(),
            'files_to_duplicate': [],
            'directories_to_duplicate': []
        }
        
        if source_path.exists():
            # List files that would be duplicated
            backend_files = [
                'definition.py', 'views.py', 'serializers.py', 
                'urls.py', 'services.py', 'metadata.json', 'hierarchical_config.py'
            ]
            
            for file_name in backend_files:
                file_path = source_path / file_name
                if file_path.exists():
                    preview['files_to_duplicate'].append(file_name)
            
            # List directories that would be duplicated
            for item in source_path.iterdir():
                if item.is_dir():
                    preview['directories_to_duplicate'].append(item.name)
        
        return preview
    
    def _preview_frontend_structure(self, source_template_id: str) -> dict:
        """Preview frontend structure that would be duplicated"""
        frontend_root = self._get_frontend_root()
        
        preview = {
            'routes_to_duplicate': [],
            'libraries_to_duplicate': [],
            'files_to_update': []
        }
        
        # Check route structure
        source_routes = frontend_root / 'routes' / 'features' / source_template_id
        if source_routes.exists():
            preview['routes_to_duplicate'] = [f.name for f in source_routes.rglob('*') if f.is_file()]
        
        # Check library structure
        source_lib = frontend_root / 'lib' / 'templates' / source_template_id
        if source_lib.exists():
            preview['libraries_to_duplicate'] = [f.name for f in source_lib.rglob('*') if f.is_file()]
        
        # Files that would be updated
        preview['files_to_update'] = ['types.ts', 'api_service_imports']
        
        return preview
    
    def _preview_integration_points(self, source_template_id: str) -> list:
        """Preview integration points that would be coordinated"""
        return [
            'Django URL configuration updates',
            'API endpoint registration',
            'Frontend API service coordination',
            'TypeScript type system alignment',
            'Authentication flow verification',
            'End-to-end integration testing'
        ]
    
    def _preview_verification_checks(self) -> list:
        """Preview verification checks that would be performed"""
        return [
            'Template isolation verification',
            'Project independence validation',
            'File independence confirmation',
            'API separation verification',
            'Cross-dependency analysis'
        ]
    
    def _check_duplication_requirements(self, source_template_id: str, new_template_id: str) -> dict:
        """Check duplication requirements"""
        from pathlib import Path
        from django.conf import settings
        
        templates_root = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
        source_path = templates_root / source_template_id
        target_path = templates_root / new_template_id
        
        return {
            'source_template_exists': source_path.exists() if source_template_id else False,
            'new_template_id_unique': not target_path.exists(),
            'valid_template_id_format': self._validate_template_id_format(new_template_id),
            'sufficient_filesystem_permissions': True,  # Simplified check
            'frontend_structure_accessible': self._get_frontend_root().exists()
        }
    
    def _generate_duplication_recommendations(self, source_template_id: str, new_template_id: str, data: dict) -> list:
        """Generate duplication recommendations"""
        recommendations = []
        
        # Template ID recommendations
        if '_' in new_template_id:
            recommendations.append("Consider using kebab-case (hyphens) instead of underscores for template ID")
        
        # Configuration recommendations
        template_config = data.get('template_config', {})
        if not template_config.get('name'):
            recommendations.append("Consider providing a display name in template configuration")
        
        if not template_config.get('description'):
            recommendations.append("Consider providing a description in template configuration")
        
        return recommendations
    
    def _validate_template_id_format(self, template_id: str) -> bool:
        """Validate template ID format"""
        import re
        # Allow alphanumeric characters and hyphens, must start with letter
        pattern = r'^[a-z][a-z0-9-]*$'
        return bool(re.match(pattern, template_id))
    
    def _get_frontend_root(self):
        """Get frontend root directory"""
        from pathlib import Path
        from django.conf import settings
        return Path(settings.BASE_DIR).parent / 'frontend' / 'my-sveltekit-app' / 'src'
