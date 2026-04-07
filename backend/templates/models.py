# templates/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

# Template Operation Models for Security and Concurrency
class TemplateOperationType(models.TextChoices):
    DUPLICATE = 'duplicate', 'Duplicate Template'
    DELETE = 'delete', 'Delete Template'
    VALIDATE = 'validate', 'Validate Template'
    DISCOVER = 'discover', 'Discover Templates'
    SYNC = 'sync', 'Sync Templates'

class TemplateOperationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'

class TemplateOperation(models.Model):
    """Track template operations for concurrency management"""
    operation_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    operation_type = models.CharField(max_length=20, choices=TemplateOperationType.choices)
    template_id = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=TemplateOperationStatus.choices, default=TemplateOperationStatus.PENDING)
    
    # Operation details
    details = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # Concurrency control
    lock_key = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['operation_type', 'template_id']),
            models.Index(fields=['status']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"{self.operation_type} - {self.template_id} ({self.status})"
    
    def mark_completed(self, result: dict = None, error_message: str = None):
        """Mark operation as completed"""
        self.completed_at = timezone.now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        
        if error_message:
            self.status = TemplateOperationStatus.FAILED
            self.error_message = error_message
        else:
            self.status = TemplateOperationStatus.COMPLETED
            self.result = result or {}
        
        self.save()
