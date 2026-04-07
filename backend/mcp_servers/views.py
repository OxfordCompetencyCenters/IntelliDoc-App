# backend/mcp_servers/views.py

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from asgiref.sync import sync_to_async

from users.models import IntelliDocProject
from .services import get_mcp_server_credential_service
from .manager import get_mcp_server_manager
from .serializers import (
    MCPServerCredentialSerializer,
    MCPServerCredentialCreateSerializer,
    MCPServerTypeSerializer
)

logger = logging.getLogger(__name__)


class MCPServerCredentialViewSet(viewsets.ViewSet):
    """ViewSet for managing MCP server credentials"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def types(self, request):
        """Get list of available MCP server types"""
        try:
            service = get_mcp_server_credential_service()
            server_types = service.get_available_server_types()
            serializer = MCPServerTypeSerializer(server_types, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error getting MCP server types: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, project_id=None):
        """List MCP server credentials status for a project"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check permissions
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = get_mcp_server_credential_service()
            status_data = service.get_project_credentials_status(project)
            return Response(status_data)
        except Exception as e:
            logger.error(f"Error listing MCP server credentials: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def retrieve(self, request, project_id=None, server_type=None):
        """Get MCP server credentials for a project and server type"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check permissions
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = get_mcp_server_credential_service()
            credentials = service.get_project_credentials(project)
            credential_obj = credentials.get(server_type)
            
            if not credential_obj:
                return Response(
                    {'error': 'Credentials not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = MCPServerCredentialSerializer(credential_obj)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error retrieving MCP server credentials: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request, project_id=None, server_type=None):
        """Create or update MCP server credentials"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check permissions
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = MCPServerCredentialCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            service = get_mcp_server_credential_service()
            credential_obj, created = service.set_credentials(
                project=project,
                server_type=server_type,
                credentials=serializer.validated_data['credentials'],
                user=request.user,
                credential_name=serializer.validated_data.get('credential_name', ''),
                server_config=serializer.validated_data.get('server_config', {}),
                validate_credentials=serializer.validated_data.get('validate_credentials', True)
            )
            
            response_serializer = MCPServerCredentialSerializer(credential_obj)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating MCP server credentials: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, project_id=None, server_type=None):
        """Delete MCP server credentials"""
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check permissions
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = get_mcp_server_credential_service()
            success = service.delete_credentials(project, server_type)
            
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {'error': 'Failed to delete credentials'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            logger.error(f"Error deleting MCP server credentials: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def test(self, request, project_id=None, server_type=None):
        """Test MCP server connection"""
        import asyncio
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check permissions
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            manager = get_mcp_server_manager()
            # Run async function in sync context
            try:
                result = asyncio.run(manager.test_connection(project, server_type))
            except RuntimeError:
                # If event loop already exists, use it
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(manager.test_connection(project, server_type))
            
            if result.get('success'):
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error testing MCP server connection: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def tools(self, request, project_id=None, server_type=None):
        """Get available tools from MCP server"""
        import asyncio
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # Check permissions
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            manager = get_mcp_server_manager()
            # Run async function in sync context
            try:
                tools = asyncio.run(manager.get_available_tools(project, server_type))
            except RuntimeError:
                # If event loop already exists, use it
                loop = asyncio.get_event_loop()
                tools = loop.run_until_complete(manager.get_available_tools(project, server_type))
            
            return Response(tools)
        except Exception as e:
            logger.error(f"Error getting MCP server tools: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

