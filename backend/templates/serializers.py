# templates/serializers.py
from rest_framework import serializers
from .discovery import TemplateDiscoverySystem
from django.core.cache import cache
import logging

# Import IntelliDocProject model
from users.models import IntelliDocProject

logger = logging.getLogger(__name__)

class TemplateSerializer(serializers.Serializer):
    """Serializer for folder-based templates with complete configuration"""
    
    id = serializers.CharField(read_only=True)
    template_type = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    icon_class = serializers.CharField(read_only=True)
    color_theme = serializers.CharField(read_only=True)
    analysis_focus = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    
    # Metadata fields
    version = serializers.CharField(read_only=True)
    author = serializers.CharField(read_only=True)
    created_date = serializers.CharField(read_only=True)
    
    # Feature flags
    features = serializers.DictField(read_only=True)
    
    # Enhanced template capabilities
    navigation_pages = serializers.ListField(read_only=True, required=False)
    processing_capabilities = serializers.DictField(read_only=True, required=False)
    total_pages = serializers.IntegerField(read_only=True, required=False)
    
    # Template status and health
    status = serializers.CharField(read_only=True, required=False)
    validation_results = serializers.DictField(read_only=True, required=False)

class TemplateConfigSerializer(serializers.Serializer):
    """Serializer for detailed template configuration"""
    
    # Basic configuration
    name = serializers.CharField(max_length=200)
    description = serializers.CharField()
    version = serializers.CharField(max_length=50, required=False, default='1.0.0')
    author = serializers.CharField(max_length=100, required=False)
    
    # Template properties
    template_type = serializers.CharField(max_length=100)
    icon_class = serializers.CharField(max_length=100, required=False)
    color_theme = serializers.CharField(max_length=50, required=False)
    analysis_focus = serializers.CharField(required=False)
    
    # Advanced configuration
    navigation_pages = serializers.ListField(required=False, default=list)
    processing_capabilities = serializers.DictField(required=False, default=dict)
    features = serializers.DictField(required=False, default=dict)
    
    # UI configuration
    ui_configuration = serializers.DictField(required=False, default=dict)
    validation_rules = serializers.DictField(required=False, default=dict)
    
    def validate_template_type(self, value):
        """Validate template type"""
        allowed_types = [
            'aicc-intellidoc', 'legal', 'medical', 'history', 
            'custom', 'research', 'analysis'
        ]
        if value not in allowed_types:
            logger.warning(f"Unusual template type provided: {value}")
        return value
    
    def validate_version(self, value):
        """Validate version format"""
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', value):
            raise serializers.ValidationError("Version must be in format X.Y.Z")
        return value

class TemplateDuplicationSerializer(serializers.Serializer):
    """Serializer for template duplication requests"""
    
    # Source template (required)
    source_template = serializers.CharField(
        max_length=100,
        help_text="Source template ID to duplicate from"
    )
    
    # New template details (all required)
    new_template_id = serializers.CharField(
        max_length=100,
        help_text="Unique identifier for the new template (kebab-case recommended)"
    )
    
    new_name = serializers.CharField(
        max_length=200,
        help_text="Display name for the new template"
    )
    
    new_description = serializers.CharField(
        help_text="Description for the new template"
    )
    
    version = serializers.CharField(
        max_length=50,
        default='1.0.0',
        help_text="Version for the new template (X.Y.Z format)"
    )
    
    author = serializers.CharField(
        max_length=100,
        help_text="Author of the new template"
    )
    
    def validate_new_template_id(self, value):
        """Validate new template ID format and uniqueness"""
        import re
        from pathlib import Path
        from django.conf import settings
        
        # Check format (kebab-case recommended)
        if not re.match(r'^[a-z][a-z0-9-]*$', value):
            raise serializers.ValidationError(
                "Template ID must start with a letter and contain only lowercase letters, numbers, and hyphens"
            )
        
        # Check uniqueness
        templates_root = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
        target_path = templates_root / value
        
        if target_path.exists():
            raise serializers.ValidationError(
                f"Template with ID '{value}' already exists"
            )
        
        return value
    
    def validate_source_template(self, value):
        """Validate source template exists"""
        from pathlib import Path
        from django.conf import settings
        
        templates_root = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
        source_path = templates_root / value
        
        if not source_path.exists():
            raise serializers.ValidationError(
                f"Source template '{value}' not found"
            )
        
        return value
    
    def validate_version(self, value):
        """Validate version format"""
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', value):
            raise serializers.ValidationError("Version must be in format X.Y.Z")
        return value

class TemplateDuplicationResultSerializer(serializers.Serializer):
    """Serializer for template duplication results"""
    
    # Basic duplication info
    source_template = serializers.CharField(read_only=True)
    new_template = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(
        choices=['in_progress', 'completed', 'failed', 'rolled_back'],
        read_only=True
    )
    
    # Detailed results
    backend_results = serializers.DictField(read_only=True)
    frontend_results = serializers.DictField(read_only=True)
    integration_results = serializers.DictField(read_only=True)
    verification_results = serializers.DictField(read_only=True)
    
    # Error handling
    errors = serializers.ListField(read_only=True)
    warnings = serializers.ListField(read_only=True)
    
    # Timestamps
    started_at = serializers.DateTimeField(read_only=True, required=False)
    completed_at = serializers.DateTimeField(read_only=True, required=False)
    duration_seconds = serializers.FloatField(read_only=True, required=False)
    
    # Post-duplication info
    new_template_endpoints = serializers.DictField(read_only=True, required=False)
    next_steps = serializers.ListField(read_only=True, required=False)

class EnhancedIntelliDocProjectSerializer(serializers.ModelSerializer):
    """Enhanced serializer for IntelliDoc projects with template independence"""
    
    # Template information (cloned data)
    template_name = serializers.CharField(read_only=True)
    template_type = serializers.CharField(read_only=True)
    analysis_focus = serializers.CharField(read_only=True)
    
    # Navigation and UI (cloned data)
    navigation_pages = serializers.JSONField(read_only=True)
    total_pages = serializers.IntegerField(read_only=True)
    has_navigation = serializers.BooleanField(read_only=True)
    
    # Processing capabilities (cloned data)
    processing_capabilities = serializers.JSONField(read_only=True)
    ui_configuration = serializers.JSONField(read_only=True)
    validation_rules = serializers.JSONField(read_only=True)
    
    # Project-specific data
    documents_count = serializers.SerializerMethodField()
    processing_status = serializers.SerializerMethodField()
    
    # CRITICAL: No template object references
    # All data comes from cloned fields in the project model
    
    class Meta:
        model = IntelliDocProject
        fields = [
            'id', 'name', 'description', 'created_at', 'updated_at',
            'template_name', 'template_type', 'analysis_focus',
            'navigation_pages', 'total_pages', 'has_navigation',
            'processing_capabilities', 'ui_configuration', 'validation_rules',
            'documents_count', 'processing_status', 
            'instructions', 'suggested_questions'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'template_name', 'template_type'
        ]
    
    def get_documents_count(self, obj):
        """Get count of documents for this project"""
        # This would integrate with document management system
        return 0  # Placeholder
    
    def get_processing_status(self, obj):
        """Get processing status for this project"""
        # This would integrate with processing system
        return 'ready'  # Placeholder
