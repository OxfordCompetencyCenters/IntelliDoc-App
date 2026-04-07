"""
Models for Public Chatbot API - Isolated tracking
ZERO impact on existing AI Catalogue models
"""
from django.db import models
from django.utils import timezone
from django.core.validators import MinLengthValidator, MaxLengthValidator
import uuid


class PublicChatRequest(models.Model):
    """
    Track public API requests - completely isolated from main system
    Uses separate tables, no foreign keys to existing models
    """
    # Unique request tracking
    request_id = models.CharField(max_length=50, unique=True, db_index=True)
    session_id = models.CharField(max_length=100, blank=True, db_index=True)  # For conversation tracking
    
    # Security and access tracking
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.CharField(max_length=300, blank=True)
    origin_domain = models.CharField(max_length=200, blank=True)  # CORS origin tracking
    
    # Request details (privacy-safe)
    message = models.TextField(
        blank=True,
        help_text="Full message content"
    )
    message_preview = models.CharField(
        max_length=100, 
        validators=[MinLengthValidator(1), MaxLengthValidator(100)],
        help_text="Truncated message for logging (first 100 chars)"
    )
    message_length = models.IntegerField(default=0)
    message_hash = models.CharField(max_length=64, blank=True)  # For duplicate detection
    
    # Response tracking
    response_generated = models.BooleanField(default=False)
    response_length = models.IntegerField(default=0)
    response_time_ms = models.IntegerField(null=True, blank=True)
    
    # ChromaDB specific metrics (isolated from Milvus)
    chroma_search_time_ms = models.IntegerField(null=True, blank=True)
    chroma_results_found = models.IntegerField(default=0)
    chroma_context_used = models.BooleanField(default=False)
    
    # LLM provider tracking (reuses existing infrastructure safely)
    llm_provider_used = models.CharField(max_length=50, blank=True)
    llm_model_used = models.CharField(max_length=100, blank=True)
    llm_tokens_used = models.IntegerField(default=0)
    llm_cost_estimate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
    # Status and error tracking
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('error', 'Error'),
        ('blocked', 'Blocked'),
        ('rate_limited', 'Rate Limited'),
        ('security_violation', 'Security Violation'),
    ], default='success')
    error_type = models.CharField(max_length=50, blank=True)
    error_message = models.CharField(max_length=200, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['session_id', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['llm_provider_used', 'created_at']),
            models.Index(fields=['origin_domain', 'created_at']),
        ]
        db_table = 'public_chatbot_requests'  # Explicit table name for isolation
    
    def __str__(self):
        return f"Request {self.request_id} from {self.ip_address} ({self.status})"

    def clean(self):
        """Validate model data"""
        from django.core.exceptions import ValidationError

        # Validate completion time is after creation time
        if self.completed_at and self.created_at:
            if self.completed_at < self.created_at:
                raise ValidationError("Completion time cannot be before creation time")

        # Validate message length is non-negative
        if self.message_length < 0:
            raise ValidationError("Message length cannot be negative")

        # Validate response length is non-negative
        if self.response_length < 0:
            raise ValidationError("Response length cannot be negative")
    
    def save(self, *args, **kwargs):
        """Auto-generate request_id and calculate response time"""
        if not self.request_id:
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            unique_suffix = str(uuid.uuid4().hex[:8])
            self.request_id = f"pub_{timestamp}_{unique_suffix}"

        # Calculate response time if completed - with validation
        if (self.completed_at and self.created_at and
            not self.response_time_ms and
            hasattr(self, 'created_at') and self.created_at):
            try:
                delta = self.completed_at - self.created_at
                self.response_time_ms = int(delta.total_seconds() * 1000)
            except (TypeError, AttributeError) as e:
                # Log warning but don't fail the save
                import logging
                logger = logging.getLogger('public_chatbot')
                logger.warning(f"Could not calculate response time for {self.request_id}: {e}")

        # Run validation before saving
        self.full_clean()

        super().save(*args, **kwargs)


