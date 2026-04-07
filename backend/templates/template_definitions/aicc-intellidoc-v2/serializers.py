# templates/template_definitions/aicc-intellidoc/serializers.py

from rest_framework import serializers
import logging

# Template-specific logger
logger = logging.getLogger('templates.aicc-intellidoc')

class AICCIntelliDocTemplateDiscoverySerializer(serializers.Serializer):
    """Serializer for AICC-IntelliDoc template discovery data"""
    
    template_id = serializers.CharField(read_only=True)
    template_name = serializers.CharField(read_only=True)
    version = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    capabilities = serializers.DictField(read_only=True)
    configuration = serializers.DictField(read_only=True)
    endpoints = serializers.DictField(read_only=True)
    independence_level = serializers.CharField(read_only=True)
    
    def to_representation(self, instance):
        logger.info(f"Serializing template discovery data for {instance.get('template_id', 'unknown')}")
        representation = super().to_representation(instance)
        logger.info(f"Template discovery serialization completed")
        return representation

class AICCIntelliDocTemplateConfigurationSerializer(serializers.Serializer):
    """Serializer for AICC-IntelliDoc template configuration"""
    
    template_id = serializers.CharField(read_only=True)
    template_name = serializers.CharField(read_only=True)
    version = serializers.CharField(read_only=True)
    configuration = serializers.DictField(read_only=True)
    hierarchical_config = serializers.DictField(read_only=True)
    processing_capabilities = serializers.DictField(read_only=True)
    
    def to_representation(self, instance):
        logger.info(f"Serializing template configuration for {instance.get('template_id', 'unknown')}")
        representation = super().to_representation(instance)
        logger.info(f"Template configuration serialization completed")
        return representation

class AICCIntelliDocTemplateDuplicationSerializer(serializers.Serializer):
    """Serializer for AICC-IntelliDoc template duplication requests"""
    
    new_template_id = serializers.CharField(
        required=True,
        help_text="ID for the new template (e.g., 'aicc-intellidoc-v2', 'my-custom-template')"
    )
    new_template_name = serializers.CharField(
        required=False,
        default="Template Copy",
        help_text="Display name for the new template"
    )
    copy_frontend = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether to copy frontend components (Phase 2 feature)"
    )
    copy_backend = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether to copy backend components"
    )
    
    def validate_new_template_id(self, value):
        """Validate new template ID format"""
        logger.info(f"Validating new template ID: {value}")
        
        import re
        if not re.match(r'^[a-z0-9-]+$', value):
            logger.warning(f"Invalid template ID format: {value}")
            raise serializers.ValidationError(
                "Template ID must contain only lowercase letters, numbers, and hyphens"
            )
        
        # Check if template already exists
        from pathlib import Path
        from django.conf import settings
        
        templates_base = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
        target_dir = templates_base / value
        
        if target_dir.exists():
            logger.warning(f"Template ID already exists: {value}")
            raise serializers.ValidationError(
                f"Template with ID '{value}' already exists"
            )
        
        logger.info(f"Template ID validation passed: {value}")
        return value
    
    def validate(self, data):
        """Validate duplication request data"""
        logger.info(f"Validating template duplication request: {data}")
        
        if not data.get('copy_frontend') and not data.get('copy_backend'):
            logger.warning("Template duplication request with no components to copy")
            raise serializers.ValidationError(
                "At least one of copy_frontend or copy_backend must be True"
            )
        
        logger.info(f"Template duplication validation passed")
        return data

class AICCIntelliDocTemplateStatusSerializer(serializers.Serializer):
    """Serializer for AICC-IntelliDoc template status information"""
    
    template_id = serializers.CharField(read_only=True)
    template_name = serializers.CharField(read_only=True)
    version = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    files = serializers.DictField(read_only=True)
    services = serializers.DictField(read_only=True)
    endpoints = serializers.DictField(read_only=True)
    last_checked = serializers.DateTimeField(read_only=True)
    
    def to_representation(self, instance):
        logger.info(f"Serializing template status for {instance.get('template_id', 'unknown')}")
        representation = super().to_representation(instance)
        logger.info(f"Template status serialization completed")
        return representation

class AICCIntelliDocDuplicationResultSerializer(serializers.Serializer):
    """Serializer for template duplication results"""
    
    source_template = serializers.CharField(read_only=True)
    new_template = serializers.CharField(read_only=True)
    new_template_name = serializers.CharField(read_only=True)
    backend = serializers.DictField(read_only=True)
    frontend = serializers.DictField(read_only=True)
    references = serializers.DictField(read_only=True)
    verification = serializers.DictField(read_only=True)
    independence_level = serializers.CharField(read_only=True)
    
    def to_representation(self, instance):
        logger.info(f"Serializing template duplication result: {instance.get('source_template', 'unknown')} -> {instance.get('new_template', 'unknown')}")
        representation = super().to_representation(instance)
        logger.info(f"Template duplication result serialization completed")
        return representation
