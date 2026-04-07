"""
Workflow Deployment Models
Models for deploying agent workflows as public-facing chatbots
"""
import uuid
from django.db import models
from django.utils import timezone
from users.models import IntelliDocProject, AgentWorkflow, User


class WorkflowDeploymentStatus(models.TextChoices):
    """Status choices for workflow deployments"""
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'


class WorkflowDeployment(models.Model):
    """Deployment configuration for a workflow as a public chatbot"""
    # Core identification
    project = models.ForeignKey(
        IntelliDocProject,
        on_delete=models.CASCADE,
        related_name='workflow_deployments'
    )
    workflow = models.ForeignKey(
        AgentWorkflow,
        on_delete=models.CASCADE,
        related_name='deployments',
        help_text='The workflow being deployed',
        null=True,
        blank=True
    )
    
    # Deployment configuration
    is_active = models.BooleanField(
        default=False,
        help_text='Whether the deployment is currently active'
    )
    endpoint_path = models.CharField(
        max_length=200,
        editable=False,
        help_text='Auto-generated endpoint path'
    )
    rate_limit_per_minute = models.IntegerField(
        default=10,
        help_text='Default rate limit per minute for origins without specific limits'
    )
    initial_greeting = models.CharField(
        max_length=500,
        default='Hi! I am your AI assistant.',
        help_text='Initial greeting message shown by the embedded chatbot'
    )
    
    # Chatbot branding customization
    chatbot_title = models.CharField(
        max_length=100,
        default='AI Assistant',
        help_text='Title displayed in the chatbot header'
    )
    chatbot_subtitle = models.CharField(
        max_length=200,
        default='Powered by AICC IntelliDoc',
        help_text='Subtitle displayed below the chatbot title'
    )
    primary_color = models.CharField(
        max_length=7,
        default='#ffffff',
        help_text='Primary color for header and user messages (hex format)'
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#ffffff',
        help_text='Secondary color for gradient effects (hex format)'
    )
    font_color = models.CharField(
        max_length=7,
        default='#000000',
        help_text='Font color for chatbot text (hex format)'
    )
    logo_url = models.URLField(
        blank=True,
        null=True,
        help_text='Optional URL to a logo image displayed in the header'
    )
    file_uploads_enabled = models.BooleanField(
        default=False,
        help_text='Whether end-users can upload files in the chatbot'
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_deployments'
    )
    
    class Meta:
        ordering = ['-updated_at']
        # Ensure only one active deployment per project
        constraints = [
            models.UniqueConstraint(
                fields=['project'],
                condition=models.Q(is_active=True),
                name='unique_active_deployment_per_project'
            )
        ]
        indexes = [
            models.Index(fields=['project', 'is_active']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        workflow_name = self.workflow.name if self.workflow else "No workflow"
        return f"{self.project.name} - {workflow_name} ({status})"
    
    def save(self, *args, **kwargs):
        """Auto-generate endpoint path on save"""
        if not self.endpoint_path:
            self.endpoint_path = f"/api/workflow-deploy/{self.project.project_id}/"
        super().save(*args, **kwargs)
    
    @property
    def endpoint_url(self):
        """Get full endpoint URL"""
        # This will be constructed based on the actual domain in views
        return self.endpoint_path


class WorkflowAllowedOrigin(models.Model):
    """Allowed origins (domains) for a workflow deployment"""
    deployment = models.ForeignKey(
        WorkflowDeployment,
        on_delete=models.CASCADE,
        related_name='allowed_origins'
    )
    origin = models.CharField(
        max_length=500,
        help_text='Allowed origin (e.g., https://example.com)'
    )
    rate_limit_per_minute = models.IntegerField(
        default=10,
        help_text='Rate limit per minute for this specific origin'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this origin is currently allowed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['origin']
        unique_together = ['deployment', 'origin']
        indexes = [
            models.Index(fields=['deployment', 'is_active']),
            models.Index(fields=['origin']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.deployment.project.name} - {self.origin} ({status})"


class WorkflowDeploymentRequestStatus(models.TextChoices):
    """Status choices for deployment requests"""
    SUCCESS = 'success', 'Success'
    ERROR = 'error', 'Error'
    RATE_LIMITED = 'rate_limited', 'Rate Limited'
    BLOCKED = 'blocked', 'Blocked'
    CORS_DENIED = 'cors_denied', 'CORS Denied'


class WorkflowDeploymentRequest(models.Model):
    """Track all requests to deployed workflows"""
    deployment = models.ForeignKey(
        WorkflowDeployment,
        on_delete=models.CASCADE,
        related_name='requests'
    )
    origin = models.CharField(
        max_length=500,
        help_text='Origin of the request'
    )
    request_id = models.CharField(
        max_length=100,
        unique=True,
        help_text='Unique request identifier'
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Optional session ID for conversation tracking'
    )
    message_preview = models.CharField(
        max_length=100,
        blank=True,
        help_text='Privacy-safe truncated message (first 100 chars)'
    )
    response_generated = models.BooleanField(
        default=False,
        help_text='Whether a response was successfully generated'
    )
    status = models.CharField(
        max_length=20,
        choices=WorkflowDeploymentRequestStatus.choices,
        default=WorkflowDeploymentRequestStatus.SUCCESS
    )
    execution_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text='Workflow execution time in milliseconds'
    )
    error_message = models.TextField(
        blank=True,
        help_text='Error message if request failed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deployment', 'created_at']),
            models.Index(fields=['origin', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['session_id', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.deployment.project.name} - {self.request_id[:8]} ({self.status})"


class DeploymentSession(models.Model):
    """Stores session state and conversation history for deployed chatbots"""
    deployment = models.ForeignKey(
        WorkflowDeployment,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_id = models.CharField(
        max_length=100,
        help_text='Unique session identifier from client'
    )
    conversation_history = models.JSONField(
        default=list,
        help_text='Full conversation history as list of messages: [{"role": "user|assistant", "content": "..."}, ...]'
    )
    message_count = models.IntegerField(
        default=0,
        help_text='Total number of messages in this session'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this session is currently active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text='Last time a message was added to this session'
    )
    
    # Human input tracking for UserProxyAgent in deployment context
    awaiting_human_input = models.BooleanField(
        default=False,
        help_text='Whether this session is awaiting human input from UserProxyAgent'
    )
    paused_execution_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='WorkflowExecution ID of the paused execution'
    )
    human_input_prompt = models.TextField(
        blank=True,
        help_text='Last conversation message to display when requesting human input'
    )
    human_input_agent_name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Name of the UserProxyAgent awaiting input'
    )
    human_input_agent_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Node ID of the UserProxyAgent awaiting input'
    )
    
    class Meta:
        ordering = ['-last_activity']
        unique_together = ['deployment', 'session_id']
        indexes = [
            models.Index(fields=['deployment', 'session_id']),
            models.Index(fields=['deployment', 'last_activity']),
            models.Index(fields=['is_active', 'last_activity']),
        ]
    
    def __str__(self):
        return f"Session {self.session_id[:8]} for {self.deployment.project.name} ({self.message_count} messages)"


class DeploymentSessionFile(models.Model):
    """Files uploaded by end-users during a deployment chatbot session"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        DeploymentSession,
        on_delete=models.CASCADE,
        related_name='uploaded_files',
    )
    filename = models.CharField(max_length=255)
    file_extension = models.CharField(max_length=20)
    mime_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    storage_path = models.CharField(max_length=500, help_text='Path in default_storage')
    provider = models.CharField(max_length=20, help_text='LLM provider the file was uploaded to')
    provider_file_id = models.CharField(max_length=500, blank=True, default='', help_text='File ID from the LLM provider API')
    extracted_text = models.TextField(blank=True, default='', help_text='Extracted text for file types not supported by provider File API')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.filename} ({self.provider}) — session {self.session.session_id[:8]}"


class DeploymentExecution(models.Model):
    """Track individual executions within a deployment session"""
    execution_id = models.CharField(
        max_length=100,
        unique=True,
        help_text='Unique execution identifier'
    )
    deployment_session = models.ForeignKey(
        DeploymentSession,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    workflow_execution = models.ForeignKey(
        'users.WorkflowExecution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deployment_executions',
        help_text='Reference to underlying WorkflowExecution record'
    )
    user_query = models.TextField(
        help_text='The user query that triggered this execution'
    )
    assistant_response = models.TextField(
        help_text='The assistant response from the workflow'
    )
    execution_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text='Execution time in milliseconds'
    )
    status = models.CharField(
        max_length=20,
        choices=WorkflowDeploymentRequestStatus.choices,
        default=WorkflowDeploymentRequestStatus.SUCCESS,
        help_text='Execution status'
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text='Error message if execution failed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deployment_session', 'created_at']),
            models.Index(fields=['execution_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Execution {self.execution_id[:8]} for session {self.deployment_session.session_id[:8]}"


class ChatbotSession(models.Model):
    """In-app chatbot conversation session."""
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    project = models.ForeignKey('users.IntelliDocProject', on_delete=models.CASCADE, related_name='chatbot_sessions')
    workflow_id = models.CharField(max_length=200, null=True, blank=True)  # UUID string of AgentWorkflow
    label = models.CharField(max_length=200, default='New Conversation')
    conversation_history = models.JSONField(default=list)
    message_count = models.IntegerField(default=0)
    preview = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"ChatbotSession {self.session_id} - {self.label}"