class IPUsageLimit(models.Model):
    """
    Track IP-based usage limits - isolated from main user system
    Prevents abuse while allowing legitimate usage
    """
    ip_address = models.GenericIPAddressField(unique=True, db_index=True)
    
    # Daily limits and tracking
    daily_request_count = models.IntegerField(default=0)
    daily_token_usage = models.IntegerField(default=0)
    last_reset_date = models.DateField(default=timezone.now)
    
    # Rate limiting (per minute/hour)
    hourly_request_count = models.IntegerField(default=0)
    last_hourly_reset = models.DateTimeField(default=timezone.now)
    
    # Blocking and security
    is_blocked = models.BooleanField(default=False)
    blocked_until = models.DateTimeField(null=True, blank=True)
    block_reason = models.CharField(max_length=100, blank=True)
    
    # Tracking patterns
    total_requests = models.IntegerField(default=0)
    successful_requests = models.IntegerField(default=0)
    security_violations = models.IntegerField(default=0)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    # Geographic and metadata (for analysis)
    country_code = models.CharField(max_length=2, blank=True)  # Optional GeoIP
    user_agent_pattern = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['ip_address', 'is_blocked']),
            models.Index(fields=['last_reset_date', 'daily_request_count']),
            models.Index(fields=['blocked_until']),
        ]
        db_table = 'public_chatbot_ip_limits'  # Explicit table name for isolation
    
    def __str__(self):
        status = "BLOCKED" if self.is_blocked else "ACTIVE"
        return f"{self.ip_address} - {self.daily_request_count}/day ({status})"
    
    def reset_daily_counts(self):
        """Reset daily counters for new day"""
        self.daily_request_count = 0
        self.daily_token_usage = 0
        self.last_reset_date = timezone.now().date()
        self.save()
    
    def reset_hourly_count(self):
        """Reset hourly counter"""
        self.hourly_request_count = 0
        self.last_hourly_reset = timezone.now()
        self.save()
    
    def increment_usage(self, token_count: int = 0, success: bool = True):
        """Increment usage counters"""
        self.total_requests += 1
        self.daily_request_count += 1
        self.hourly_request_count += 1
        self.daily_token_usage += token_count
        self.last_seen = timezone.now()
        
        if success:
            self.successful_requests += 1
        
        # Auto-reset if needed
        current_date = timezone.now().date()
        if self.last_reset_date < current_date:
            self.reset_daily_counts()
        
        current_hour = timezone.now().replace(minute=0, second=0, microsecond=0)
        last_hour = self.last_hourly_reset.replace(minute=0, second=0, microsecond=0)
        if current_hour > last_hour:
            self.reset_hourly_count()
        
        self.save()
    
    def is_rate_limited(self) -> bool:
        """Check if IP is currently rate limited"""
        # Check if explicitly blocked
        if self.is_blocked and self.blocked_until and self.blocked_until > timezone.now():
            return True
        
        # Check daily limits (100 requests per day)
        if self.daily_request_count >= 100:
            return True
        
        # Check hourly limits (20 requests per hour)
        if self.hourly_request_count >= 20:
            return True
        
        return False


