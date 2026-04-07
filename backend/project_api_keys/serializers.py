# backend/project_api_keys/serializers.py

from rest_framework import serializers
from users.models import ProjectAPIKey, ProjectAPIKeyProvider
from .encryption import encryption_service

class ProjectAPIKeySerializer(serializers.ModelSerializer):
    """Serializer for ProjectAPIKey with security features"""
    
    # Write-only field for API key input
    api_key = serializers.CharField(write_only=True, required=False)
    
    # Read-only fields for display
    masked_key = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    provider_display_info = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ProjectAPIKey
        fields = [
            'id',
            'provider_type',
            'key_name',
            'is_active',
            'is_validated',
            'validation_error',
            'last_validated_at',
            'usage_count',
            'last_used_at',
            'created_at',
            'updated_at',
            # Write-only fields
            'api_key',
            # Read-only computed fields
            'masked_key',
            'status_display',
            'provider_display_info'
        ]
        read_only_fields = [
            'id',
            'is_validated',
            'validation_error',
            'last_validated_at',
            'usage_count',
            'last_used_at',
            'created_at',
            'updated_at',
            'masked_key',
            'status_display',
            'provider_display_info'
        ]
    
    def get_masked_key(self, obj):
        """Return masked version of the API key"""
        try:
            # Try to decrypt and mask
            project_id = str(obj.project.project_id)
            decrypted_key = encryption_service.decrypt_api_key(project_id, obj.encrypted_api_key)
            
            if len(decrypted_key) <= 8:
                return "••••••••"
            return f"{decrypted_key[:4]}••••••••{decrypted_key[-4:]}"
        except Exception:
            return "••••••••••••••••"  # Fallback if decryption fails
    
    def get_status_display(self, obj):
        """Get human-readable status"""
        if not obj.is_active:
            return "Inactive"
        elif not obj.is_validated:
            return "Not Validated"
        elif obj.validation_error:
            return "Validation Failed"
        else:
            return "Active"
    
    def get_provider_display_info(self, obj):
        """Get provider display information"""
        return obj.get_provider_display_info()
    
    def create(self, validated_data):
        """Create new API key with encryption"""
        api_key = validated_data.pop('api_key', None)
        project = validated_data.get('project')
        
        if not api_key:
            raise serializers.ValidationError({
                'api_key': 'API key is required for new entries'
            })
        
        if not project:
            raise serializers.ValidationError({
                'project': 'Project is required'
            })
        
        # Encrypt the API key
        project_id = str(project.project_id)
        try:
            encrypted_key = encryption_service.encrypt_api_key(project_id, api_key)
            validated_data['encrypted_api_key'] = encrypted_key
        except Exception as e:
            raise serializers.ValidationError({
                'api_key': f'Failed to encrypt API key: {str(e)}'
            })
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update API key with optional re-encryption"""
        api_key = validated_data.pop('api_key', None)
        
        if api_key:
            # Re-encrypt with new key
            project_id = str(instance.project.project_id)
            try:
                encrypted_key = encryption_service.encrypt_api_key(project_id, api_key)
                validated_data['encrypted_api_key'] = encrypted_key
                # Reset validation status when key changes
                validated_data['is_validated'] = False
                validated_data['validation_error'] = ''
                validated_data['last_validated_at'] = None
            except Exception as e:
                raise serializers.ValidationError({
                    'api_key': f'Failed to encrypt API key: {str(e)}'
                })
        
        return super().update(instance, validated_data)
    
    def validate_provider_type(self, value):
        """Validate provider type"""
        from users.models import ProjectAPIKeyProvider
        
        if value not in [choice[0] for choice in ProjectAPIKeyProvider.choices]:
            raise serializers.ValidationError(
                f"Invalid provider type. Must be one of: {', '.join([choice[0] for choice in ProjectAPIKeyProvider.choices])}"
            )
        
        return value
    
    def validate_key_name(self, value):
        """Validate key name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Key name is required")
        
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Key name must be at least 3 characters")
        
        return value.strip()


class ProjectAPIKeyListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing API keys"""
    
    masked_key = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    provider_display_info = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ProjectAPIKey
        fields = [
            'id',
            'provider_type',
            'key_name',
            'is_active',
            'is_validated',
            'usage_count',
            'last_used_at',
            'created_at',
            'masked_key',
            'status_display',
            'provider_display_info'
        ]
    
    def get_masked_key(self, obj):
        """Return masked version of the API key"""
        return obj.masked_key if hasattr(obj, '_decrypted_key') else "••••••••••••••••"
    
    def get_status_display(self, obj):
        """Get human-readable status"""
        return obj.status_display
    
    def get_provider_display_info(self, obj):
        """Get provider display information"""
        return obj.get_provider_display_info()


class ProjectAPIKeyCreateSerializer(serializers.Serializer):
    """Serializer for creating/updating API keys"""
    
    provider_type = serializers.ChoiceField(
        choices=[choice[0] for choice in ProjectAPIKeyProvider.choices],
        required=True
    )
    api_key = serializers.CharField(required=True, write_only=True)
    key_name = serializers.CharField(required=False, allow_blank=True, default='')
    validate_key = serializers.BooleanField(required=False, default=True)
    
    def validate_api_key(self, value):
        """Validate API key format"""
        if not value or not value.strip():
            raise serializers.ValidationError("API key cannot be empty")
        return value.strip()
    
    def validate_key_name(self, value):
        """Validate key name"""
        if value and len(value.strip()) < 3:
            raise serializers.ValidationError("Key name must be at least 3 characters if provided")
        return value.strip() if value else ''


class ProjectAPIKeyStatusSerializer(serializers.Serializer):
    """Serializer for project API key status"""
    
    project_id = serializers.UUIDField(read_only=True)
    project_name = serializers.CharField(read_only=True)
    providers = serializers.ListField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)


class APIKeyValidationSerializer(serializers.Serializer):
    """Serializer for API key validation results"""
    
    provider_type = serializers.CharField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    error = serializers.CharField(read_only=True, required=False)
    validated_at = serializers.DateTimeField(read_only=True, required=False)


class AvailableProvidersSerializer(serializers.Serializer):
    """Serializer for available providers"""
    
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)
    color = serializers.CharField(read_only=True)
