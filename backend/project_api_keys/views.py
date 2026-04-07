# backend/project_api_keys/views_fixed.py

import logging
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from users.models import IntelliDocProject, ProjectAPIKey
from .services import get_project_api_key_service
from .serializers import (
    ProjectAPIKeyCreateSerializer,
    ProjectAPIKeySerializer,
    ProjectAPIKeyStatusSerializer,
    APIKeyValidationSerializer,
    AvailableProvidersSerializer
)

logger = logging.getLogger(__name__)

class ProjectAPIKeyViewSet(viewsets.ViewSet):
    """ViewSet for managing project-specific API keys - FIXED VERSION"""
    
    permission_classes = [IsAuthenticated]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key_service = get_project_api_key_service()
    
    def get_project(self, project_id):
        """Get project and ensure user has access using project permission system"""
        project = get_object_or_404(
            IntelliDocProject,
            project_id=project_id
        )
        
        # Use project permission system to verify access (not just creator check)
        if not project.has_user_access(self.request.user):
            logger.warning(f"🚫 API KEY ACCESS: User {self.request.user.email} denied access to project {project.name} (project_id: {project_id})")
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to access this project's API keys")
        
        return project
    
    @action(detail=False, methods=['get'], url_path='providers')
    def available_providers(self, request):
        """Get list of available API providers"""
        try:
            providers = self.api_key_service.get_available_providers()
            serializer = AvailableProvidersSerializer(providers, many=True)
            
            return Response({
                'success': True,
                'providers': serializer.data
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to get available providers: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='project/(?P<project_id>[^/.]+)/status')
    def project_status(self, request, project_id=None):
        """Get API keys status for a project"""
        try:
            logger.info(f"🔑 Getting API key status for project: {project_id}")
            project = self.get_project(project_id)
            status_data = self.api_key_service.get_project_api_keys_status(project)
            
            serializer = ProjectAPIKeyStatusSerializer(status_data)
            
            return Response({
                'success': True,
                'status': serializer.data
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to get project API keys status: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get', 'post'], url_path='project/(?P<project_id>[^/.]+)/keys')
    def manage_project_keys(self, request, project_id=None):
        """Handle both GET (list) and POST (create/update) for project API keys"""
        if request.method == 'GET':
            return self._list_project_keys(request, project_id)
        elif request.method == 'POST':
            return self._set_api_key(request, project_id)
    
    def _list_project_keys(self, request, project_id):
        """List all API keys for a project"""
        try:
            logger.info(f"🔑 Listing API keys for project: {project_id}")
            project = self.get_project(project_id)
            
            api_keys = ProjectAPIKey.objects.filter(
                project=project,
                is_active=True
            ).select_related('created_by')
            
            serializer = ProjectAPIKeySerializer(api_keys, many=True)
            
            logger.info(f"✅ Retrieved {len(serializer.data)} API keys")
            return Response({
                'success': True,
                'api_keys': serializer.data,
                'count': len(serializer.data)
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to list project API keys: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _set_api_key(self, request, project_id):
        """Set or update an API key for a project"""
        try:
            logger.info(f"🔑 Setting API key for project: {project_id}")
            logger.info(f"🔑 Request data: {request.data}")
            
            project = self.get_project(project_id)
            
            serializer = ProjectAPIKeyCreateSerializer(data=request.data)
            if not serializer.is_valid():
                logger.warning(f"🔑 Validation errors: {serializer.errors}")
                return Response(
                    {'success': False, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            data = serializer.validated_data
            logger.info(f"🔑 Validated data: {data}")
            
            # Set the API key
            api_key_obj, created = self.api_key_service.set_project_api_key(
                project=project,
                provider_type=data['provider_type'],
                api_key=data['api_key'],
                user=request.user,
                key_name=data.get('key_name', ''),
                validate_key=data.get('validate_key', True)
            )
            
            # Return the created/updated key info
            key_serializer = ProjectAPIKeySerializer(api_key_obj)
            
            logger.info(f"✅ API key {'created' if created else 'updated'} successfully")
            return Response({
                'success': True,
                'created': created,
                'api_key': key_serializer.data,
                'message': f"API key {'created' if created else 'updated'} successfully"
            })
            
        except ValueError as e:
            logger.warning(f"⚠️ API key validation error: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"❌ Failed to set API key: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='project/(?P<project_id>[^/.]+)/keys/(?P<provider_type>[^/.]+)/validate')
    def validate_api_key(self, request, project_id=None, provider_type=None):
        """Validate an existing API key"""
        try:
            logger.info(f"🔑 Validating API key for {provider_type} in project: {project_id}")
            project = self.get_project(project_id)
            
            # Get the API key object
            api_key_obj = get_object_or_404(
                ProjectAPIKey,
                project=project,
                provider_type=provider_type
            )
            
            # Validate the key
            validation_result = self.api_key_service.validate_api_key(api_key_obj)
            
            # Update the API key object with validation results
            api_key_obj.is_validated = validation_result['is_valid']
            api_key_obj.validation_error = validation_result['error']
            if validation_result['is_valid']:
                api_key_obj.last_validated_at = timezone.now()
            api_key_obj.save()
            
            serializer = APIKeyValidationSerializer({
                'provider_type': provider_type,
                **validation_result
            })
            
            return Response({
                'success': True,
                'validation': serializer.data
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to validate API key: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['delete'], url_path='project/(?P<project_id>[^/.]+)/keys/(?P<provider_type>[^/.]+)')
    def delete_api_key(self, request, project_id=None, provider_type=None):
        """Delete an API key for a project and provider"""
        try:
            logger.info(f"🗑️ Deleting API key for {provider_type} in project: {project_id}")
            project = self.get_project(project_id)
            
            success = self.api_key_service.delete_project_api_key(
                project=project,
                provider_type=provider_type
            )
            
            if success:
                logger.info(f"✅ API key for {provider_type} deleted successfully")
                return Response({
                    'success': True,
                    'message': f'API key for {provider_type} deleted successfully'
                })
            else:
                return Response(
                    {'success': False, 'error': 'Failed to delete API key'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Exception as e:
            logger.error(f"❌ Failed to delete API key: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
