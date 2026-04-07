# backend/api/serializers.py

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from users.models import (
    DashboardIcon, UserIconPermission, GroupIconPermission, IconClass, ColorTheme, 
    IntelliDocProject, ProjectDocument, DocumentChunk, DocumentVectorStatus,
    UserProjectPermission, GroupProjectPermission
)
from templates.discovery import TemplateDiscoverySystem
from .template_cloning_utils import clone_template_configuration

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class UserCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'password2', 'first_name', 'last_name']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    uid = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})
        return attrs

class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for authenticated users to change their password"""
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    
    def validate_current_password(self, value):
        """Validate that the current password is correct"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
    
    def validate_new_password(self, value):
        """Additional validation for new password"""
        user = self.context['request'].user
        
        # Check if new password is different from current password
        if user.check_password(value):
            raise serializers.ValidationError("New password cannot be the same as current password.")
        
        return value
    
    def save(self):
        """Change the user's password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user

class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role', 'is_active']
        read_only_fields = ['email']

class DashboardIconSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardIcon
        fields = ['id', 'name', 'description', 'icon_class', 'color', 'route', 'order', 'is_active']

class IconChoicesSerializer(serializers.Serializer):
    """Serializer to provide available icon and color choices for the frontend"""
    icon_choices = serializers.SerializerMethodField()
    color_choices = serializers.SerializerMethodField()
    
    def get_icon_choices(self, obj):
        """Return all available icon choices"""
        return [{'value': choice[0], 'label': choice[1]} for choice in IconClass.choices]
    
    def get_color_choices(self, obj):
        """Return all available color choices"""
        return [{'value': choice[0], 'label': choice[1]} for choice in ColorTheme.choices]

class UserIconPermissionSerializer(serializers.ModelSerializer):
    icon_name = serializers.ReadOnlyField(source='icon.name')
    user_email = serializers.ReadOnlyField(source='user.email')
    
    class Meta:
        model = UserIconPermission
        fields = ['id', 'user', 'icon', 'icon_name', 'user_email', 'granted_at']
        read_only_fields = ['granted_at']

class IconPermissionBulkUpdateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    icon_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']

class GroupIconPermissionSerializer(serializers.ModelSerializer):
    icon_name = serializers.ReadOnlyField(source='icon.name')
    group_name = serializers.ReadOnlyField(source='group.name')
    
    class Meta:
        model = GroupIconPermission
        fields = ['id', 'group', 'icon', 'icon_name', 'group_name', 'granted_at']
        read_only_fields = ['granted_at']

class GroupIconPermissionBulkUpdateSerializer(serializers.Serializer):
    group_id = serializers.IntegerField(required=True)
    icon_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )


class ProjectDocumentSerializer(serializers.ModelSerializer):
    document_id = serializers.UUIDField(read_only=True)
    uploaded_by = UserSerializer(read_only=True)
    file_size_formatted = serializers.ReadOnlyField()
    download_url = serializers.SerializerMethodField()
    llm_upload_status = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectDocument
        fields = [
            'id', 'document_id', 'original_filename', 'file_size', 'file_size_formatted',
            'file_type', 'file_extension', 'upload_status', 'uploaded_by', 'uploaded_at',
            'download_url', 'llm_upload_status'
        ]
        read_only_fields = ['id', 'document_id', 'uploaded_by', 'uploaded_at']
    
    def get_download_url(self, obj):
        """Generate the download URL for the document"""
        if obj.project and obj.document_id:
            return f'/api/projects/{obj.project.project_id}/documents/{obj.document_id}/download/'
        return None
    
    def get_llm_upload_status(self, obj):
        """
        Return per-provider upload status so the frontend can show
        which documents are ready for which LLM provider.
        """
        return {
            'openai': bool(getattr(obj, 'llm_file_id_openai', None)),
            'anthropic': bool(getattr(obj, 'llm_file_id_anthropic', None)),
            'google': bool(getattr(obj, 'llm_file_id_google', None)),
        }


class DocumentVectorStatusSerializer(serializers.ModelSerializer):
    document = ProjectDocumentSerializer(read_only=True)
    processing_progress = serializers.ReadOnlyField()
    
    class Meta:
        model = DocumentVectorStatus
        fields = [
            'id', 'document', 'status', 'vector_id', 'content_length', 'embedding_dimension',
            'processing_time_ms', 'error_message', 'processed_at', 'created_at', 'updated_at',
            # Summary and Topic tracking
            'summary_generated', 'summary_generated_at', 'summary_chunks_count',
            'summarizer_used', 'processing_progress'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'processing_progress']


class DocumentChunkSerializer(serializers.ModelSerializer):
    document = ProjectDocumentSerializer(read_only=True)
    has_ai_generated_content = serializers.ReadOnlyField()
    ai_processing_status = serializers.ReadOnlyField()
    
    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'chunk_id', 'chunk_index', 'chunk_type', 'section_title',
            'content_length', 'has_embedding', 'vector_id',
            # Metadata
            'document', 'created_at', 'updated_at',
            # Computed properties
            'has_ai_generated_content', 'ai_processing_status'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'has_ai_generated_content', 'ai_processing_status']


class DocumentChunkSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for chunk summary data"""
    class Meta:
        model = DocumentChunk
        fields = [
            'chunk_id', 'chunk_index', 'section_title'
        ]


