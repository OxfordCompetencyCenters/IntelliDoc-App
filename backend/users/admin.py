# users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import (
    User, DashboardIcon, UserIconPermission, GroupIconPermission,
    LLMProvider, APIKeyConfig, LLMComparison, LLMResponse, ProjectAPIKey
)

# Import the admin configuration for ProjectAPIKey
from project_api_keys.admin import ProjectAPIKeyAdmin

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'role')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {'fields': ('role', 'is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_active', 'is_staff'),
        }),
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)


@admin.register(DashboardIcon)
class DashboardIconAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_icon_preview', 'color', 'route', 'order', 'is_active')
    list_filter = ('is_active', 'color', 'icon_class')
    search_fields = ('name', 'description')
    ordering = ('order', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Visual Appearance', {
            'fields': ('icon_class', 'color'),
            'description': 'Choose from predefined FontAwesome icons and Oxford University color themes'
        }),
        ('Navigation', {
            'fields': ('route', 'order'),
            'description': 'Define where this icon leads and its display order'
        })
    )
    
    class Media:
        css = {
            'all': (
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
            )
        }
    
    def get_icon_preview(self, obj):
        """Display a visual preview of the icon"""
        from django.utils.safestring import mark_safe
        
        # Map color theme values to actual hex colors for admin display
        color_hex_map = {
            'oxford-blue': '#002147',
            'oxford-blue-light': '#334e68',
            'oxford-blue-dark': '#001122',
            'academic-gold': '#FFD700',
            'antique-gold': '#CD7F32',
            'burgundy': '#800020',
            'forest-green': '#228B22',
            'royal-purple': '#663399',
            'crimson': '#DC143C',
            'charcoal': '#36454F',
            'slate': '#708090',
            'pearl': '#F8F8FF',
            'cream': '#F5F5DC',
            'success': '#10B981',
            'warning': '#F59E0B',
            'error': '#EF4444',
            'info': '#3B82F6',
            'emerald': '#50C878',
            'sapphire': '#0F52BA',
            'ruby': '#E0115F',
            'amber': '#FFBF00',
            'teal': '#008080',
            'indigo': '#4B0082',
            'coral': '#FF7F50',
            'mint': '#98FB98',
        }
        
        color_hex = color_hex_map.get(obj.color, '#002147')  # Default to Oxford blue
        
        return mark_safe(
            f'<i class="fas {obj.icon_class}" style="color: {color_hex}; font-size: 16px; margin-right: 8px;"></i>'
            f'<span style="font-family: monospace; color: #666;">{obj.icon_class}</span>'
        )
    get_icon_preview.short_description = 'Icon Preview'


@admin.register(UserIconPermission)
class UserIconPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'icon', 'granted_at', 'granted_by')
    list_filter = ('granted_at', 'icon')
    search_fields = ('user__email', 'icon__name')
    ordering = ('-granted_at',)


@admin.register(GroupIconPermission)
class GroupIconPermissionAdmin(admin.ModelAdmin):
    list_display = ('group', 'icon', 'granted_at', 'granted_by')
    list_filter = ('granted_at', 'icon')
    search_fields = ('group__name', 'icon__name')
    ordering = ('-granted_at',)


# LLM Eval Admin - Only Essential Models
@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'max_tokens', 'timeout_seconds', 'is_active')
    list_filter = ('provider_type', 'is_active')
    search_fields = ('name',)
    ordering = ('name',)
    
    fieldsets = (
        ('Provider Information', {
            'fields': ('name', 'provider_type', 'is_active')
        }),
        ('API Configuration', {
            'fields': ('api_endpoint', 'max_tokens', 'timeout_seconds'),
            'description': 'Models will be fetched dynamically from the provider API'
        })
    )


@admin.register(APIKeyConfig)
class APIKeyConfigAdmin(admin.ModelAdmin):
    list_display = ('provider', 'key_name', 'usage_limit_daily', 'usage_count_today', 'is_active', 'created_by')
    list_filter = ('provider', 'is_active', 'created_at')
    search_fields = ('key_name', 'provider__name')
    ordering = ('provider', 'key_name')
    readonly_fields = ('usage_count_today', 'last_reset_date', 'created_by', 'created_at')
    
    fieldsets = (
        ('Provider Information', {
            'fields': ('provider', 'key_name', 'is_active')
        }),
        ('API Key', {
            'fields': ('api_key',),
            'description': 'API key will be encrypted when saved'
        }),
        ('Usage Controls', {
            'fields': ('usage_limit_daily', 'usage_count_today', 'last_reset_date')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Note: LLMComparison and LLMResponse are viewable through the frontend
# No need to clutter Django admin with them
