# templates/admin.py

from django.contrib import admin
from .models import TemplateOperation


@admin.register(TemplateOperation)
class TemplateOperationAdmin(admin.ModelAdmin):
    """Admin configuration for TemplateOperation"""
    
    list_display = [
        'operation_type', 'template_id', 'user', 'status', 
        'duration_seconds', 'started_at'
    ]
    list_filter = ['operation_type', 'status', 'started_at']
    search_fields = ['template_id', 'user__email', 'operation_type']
    readonly_fields = ['operation_id', 'started_at', 'completed_at', 'duration_seconds']
    
    fieldsets = (
        ('Operation Details', {
            'fields': ('operation_id', 'operation_type', 'template_id', 'user', 'status')
        }),
        ('Results', {
            'fields': ('details', 'result', 'error_message')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'duration_seconds')
        }),
        ('Concurrency', {
            'fields': ('lock_key',),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Disable manual creation of operations"""
        return False