class ProjectTemplateSerializer(serializers.Serializer):
    """Serializer for folder-based template discovery"""
    id = serializers.CharField()
    template_type = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    icon_class = serializers.CharField()
    color_theme = serializers.CharField()
    source = serializers.CharField()
    version = serializers.CharField(required=False)
    author = serializers.CharField(required=False)
    features = serializers.DictField(required=False)


class TemplateConfigurationSerializer(serializers.Serializer):
    """Serializer for complete template configuration"""
    template_id = serializers.CharField()
    name = serializers.CharField()
    template_type = serializers.CharField()
    description = serializers.CharField()
    instructions = serializers.CharField()
    suggested_questions = serializers.ListField(child=serializers.CharField())
    required_fields = serializers.ListField(child=serializers.CharField())
    analysis_focus = serializers.CharField()
    icon_class = serializers.CharField()
    color_theme = serializers.CharField()
    has_navigation = serializers.BooleanField()
    total_pages = serializers.IntegerField()
    navigation_pages = serializers.ListField(child=serializers.DictField())
    processing_capabilities = serializers.DictField()
    validation_rules = serializers.DictField()
    ui_configuration = serializers.DictField()


class TemplateDuplicationSerializer(serializers.Serializer):
    """Serializer for template duplication requests"""
    source_template = serializers.CharField(required=True)
    new_template_id = serializers.CharField(required=True)
    new_name = serializers.CharField(required=False)
    new_description = serializers.CharField(required=False)
    new_author = serializers.CharField(required=False)


