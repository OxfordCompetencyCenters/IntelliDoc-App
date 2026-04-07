# backend/mcp_servers/serializers.py

from rest_framework import serializers
from users.models import MCPServerCredential, MCPServerType


class MCPServerCredentialSerializer(serializers.ModelSerializer):
    """Serializer for MCP Server Credentials (read-only for security)"""
    
    class Meta:
        model = MCPServerCredential
        fields = [
            'server_type',
            'credential_name',
            'is_active',
            'is_validated',
            'validation_error',
            'last_validated_at',
            'usage_count',
            'last_used_at',
            'status_display',
            'server_config'
        ]
        read_only_fields = fields


class MCPServerCredentialCreateSerializer(serializers.Serializer):
    """Serializer for creating/updating MCP server credentials"""
    credentials = serializers.DictField(required=True, help_text="Credentials dictionary (will be encrypted)")
    credential_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    server_config = serializers.DictField(required=False, default=dict)
    validate_credentials = serializers.BooleanField(required=False, default=True)


class MCPServerTypeSerializer(serializers.Serializer):
    """Serializer for MCP server type information"""
    code = serializers.CharField()
    name = serializers.CharField()
    display_name = serializers.CharField()
    description = serializers.CharField()
    icon = serializers.CharField()
    color = serializers.CharField()

