# backend/mcp_servers/urls.py

from django.urls import path
from .views import MCPServerCredentialViewSet

urlpatterns = [
    # List all supported MCP server types
    path('types/', MCPServerCredentialViewSet.as_view({'get': 'types'}), name='mcp-server-types'),
    
    # List all credentials for a project
    path('projects/<uuid:project_id>/credentials/', MCPServerCredentialViewSet.as_view({'get': 'list'}), name='mcp-server-credentials-list'),
    
    # Get, create, update, or delete credentials for a specific server type
    path('projects/<uuid:project_id>/credentials/<str:server_type>/', MCPServerCredentialViewSet.as_view({
        'get': 'retrieve',
        'post': 'create',
        'delete': 'destroy'
    }), name='mcp-server-credential-detail'),
    
    # Test connection for a specific server type
    path('projects/<uuid:project_id>/credentials/<str:server_type>/test/', MCPServerCredentialViewSet.as_view({'post': 'test'}), name='mcp-server-credential-test'),
    
    # List available tools for a specific server type
    path('projects/<uuid:project_id>/credentials/<str:server_type>/tools/', MCPServerCredentialViewSet.as_view({'get': 'tools'}), name='mcp-server-credential-tools'),
]