class IntelliDocProjectSerializer(serializers.ModelSerializer):
    """Serializer for IntelliDoc projects.

    Template config (navigation_pages, processing_capabilities, etc.) is injected
    at read time from the template definition if the project doesn't have its own
    stored copy. This replaces the old deep-copy-at-creation approach.
    """
    project_id = serializers.UUIDField(read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = IntelliDocProject
        fields = [
            'id', 'project_id', 'name', 'description', 'has_navigation',
            'template_name', 'template_type', 'template_version', 'template_description', 'instructions',
            'suggested_questions', 'required_fields', 'analysis_focus', 'icon_class', 'color_theme',
            'total_pages', 'navigation_pages', 'processing_capabilities', 'validation_rules', 'ui_configuration',
            'preserve_original_folder_structure',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'project_id', 'created_by', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Inject template config at read time if project has empty fields
        config_fields = ['navigation_pages', 'processing_capabilities', 'validation_rules', 'ui_configuration']
        needs_inject = any(not data.get(f) for f in config_fields)
        if needs_inject and data.get('template_type'):
            try:
                from templates.discovery import TemplateDiscoverySystem
                tpl = TemplateDiscoverySystem.get_template_configuration(data['template_type'])
                if tpl:
                    cfg = tpl.get('configuration', {})
                    for field in config_fields:
                        if not data.get(field):
                            data[field] = cfg.get(field, [] if field == 'navigation_pages' else {})
                    if not data.get('has_navigation') and cfg.get('has_navigation'):
                        data['has_navigation'] = cfg['has_navigation']
                    if (not data.get('total_pages') or data['total_pages'] <= 1) and cfg.get('total_pages'):
                        data['total_pages'] = cfg['total_pages']
                    if not data.get('instructions') and cfg.get('instructions'):
                        data['instructions'] = cfg['instructions']
            except Exception:
                pass  # If template lookup fails, return stored data as-is
        return data


class IntelliDocProjectCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating IntelliDoc projects with template system"""
    template_id = serializers.CharField(required=True)
    
    class Meta:
        model = IntelliDocProject
        fields = ['name', 'description', 'template_id']
        
    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Project name cannot be empty.")
        return value.strip()
    
    def validate_description(self, value):
        if not value.strip():
            raise serializers.ValidationError("Project description is required.")
        return value.strip()
    
    def validate_template_id(self, value):
        # Use folder-based template discovery
        template_config = TemplateDiscoverySystem.get_template_configuration(value)
        if not template_config:
            raise serializers.ValidationError("Invalid template selected.")
        return value
    
    def create(self, validated_data):
        template_id = validated_data.pop('template_id')
        
        # Get complete template configuration from folder
        template_config = TemplateDiscoverySystem.get_template_configuration(template_id)
        if not template_config:
            raise serializers.ValidationError("Template configuration not found.")
        
        # Extract configuration data
        config = template_config.get('configuration', {})
        metadata = template_config.get('metadata', {})
        
        # Clone COMPLETE template configuration with deep copy
        cloned_config, _ = clone_template_configuration(
            config,
            metadata,
            include_audit_trail=False
        )
        
        # Extract template version
        template_version = metadata.get('version', '1.0.0')
        
        # Clone COMPLETE template configuration into the project
        project = IntelliDocProject.objects.create(
            # Project data
            name=validated_data['name'],
            description=validated_data['description'],
            created_by=validated_data['created_by'],
            
            # Cloned basic template data
            template_name=cloned_config.get('name', metadata.get('name')),
            template_type=cloned_config.get('template_type', metadata.get('template_type')),
            template_version=template_version,
            template_description=cloned_config.get('description', metadata.get('description')),
            instructions=cloned_config.get('instructions', ''),
            suggested_questions=cloned_config.get('suggested_questions', []),
            required_fields=cloned_config.get('required_fields', []),
            analysis_focus=cloned_config.get('analysis_focus', ''),
            icon_class=cloned_config.get('icon_class', metadata.get('ui_assets', {}).get('icon', 'fa-file-alt')),
            color_theme=cloned_config.get('color_theme', metadata.get('color_theme', 'oxford-blue')),
            has_navigation=cloned_config.get('total_pages', 1) > 1,
            
            # Complete configuration cloning (deep copied)
            total_pages=cloned_config.get('total_pages', 1),
            navigation_pages=cloned_config.get('navigation_pages', []),
            processing_capabilities=cloned_config.get('processing_capabilities', {}),
            validation_rules=cloned_config.get('validation_rules', {}),
            ui_configuration=cloned_config.get('ui_configuration', {})
        )
        return project

# ============================================================================
# PROJECT PERMISSION SERIALIZERS
# ============================================================================

class UserProjectPermissionSerializer(serializers.ModelSerializer):
    project_name = serializers.ReadOnlyField(source='project.name')
    user_email = serializers.ReadOnlyField(source='user.email')
    user_name = serializers.ReadOnlyField(source='user.get_full_name')
    
    class Meta:
        model = UserProjectPermission
        fields = ['id', 'user', 'project', 'project_name', 'user_email', 'user_name', 'granted_at']
        read_only_fields = ['granted_at']

class GroupProjectPermissionSerializer(serializers.ModelSerializer):
    project_name = serializers.ReadOnlyField(source='project.name')
    group_name = serializers.ReadOnlyField(source='group.name')
    
    class Meta:
        model = GroupProjectPermission
        fields = ['id', 'group', 'project', 'project_name', 'group_name', 'granted_at']
        read_only_fields = ['granted_at']

class ProjectPermissionBulkUpdateSerializer(serializers.Serializer):
    project_id = serializers.UUIDField(required=True)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )

class ProjectAssignmentSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    project_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True
    )