class PublicKnowledgeDocument(models.Model):
    """
    Admin-managed knowledge base documents for ChromaDB
    Completely separate from main document system
    """
    # Document identification
    document_id = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, default='general')
    subcategory = models.CharField(max_length=50, blank=True)
    
    # Content
    content = models.TextField(help_text="Full document content for ChromaDB")
    content_preview = models.CharField(max_length=300, blank=True)  # For admin display
    content_hash = models.CharField(max_length=64, blank=True)  # For duplicate detection
    
    # Admin approval workflow
    is_approved = models.BooleanField(default=False, help_text="Admin approved for public use")
    security_reviewed = models.BooleanField(default=False, help_text="Security review completed")
    quality_score = models.IntegerField(default=0, help_text="Content quality (0-100)")
    
    # ChromaDB sync status
    synced_to_chromadb = models.BooleanField(default=False)
    chromadb_id = models.CharField(max_length=100, blank=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True)
    
    # Usage tracking
    search_count = models.IntegerField(default=0)  # How often this appears in searches
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    source_url = models.URLField(blank=True, help_text="Original source if applicable")
    language = models.CharField(max_length=10, default='en')
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    
    # Admin tracking
    created_by = models.CharField(max_length=100, blank=True)  # Admin username
    approved_by = models.CharField(max_length=100, blank=True)  # Admin username
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['category', 'is_approved']),
            models.Index(fields=['is_approved', 'security_reviewed']),
            models.Index(fields=['synced_to_chromadb']),
            models.Index(fields=['search_count', 'last_used']),
        ]
        db_table = 'public_chatbot_knowledge'  # Explicit table name for isolation
    
    def __str__(self):
        status = "✅" if self.is_approved else "⏳"
        return f"{status} {self.title} ({self.category})"
    
    def save(self, *args, **kwargs):
        """Auto-generate document_id and content preview"""
        if not self.document_id:
            self.document_id = f"pub_{timezone.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
        
        if not self.content_preview and self.content:
            # Create preview from first 300 characters
            self.content_preview = (self.content[:297] + '...') if len(self.content) > 300 else self.content
        
        # Generate content hash for duplicate detection
        if self.content:
            import hashlib
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()
        
        super().save(*args, **kwargs)


class ChatbotConfiguration(models.Model):
    """
    Global configuration for public chatbot - isolated settings
    """
    # Rate limiting settings
    daily_requests_per_ip = models.IntegerField(default=100)
    hourly_requests_per_ip = models.IntegerField(default=20)
    max_message_length = models.IntegerField(default=500)
    
    # ChromaDB settings
    max_search_results = models.IntegerField(default=5)
    similarity_threshold = models.FloatField(default=0.7)
    
    # LLM settings
    default_llm_provider = models.CharField(max_length=50, default='openai')
    default_model = models.CharField(max_length=100, default='gpt-3.5-turbo')
    max_response_tokens = models.IntegerField(default=300)
    system_prompt = models.TextField(
        default="You are a helpful assistant providing accurate, concise responses.",
        help_text="System prompt that defines the AI assistant's behavior and personality"
    )
    
    # Security settings
    enable_security_scanning = models.BooleanField(default=True)
    block_suspicious_ips = models.BooleanField(default=True)
    log_full_conversations = models.BooleanField(default=False)
    
    # Feature flags
    is_enabled = models.BooleanField(default=True, help_text="Global on/off switch")
    enable_vector_search = models.BooleanField(default=True, help_text="Enable/disable ChromaDB vector search for context")
    enable_query_rephrasing = models.BooleanField(default=True, help_text="Enable LLM-based query rephrasing for better retrieval on subsequent queries")
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.CharField(max_length=200, blank=True)
    
    # Monitoring
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True)  # Admin username
    
    class Meta:
        db_table = 'public_chatbot_config'
        verbose_name = 'Chatbot Configuration'
        verbose_name_plural = 'Chatbot Configuration'
    
    def __str__(self):
        status = "🟢 Enabled" if self.is_enabled else "🔴 Disabled"
        return f"Chatbot Config - {status}"
    
    def save(self, *args, **kwargs):
        # Ensure only one configuration record exists
        if not self.pk and ChatbotConfiguration.objects.exists():
            raise ValueError("Only one ChatbotConfiguration instance allowed")
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get or create the singleton configuration"""
        config, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'is_enabled': True,
                'maintenance_mode': False,
                'daily_requests_per_ip': 100,
                'hourly_requests_per_ip': 20,
                'system_prompt': "You are a helpful assistant providing accurate, concise responses."
            }
        )
        return config