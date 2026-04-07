# backend/project_api_keys/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from users.models import ProjectAPIKey

@admin.register(ProjectAPIKey)
class ProjectAPIKeyAdmin(admin.ModelAdmin):
    """Admin interface for project-specific API keys"""
    
    list_display = [
        'project_name', 'provider_display', 'key_display', 
        'status_badge', 'validation_badge', 'usage_stats',
        'created_by_name', 'created_at'
    ]
    
    list_filter = [
        'provider_type', 'is_active', 'is_validated', 
        'created_at', 'last_validated_at'
    ]
    
    search_fields = [
        'project__name', 'key_name', 'created_by__email',
        'created_by__first_name', 'created_by__last_name'
    ]
    
    readonly_fields = [
        'project', 'provider_type', 'encrypted_api_key', 
        'is_validated', 'validation_error', 'last_validated_at',
        'usage_count', 'last_used_at', 'created_by', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Project Information', {
            'fields': ('project', 'provider_type', 'key_name')
        }),
        ('API Key', {
            'fields': ('encrypted_api_key',),
            'classes': ('collapse',),
            'description': 'Encrypted API key data (read-only for security)'
        }),
        ('Status & Validation', {
            'fields': (
                'is_active', 'is_validated', 'validation_error', 
                'last_validated_at'
            )
        }),
        ('Usage Statistics', {
            'fields': ('usage_count', 'last_used_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def project_name(self, obj):
        """Display project name with link"""
        if obj.project:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:users_intellidocproject_change', args=[obj.project.pk]),
                obj.project.name
            )
        return '-'
    project_name.short_description = 'Project'
    
    def provider_display(self, obj):
        """Display provider with icon"""
        provider_info = obj.get_provider_display_info()
        return format_html(
            '<i class="{}"></i> {}',
            provider_info['icon'],
            provider_info['name']
        )
    provider_display.short_description = 'Provider'
    
    def key_display(self, obj):
        """Display masked key"""
        if obj.key_name:
            return f"{obj.key_name} ({obj.masked_key})"
        return obj.masked_key
    key_display.short_description = 'API Key'
    
    def status_badge(self, obj):
        """Display status with color badge"""
        if obj.is_active:
            color = 'green'
            text = 'Active'
        else:
            color = 'red'
            text = 'Inactive'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    status_badge.short_description = 'Status'
    
    def validation_badge(self, obj):
        """Display validation status with badge"""
        if not obj.is_active:
            return format_html('<span style="color: gray;">N/A</span>')
        
        if obj.is_validated:
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Valid</span>'
            )
        elif obj.validation_error:
            return format_html(
                '<span style="color: red; font-weight: bold;" title="{}">❌ Failed</span>',
                obj.validation_error
            )
        else:
            return format_html('<span style="color: orange;">⏳ Not Validated</span>')
    validation_badge.short_description = 'Validation'
    
    def usage_stats(self, obj):
        """Display usage statistics"""
        if obj.usage_count == 0:
            return format_html('<span style="color: gray;">Never used</span>')
        
        return format_html(
            '<strong>{}</strong> uses<br/><small>Last: {}</small>',
            obj.usage_count,
            obj.last_used_at.strftime('%m/%d %H:%M') if obj.last_used_at else 'Unknown'
        )
    usage_stats.short_description = 'Usage'
    
    def created_by_name(self, obj):
        """Display creator name with link"""
        if obj.created_by:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:users_user_change', args=[obj.created_by.pk]),
                obj.created_by.get_full_name() or obj.created_by.email
            )
        return '-'
    created_by_name.short_description = 'Created By'
    
    def has_add_permission(self, request):
        """Disable add permission - keys should be added through API"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Only allow superusers to change API keys"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Only allow superusers to delete API keys"""
        return request.user.is_superuser
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'project', 'created_by'
        )
    
    class Media:
        css = {
            'all': ('admin/css/project_api_keys.css',)
        }
