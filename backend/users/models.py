# backend/users/models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group
from django.db import models
from django.utils import timezone
import uuid
import math

class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    STAFF = 'STAFF', 'Staff'
    USER = 'USER', 'Regular User'

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self.create_user(email, password, **extra_fields)

class IconClass(models.TextChoices):
    # User & People Icons
    USER = 'fa-user', 'User'
    USERS = 'fa-users', 'Users'
    USER_PLUS = 'fa-user-plus', 'Add User'
    USER_MINUS = 'fa-user-minus', 'Remove User'
    USER_SHIELD = 'fa-user-shield', 'User Security'
    USER_COG = 'fa-user-cog', 'User Settings'
    USER_TIE = 'fa-user-tie', 'Professional User'
    USER_GRADUATE = 'fa-user-graduate', 'Graduate/Student'
    
    # Navigation & Interface
    HOME = 'fa-home', 'Home'
    DASHBOARD = 'fa-tachometer-alt', 'Dashboard'
    MENU = 'fa-bars', 'Menu'
    GRID = 'fa-th', 'Grid View'
    LIST = 'fa-list', 'List View'
    SEARCH = 'fa-search', 'Search'
    FILTER = 'fa-filter', 'Filter'
    
    # Documents & Files
    FILE = 'fa-file', 'File'
    FILE_TEXT = 'fa-file-alt', 'Text Document'
    FILE_PDF = 'fa-file-pdf', 'PDF File'
    FILE_EXCEL = 'fa-file-excel', 'Excel File'
    FILE_WORD = 'fa-file-word', 'Word Document'
    FOLDER = 'fa-folder', 'Folder'
    FOLDER_OPEN = 'fa-folder-open', 'Open Folder'
    DOWNLOAD = 'fa-download', 'Download'
    UPLOAD = 'fa-upload', 'Upload'
    
    # Communication
    EMAIL = 'fa-envelope', 'Email'
    PHONE = 'fa-phone', 'Phone'
    COMMENTS = 'fa-comments', 'Comments'
    CHAT = 'fa-comment-dots', 'Chat'
    BELL = 'fa-bell', 'Notifications'
    
    # Settings & Configuration
    COG = 'fa-cog', 'Settings'
    COGS = 'fa-cogs', 'Advanced Settings'
    TOOLS = 'fa-tools', 'Tools'
    WRENCH = 'fa-wrench', 'Configuration'
    SLIDERS = 'fa-sliders-h', 'Controls'
    
    # Analytics & Charts
    CHART_BAR = 'fa-chart-bar', 'Bar Chart'
    CHART_LINE = 'fa-chart-line', 'Line Chart'
    CHART_PIE = 'fa-chart-pie', 'Pie Chart'
    ANALYTICS = 'fa-analytics', 'Analytics'
    GRAPH = 'fa-project-diagram', 'Graph'
    
    # Academic & Educational
    BOOK = 'fa-book', 'Book'
    GRADUATION_CAP = 'fa-graduation-cap', 'Education'
    UNIVERSITY = 'fa-university', 'University'
    CHALKBOARD = 'fa-chalkboard-teacher', 'Teaching'
    PENCIL = 'fa-pencil-alt', 'Edit/Write'
    CLIPBOARD = 'fa-clipboard', 'Clipboard'
    
    # Business & Finance
    BRIEFCASE = 'fa-briefcase', 'Business'
    DOLLAR = 'fa-dollar-sign', 'Finance'
    CALCULATOR = 'fa-calculator', 'Calculator'
    BALANCE = 'fa-balance-scale', 'Balance'
    HANDSHAKE = 'fa-handshake', 'Partnership'
    
    # Technology & Development
    CODE = 'fa-code', 'Code'
    LAPTOP = 'fa-laptop', 'Laptop'
    SERVER = 'fa-server', 'Server'
    DATABASE = 'fa-database', 'Database'
    CLOUD = 'fa-cloud', 'Cloud'
    ROBOT = 'fa-robot', 'AI/Automation'
    MICROCHIP = 'fa-microchip', 'Technology'
    
    # Security & Protection
    SHIELD = 'fa-shield-alt', 'Security'
    LOCK = 'fa-lock', 'Locked'
    UNLOCK = 'fa-unlock', 'Unlocked'
    KEY = 'fa-key', 'Access Key'
    EYE = 'fa-eye', 'View'
    EYE_SLASH = 'fa-eye-slash', 'Hide'
    
    # Actions & Controls
    PLAY = 'fa-play', 'Play/Start'
    PAUSE = 'fa-pause', 'Pause'
    STOP = 'fa-stop', 'Stop'
    REFRESH = 'fa-sync-alt', 'Refresh'
    EDIT = 'fa-edit', 'Edit'
    TRASH = 'fa-trash', 'Delete'
    SAVE = 'fa-save', 'Save'
    COPY = 'fa-copy', 'Copy'
    
    # Status & Indicators
    CHECK = 'fa-check', 'Success/Complete'
    TIMES = 'fa-times', 'Error/Close'
    EXCLAMATION = 'fa-exclamation-triangle', 'Warning'
    INFO = 'fa-info-circle', 'Information'
    STAR = 'fa-star', 'Favorite/Rating'
    HEART = 'fa-heart', 'Like/Favorite'
    
    # Navigation & Direction
    ARROW_RIGHT = 'fa-arrow-right', 'Arrow Right'
    ARROW_LEFT = 'fa-arrow-left', 'Arrow Left'
    ARROW_UP = 'fa-arrow-up', 'Arrow Up'
    ARROW_DOWN = 'fa-arrow-down', 'Arrow Down'
    PLUS = 'fa-plus', 'Add/Plus'
    MINUS = 'fa-minus', 'Remove/Minus'
    
    # Time & Calendar
    CALENDAR = 'fa-calendar', 'Calendar'
    CLOCK = 'fa-clock', 'Time'
    HISTORY = 'fa-history', 'History'
    
    # Location & Maps
    MAP = 'fa-map', 'Map'
    LOCATION = 'fa-map-marker-alt', 'Location'
    GLOBE = 'fa-globe', 'Global/World'
    
    # Miscellaneous
    QUESTION = 'fa-question-circle', 'Help/Question'
    LIGHTBULB = 'fa-lightbulb', 'Idea/Innovation'
    MAGIC = 'fa-magic', 'Magic/Special'
    FIRE = 'fa-fire', 'Hot/Trending'

class ColorTheme(models.TextChoices):
    # Oxford University Primary Colors
    OXFORD_BLUE = 'oxford-blue', 'Oxford Blue (#002147)'
    OXFORD_BLUE_LIGHT = 'oxford-blue-light', 'Light Oxford Blue (#334e68)'
    OXFORD_BLUE_DARK = 'oxford-blue-dark', 'Dark Oxford Blue (#001122)'
    
    # Academic Gold Accents
    ACADEMIC_GOLD = 'academic-gold', 'Academic Gold (#FFD700)'
    ANTIQUE_GOLD = 'antique-gold', 'Antique Gold (#CD7F32)'
    
    # Classic Academic Colors
    BURGUNDY = 'burgundy', 'Burgundy (#800020)'
    FOREST_GREEN = 'forest-green', 'Forest Green (#228B22)'
    ROYAL_PURPLE = 'royal-purple', 'Royal Purple (#663399)'
    CRIMSON = 'crimson', 'Crimson (#DC143C)'
    
    # Professional Neutrals
    CHARCOAL = 'charcoal', 'Charcoal Gray (#36454F)'
    SLATE = 'slate', 'Slate Gray (#708090)'
    PEARL = 'pearl', 'Pearl White (#F8F8FF)'
    CREAM = 'cream', 'Cream (#F5F5DC)'
    
    # Status Colors (Oxford-themed)
    SUCCESS = 'success', 'Success Green (#10B981)'
    WARNING = 'warning', 'Warning Amber (#F59E0B)'
    ERROR = 'error', 'Error Red (#EF4444)'
    INFO = 'info', 'Info Blue (#3B82F6)'
    
    # Vibrant Options
    EMERALD = 'emerald', 'Emerald (#50C878)'
    SAPPHIRE = 'sapphire', 'Sapphire (#0F52BA)'
    RUBY = 'ruby', 'Ruby (#E0115F)'
    AMBER = 'amber', 'Amber (#FFBF00)'
    
    # Modern Variants
    TEAL = 'teal', 'Teal (#008080)'
    INDIGO = 'indigo', 'Indigo (#4B0082)'
    CORAL = 'coral', 'Coral (#FF7F50)'
    MINT = 'mint', 'Mint (#98FB98)'

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.USER,
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        return self.first_name or self.email.split('@')[0]
    
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN
        
    @property
    def is_staff_member(self):
        return self.role == UserRole.STAFF

class DashboardIcon(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    icon_class = models.CharField(
        max_length=50, 
        choices=IconClass.choices,
        default=IconClass.DASHBOARD,
        help_text="Select an icon from the predefined FontAwesome icons"
    )
    color = models.CharField(
        max_length=20, 
        choices=ColorTheme.choices,
        default=ColorTheme.OXFORD_BLUE,
        help_text="Select a color theme that fits Oxford University branding"
    )
    route = models.CharField(max_length=100, help_text="Route to navigate to when icon is clicked")
    order = models.PositiveIntegerField(default=0, help_text="Display order on dashboard")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    authorized_users = models.ManyToManyField(
        User,
        through='UserIconPermission',
        related_name='accessible_icons',
        through_fields=('icon', 'user')
    )
    
    authorized_groups = models.ManyToManyField(
        Group,
        through='GroupIconPermission',
        related_name='accessible_icons',
        through_fields=('icon', 'group')
    )
    
    class Meta:
        ordering = ['order', 'name']
        
    def __str__(self):
        return self.name
    
    def generate_collection_name(self) -> str:
        """Generate collection name using project name instead of generic 'project' prefix"""
        # Sanitize project name for Milvus collection naming
        # Replace spaces and special characters with underscores
        sanitized_name = self.name.lower().replace(' ', '_').replace('-', '_')
        # Remove any non-alphanumeric characters except underscores
        sanitized_name = ''.join(c for c in sanitized_name if c.isalnum() or c == '_')
        # Ensure it starts with a letter (Milvus requirement)
        if not sanitized_name or not sanitized_name[0].isalpha():
            sanitized_name = 'project_' + sanitized_name
        
        # Add project ID suffix to ensure uniqueness
        project_id_suffix = str(self.project_id).replace('-', '_')
        collection_name = f"{sanitized_name}_{project_id_suffix}"
        
        return collection_name

class UserIconPermission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    icon = models.ForeignKey(DashboardIcon, on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='granted_permissions'
    )
    
    class Meta:
        unique_together = ['user', 'icon']
        
    def __str__(self):
        return f"{self.user.email} - {self.icon.name}"

class GroupIconPermission(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    icon = models.ForeignKey(DashboardIcon, on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='granted_group_permissions'
    )
    
    class Meta:
        unique_together = ['group', 'icon']
        
    def __str__(self):
        return f"{self.group.name} - {self.icon.name}"

# ============================================================================
# PROJECT PERMISSION MODELS
# ============================================================================

class UserProjectPermission(models.Model):
    """Individual user permissions for specific projects"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_permissions')
    project = models.ForeignKey('IntelliDocProject', on_delete=models.CASCADE, related_name='user_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='granted_project_permissions'
    )
    
    class Meta:
        unique_together = ['user', 'project']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['project']),
        ]
        
    def __str__(self):
        return f"{self.user.email} - {self.project.name}"

class GroupProjectPermission(models.Model):
    """Group-based permissions for specific projects"""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='project_permissions')
    project = models.ForeignKey('IntelliDocProject', on_delete=models.CASCADE, related_name='group_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='granted_group_project_permissions'
    )
    
    class Meta:
        unique_together = ['group', 'project']
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['project']),
        ]
        
    def __str__(self):
        return f"{self.group.name} - {self.project.name}"

# IntelliDoc Models
# Note: ProjectTemplate has been moved to templates.models

class IntelliDocProject(models.Model):
    project_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Navigation feature flag - only for projects that should have multi-page navigation
    has_navigation = models.BooleanField(default=False, help_text="Enable multi-page navigation for this project")
    
    # Cloned template data (copied during creation, independent of original template)
    template_name = models.CharField(max_length=100, blank=True)
    template_type = models.CharField(max_length=20, blank=True)
    template_version = models.CharField(max_length=50, blank=True, help_text="Template version at creation time")
    template_description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    suggested_questions = models.JSONField(default=list)
    required_fields = models.JSONField(default=list)
    analysis_focus = models.TextField(blank=True)
    icon_class = models.CharField(max_length=50, default='fa-file-alt')
    color_theme = models.CharField(max_length=20, default='oxford-blue')
    
    # NEW: Complete configuration fields for template independence
    total_pages = models.IntegerField(default=1, help_text="Total number of navigation pages")
    navigation_pages = models.JSONField(default=list, help_text="Complete navigation configuration")
    processing_capabilities = models.JSONField(default=dict, help_text="Processing capabilities configuration")
    validation_rules = models.JSONField(default=dict, help_text="Validation rules configuration")
    ui_configuration = models.JSONField(default=dict, help_text="UI configuration settings")
    
    # Document organization settings
    preserve_original_folder_structure = models.BooleanField(
        default=True,
        help_text="LLM-based folder organization using per-document short summaries"
    )
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='intellidoc_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Project access permissions
    authorized_users = models.ManyToManyField(
        User,
        through='UserProjectPermission',
        related_name='accessible_projects',
        through_fields=('project', 'user'),
        blank=True
    )
    
    authorized_groups = models.ManyToManyField(
        Group,
        through='GroupProjectPermission',
        related_name='accessible_projects',
        through_fields=('project', 'group'),
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return self.name
    
    def has_user_access(self, user):
        """Check if a user has access to this project"""
        # Project creator always has access
        if self.created_by == user:
            return True
        
        # Superusers always have access (Django's built-in permission system)
        # This ensures superusers have access even if their role field is not ADMIN
        if user.is_superuser:
            return True
        
        # Admin users always have access
        if user.is_admin:
            return True
        
        # Check direct user permission
        if self.user_permissions.filter(user=user).exists():
            return True
        
        # Check group permissions
        user_groups = user.groups.all()
        if self.group_permissions.filter(group__in=user_groups).exists():
            return True
        
        return False
    
    def generate_collection_name(self) -> str:
        """Generate collection name using project name instead of generic 'project' prefix
        
        IMPORTANT: This method MUST match the logic in MilvusProjectVectorDatabase._generate_collection_name()
        to prevent collection name mismatches between database records and actual Milvus collections.
        """
        import re
        
        # Sanitize project name for Milvus compatibility
        # Milvus collection names can only contain numbers, letters and underscores
        # Remove all non-alphanumeric characters (spaces, hyphens, etc.) to match actual collection creation behavior
        # This matches the behavior in MilvusProjectVectorDatabase._generate_collection_name()
        sanitized_name = re.sub(r'[^a-zA-Z0-9]', '', self.name.lower())
        
        # Ensure name is not empty and starts with a letter or underscore
        if not sanitized_name or sanitized_name[0].isdigit():
            sanitized_name = f"project_{sanitized_name}"
        
        # Limit length to reasonable size (Milvus has limits)
        # This MUST match the limit in MilvusProjectVectorDatabase._generate_collection_name()
        if len(sanitized_name) > 20:
            sanitized_name = sanitized_name[:20]
        
        # Append project ID suffix to ensure uniqueness
        project_id_suffix = str(self.project_id).replace('-', '_')
        collection_name = f"{sanitized_name}_{project_id_suffix}"
        
        return collection_name


class ProjectDocument(models.Model):
    """Documents uploaded to specific projects - ensures project isolation"""
    document_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    project = models.ForeignKey(IntelliDocProject, on_delete=models.CASCADE, related_name='documents')
    
    # File information
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)  # Path to stored file
    file_size = models.BigIntegerField()  # Size in bytes
    file_type = models.CharField(max_length=100)  # MIME type
    file_extension = models.CharField(max_length=10)
    
    # Document metadata
    upload_status = models.CharField(max_length=20, choices=[
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error')
    ], default='uploading')
    
    # Analysis results (will be populated after document analysis)
    analysis_results = models.JSONField(default=dict, blank=True)
    extraction_text = models.TextField(blank=True)  # Extracted text content
    
    # Tracking
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # LLM Provider File References (for Full Document Mode)
    # These store file_ids from LLM provider File APIs for sending entire documents
    llm_file_id_openai = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="OpenAI Files API file_id for this document"
    )
    llm_file_id_anthropic = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Anthropic Files API file_id for this document"
    )
    llm_file_id_google = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Google/Gemini Files API file URI for this document"
    )
    llm_file_uploaded_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When the document was uploaded to LLM providers"
    )
    
    class Meta:
        ordering = ['-uploaded_at']
        # Ensure document names are unique within each project
        unique_together = ['project', 'original_filename']
    
    def __str__(self):
        return f"{self.original_filename} ({self.project.name})"
    
    @property
    def file_size_formatted(self):
        """Return human-readable file size"""
        if self.file_size == 0:
            return '0 Bytes'
        
        k = 1024
        sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
        i = int(math.floor(math.log(self.file_size) / math.log(k)))
        return f"{round(self.file_size / math.pow(k, i), 2)} {sizes[i]}"
    
    def get_storage_path(self):
        """Generate secure storage path for the document"""
        return f"projects/{self.project.project_id}/documents/{self.document_id}_{self.original_filename}"


class ProjectDocumentSummary(models.Model):
    """
    Document-level AI summaries generated from the provider's File API.

    One row per `ProjectDocument` (project isolation is enforced via the FK chain:
    ProjectDocument -> IntelliDocProject).
    """

    document = models.OneToOneField(
        ProjectDocument,
        on_delete=models.CASCADE,
        related_name='document_summary',
    )

    # ~3000-word summary
    long_summary = models.TextField(blank=True)
    # ~200-word derived summary
    short_summary = models.TextField(blank=True)

    llm_provider = models.CharField(max_length=20, default='openai')
    llm_model = models.CharField(max_length=100, blank=True)
    summarizer_used = models.CharField(max_length=50, default='file_api')

    memory = models.JSONField(
        default=list, blank=True,
        help_text="Accumulated agent insights from tool calls",
    )
    citation = models.JSONField(
        default=dict, blank=True,
        help_text="Bibliographic metadata for the document (title, authors, year, DOI, etc.)",
    )

    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Summary: {self.document.original_filename}"


class WebSearchUrlSummary(models.Model):
    """
    LLM-generated summaries for web search URLs configured on agent nodes.

    One row per (project, url) pair. Used to build per-URL tool descriptions
    so the LLM can selectively call only the most relevant URL instead of
    fetching all configured URLs at once.

    Project isolation: enforced via the FK to IntelliDocProject.
    """

    project = models.ForeignKey(
        'IntelliDocProject',
        on_delete=models.CASCADE,
        related_name='url_summaries',
    )
    url = models.URLField(max_length=2000)

    # ~200-word summary used as the tool description
    short_summary = models.TextField(blank=True)
    # ~3000-word detailed summary stored for future use
    long_summary = models.TextField(blank=True)

    llm_provider = models.CharField(max_length=20, default='openai')
    llm_model = models.CharField(max_length=100, blank=True)

    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('project', 'url')]
        ordering = ['url']

    def __str__(self):
        return f"URLSummary: {self.url[:80]}"


class ProjectDocumentFolderOrganization(models.Model):
    """
    Stores a per-project mapping of each document to an LLM-chosen folder path
    (used for both Milvus chunk organization and the UI node attachment folder picker).

    Project isolation is enforced via:
    ProjectDocumentFolderOrganization -> ProjectDocument -> IntelliDocProject.
    """

    document = models.OneToOneField(
        ProjectDocument,
        on_delete=models.CASCADE,
        related_name='folder_organization',
    )

    # Example: "Legal/Contracts" (depth <= 2; no leading/trailing slashes)
    folder_path = models.CharField(max_length=200, default='General')

    llm_provider = models.CharField(max_length=20, default='openai')
    llm_model = models.CharField(max_length=100, blank=True)
    organization_method = models.CharField(max_length=50, default='llm_folder_org')

    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['document']),
        ]

    def __str__(self):
        return f"Folder org for {self.document.original_filename}: {self.folder_path}"

# ============================================================================
# PROJECT-SPECIFIC API KEY MANAGEMENT
# ============================================================================

class ProjectAPIKeyProvider(models.TextChoices):
    """Supported API providers for project-specific keys"""
    OPENAI = 'openai', 'OpenAI'
    GOOGLE = 'google', 'Google (Gemini)'
    ANTHROPIC = 'anthropic', 'Anthropic (Claude)'

class ProjectAPIKey(models.Model):
    """Project-specific API key storage with encryption"""
    # Core identification
    project = models.ForeignKey(IntelliDocProject, on_delete=models.CASCADE, related_name='api_keys')
    provider_type = models.CharField(
        max_length=20, 
        choices=ProjectAPIKeyProvider.choices,
        help_text="API provider type"
    )
    
    # Encrypted API key storage
    encrypted_api_key = models.TextField(
        help_text="Encrypted API key using project-specific encryption"
    )
    
    # Key metadata
    key_name = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Optional descriptive name for the key (e.g., 'Production Key')"
    )
    
    # Status and validation
    is_active = models.BooleanField(default=True, help_text="Whether this key is active and should be used")
    is_validated = models.BooleanField(default=False, help_text="Whether this key has been validated with the provider")
    validation_error = models.TextField(blank=True, help_text="Last validation error message, if any")
    last_validated_at = models.DateTimeField(null=True, blank=True, help_text="When the key was last validated")
    
    # Usage tracking
    usage_count = models.IntegerField(default=0, help_text="Number of times this key has been used")
    last_used_at = models.DateTimeField(null=True, blank=True, help_text="When the key was last used")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, help_text="User who added this API key")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        unique_together = ['project', 'provider_type']  # One key per provider per project
        indexes = [
            models.Index(fields=['project', 'provider_type', 'is_active']),
            models.Index(fields=['project', 'is_active']),
        ]
    
    def __str__(self):
        key_name = self.key_name or f"{self.get_provider_type_display()} Key"
        return f"{self.project.name} - {key_name} ({self.provider_type})"
    
    @property
    def masked_key(self):
        """Return a masked version of the key for display purposes"""
        if not hasattr(self, '_decrypted_key'):
            return "••••••••••••••••"
        
        key = self._decrypted_key
        if len(key) <= 8:
            return "••••••••"
        return f"{key[:4]}••••••••{key[-4:]}"
    
    @property
    def status_display(self):
        """Get human-readable status"""
        if not self.is_active:
            return "Inactive"
        elif not self.is_validated:
            return "Not Validated"
        elif self.validation_error:
            return "Validation Failed"
        else:
            return "Active"
    
    def get_provider_display_info(self):
        """Get provider display information"""
        provider_info = {
            'openai': {
                'name': 'OpenAI',
                'description': 'GPT models for chat, summarization, and analysis',
                'icon': 'fa-robot',
                'color': 'emerald'
            },
            'google': {
                'name': 'Google Gemini',
                'description': 'Gemini models for document processing and OCR',
                'icon': 'fa-google',
                'color': 'info'
            },
            'anthropic': {
                'name': 'Anthropic Claude',
                'description': 'Claude models for advanced reasoning and analysis',
                'icon': 'fa-brain',
                'color': 'royal-purple'
            }
        }
        return provider_info.get(self.provider_type, {
            'name': self.get_provider_type_display(),
            'description': 'API provider',
            'icon': 'fa-key',
            'color': 'oxford-blue'
        })


# ============================================================================
# MCP SERVER MODELS
# ============================================================================

class MCPServerType(models.TextChoices):
    """Supported MCP server types"""
    GOOGLE_DRIVE = 'google_drive', 'Google Drive'
    SHAREPOINT = 'sharepoint', 'SharePoint'


class MCPServerCredential(models.Model):
    """Project-specific MCP server credential storage with encryption"""
    # Core identification
    project = models.ForeignKey(IntelliDocProject, on_delete=models.CASCADE, related_name='mcp_server_credentials')
    server_type = models.CharField(
        max_length=20,
        choices=MCPServerType.choices,
        help_text="MCP server type"
    )
    
    # Encrypted credentials storage (JSON format)
    encrypted_credentials = models.TextField(
        help_text="Encrypted credentials JSON using project-specific encryption"
    )
    
    # Server configuration (unencrypted, for non-sensitive settings)
    server_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Server configuration (site URLs, folder paths, etc.)"
    )
    
    # Credential metadata
    credential_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional descriptive name for the credential (e.g., 'Production Credentials')"
    )
    
    # Status and validation
    is_active = models.BooleanField(default=True, help_text="Whether this credential is active and should be used")
    is_validated = models.BooleanField(default=False, help_text="Whether this credential has been validated with the server")
    validation_error = models.TextField(blank=True, help_text="Last validation error message, if any")
    last_validated_at = models.DateTimeField(null=True, blank=True, help_text="When the credential was last validated")
    
    # Usage tracking
    usage_count = models.IntegerField(default=0, help_text="Number of times this credential has been used")
    last_used_at = models.DateTimeField(null=True, blank=True, help_text="When the credential was last used")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, help_text="User who added this credential")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        unique_together = ['project', 'server_type']  # One credential per server type per project
        indexes = [
            models.Index(fields=['project', 'server_type', 'is_active']),
            models.Index(fields=['project', 'is_active']),
        ]
    
    def __str__(self):
        credential_name = self.credential_name or f"{self.get_server_type_display()} Credential"
        return f"{self.project.name} - {credential_name} ({self.server_type})"
    
    @property
    def status_display(self):
        """Get human-readable status"""
        if not self.is_active:
            return "Inactive"
        elif not self.is_validated:
            return "Not Validated"
        elif self.validation_error:
            return "Validation Failed"
        else:
            return "Active"
    
    def get_server_display_info(self):
        """Get server display information"""
        server_info = {
            'google_drive': {
                'name': 'Google Drive',
                'description': 'Access and manage Google Drive files and folders',
                'icon': 'fa-google-drive',
                'color': 'blue'
            },
            'sharepoint': {
                'name': 'SharePoint',
                'description': 'Access and manage SharePoint documents and sites',
                'icon': 'fa-microsoft',
                'color': 'orange'
            }
        }
        return server_info.get(self.server_type, {
            'name': self.get_server_type_display(),
            'description': 'MCP server',
            'icon': 'fa-server',
            'color': 'oxford-blue'
        })


# ============================================================================
# LLM EVALUATION MODELS
# ============================================================================

class LLMProvider(models.Model):
    """Represents different LLM providers (OpenAI, Gemini, Claude, etc.)"""
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('gemini', 'Google Gemini'),
        ('claude', 'Anthropic Claude'),
        ('huggingface', 'Hugging Face'),
    ]
    
    name = models.CharField(max_length=50, help_text="Provider display name (e.g., 'OpenAI')")
    provider_type = models.CharField(max_length=20, choices=PROVIDER_CHOICES, unique=True)
    api_endpoint = models.URLField()
    is_active = models.BooleanField(default=True)
    max_tokens = models.IntegerField(default=1000)
    timeout_seconds = models.IntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class APIKeyConfig(models.Model):
    """Manages API keys for different LLM providers"""
    provider = models.ForeignKey(LLMProvider, on_delete=models.CASCADE)
    key_name = models.CharField(max_length=100, help_text="Descriptive name for this API key")
    api_key = models.TextField(help_text="Encrypted API key")
    usage_limit_daily = models.IntegerField(null=True, blank=True, help_text="Daily request limit")
    usage_count_today = models.IntegerField(default=0)
    last_reset_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['provider', 'key_name']
        ordering = ['provider', 'key_name']
    
    def __str__(self):
        return f"{self.provider.name} - {self.key_name}"


class LLMComparison(models.Model):
    """Stores comparison sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    prompt = models.TextField()
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.title or self.prompt[:50]}..."


class LLMResponse(models.Model):
    """Stores individual LLM responses within a comparison"""
    comparison = models.ForeignKey(LLMComparison, on_delete=models.CASCADE, related_name='responses')
    provider = models.ForeignKey(LLMProvider, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=100)
    response_text = models.TextField(blank=True)
    response_time_ms = models.IntegerField(help_text="Response time in milliseconds")
    token_count = models.IntegerField(null=True, blank=True)
    cost_estimate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.provider.name} - {self.comparison.id}"


# Vector Search Models
class VectorProcessingStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'


class ProjectVectorCollection(models.Model):
    """Tracks vector collection status for each project"""
    project = models.OneToOneField(IntelliDocProject, on_delete=models.CASCADE, related_name='vector_collection')
    collection_name = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=VectorProcessingStatus.choices, default=VectorProcessingStatus.PENDING)
    total_documents = models.IntegerField(default=0)
    processed_documents = models.IntegerField(default=0)
    failed_documents = models.IntegerField(default=0)
    last_processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.collection_name} ({self.status})"
    
    @property
    def processing_progress(self):
        """Return processing progress as percentage"""
        if self.total_documents == 0:
            return 0
        return (self.processed_documents / self.total_documents) * 100


class DocumentVectorStatus(models.Model):
    """Tracks vector processing status for individual documents"""
    document = models.OneToOneField(ProjectDocument, on_delete=models.CASCADE, related_name='vector_status')
    collection = models.ForeignKey(ProjectVectorCollection, on_delete=models.CASCADE, related_name='document_statuses')
    status = models.CharField(max_length=20, choices=VectorProcessingStatus.choices, default=VectorProcessingStatus.PENDING)
    vector_id = models.CharField(max_length=100, blank=True, help_text="Milvus vector ID")
    content_length = models.IntegerField(default=0)
    embedding_dimension = models.IntegerField(default=384)
    processing_time_ms = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Summary and Topic tracking fields
    summary_generated = models.BooleanField(default=False, help_text='Whether summary has been generated for this document')
    summary_generated_at = models.DateTimeField(null=True, blank=True, help_text='When summary was generated')
    summary_chunks_count = models.IntegerField(default=0, help_text='Number of chunks with summaries')
    topic_generated = models.BooleanField(default=False, help_text='Whether topics have been generated for this document')
    topic_generated_at = models.DateTimeField(null=True, blank=True, help_text='When topics were generated')
    topic_chunks_count = models.IntegerField(default=0, help_text='Number of chunks with topics')
    summarizer_used = models.CharField(max_length=50, default='none', help_text='Which summarizer was used (openai_gpt, simple, none)')
    topic_generator_used = models.CharField(max_length=50, default='none', help_text='Which topic generator was used (openai_gpt, simple, none)')
    
    class Meta:
        ordering = ['-updated_at']
        unique_together = ['document', 'collection']
    
    def __str__(self):
        return f"{self.document.original_filename} - {self.status}"


class DocumentChunk(models.Model):
    """Tracks individual document chunks with summary/topic metadata"""
    chunk_id = models.CharField(max_length=100, unique=True, help_text='Unique chunk identifier')
    chunk_index = models.IntegerField(help_text='Order of chunk within document')
    chunk_type = models.CharField(max_length=50, default='content', help_text='Type of chunk (content, header, section, etc.)')
    section_title = models.CharField(max_length=500, blank=True, help_text='Section title or heading')
    content_length = models.IntegerField(default=0, help_text='Length of chunk content in characters')
    has_embedding = models.BooleanField(default=False, help_text='Whether chunk has vector embedding')
    vector_id = models.CharField(max_length=100, blank=True, help_text='Vector database ID for this chunk')
    
    # Summary fields
    has_summary = models.BooleanField(default=False, help_text='Whether chunk has generated summary')
    summary_word_count = models.IntegerField(default=0, help_text='Word count of generated summary')
    summary_generated_at = models.DateTimeField(null=True, blank=True)
    summarizer_used = models.CharField(max_length=50, default='none')
    
    # Topic fields
    has_topic = models.BooleanField(default=False, help_text='Whether chunk has generated topic')
    topic_word_count = models.IntegerField(default=0, help_text='Word count of generated topic')
    topic_generated_at = models.DateTimeField(null=True, blank=True)
    topic_generator_used = models.CharField(max_length=50, default='none')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Relationships
    document = models.ForeignKey(ProjectDocument, on_delete=models.CASCADE, related_name='chunks')
    vector_status = models.ForeignKey(DocumentVectorStatus, on_delete=models.CASCADE, related_name='chunks')
    
    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']
    
    def __str__(self):
        return f"{self.document.original_filename} - Chunk {self.chunk_index}"
    
    @property
    def has_ai_generated_content(self):
        """Check if chunk has AI-generated summary or topic"""
        return self.has_summary or self.has_topic
    
    @property
    def ai_processing_status(self):
        """Get AI processing status summary"""
        status = []
        if self.has_summary:
            status.append(f"Summary ({self.summarizer_used})")
        if self.has_topic:
            status.append(f"Topic ({self.topic_generator_used})")
        return ", ".join(status) if status else "No AI processing"



# ============================================================================
# AGENT ORCHESTRATION MODELS (Template Independent)
# ============================================================================

class AgentWorkflowStatus(models.TextChoices):
    """Status choices for agent workflows"""
    DRAFT = 'draft', 'Draft'
    VALIDATED = 'validated', 'Validated'
    ACTIVE = 'active', 'Active'
    ARCHIVED = 'archived', 'Archived'


class AgentWorkflow(models.Model):
    """Template-independent agent workflow storage with workflow orchestration"""
    # Core identification
    project = models.ForeignKey(IntelliDocProject, on_delete=models.CASCADE, related_name='agent_workflows')
    workflow_id = models.UUIDField(default=uuid.uuid4, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Workflow configuration
    graph_json = models.JSONField(help_text='Visual graph representation with nodes and edges')
    version = models.CharField(max_length=20, default='1.0.0')
    status = models.CharField(max_length=20, choices=AgentWorkflowStatus.choices, default=AgentWorkflowStatus.DRAFT)
    
    # 🤖 CUSTOM ORCHESTRATION INTEGRATION FIELDS (Phase 1)
    custom_config = models.JSONField(default=dict, help_text='Custom orchestration configuration and metadata')
    supports_rag = models.BooleanField(default=False, help_text='Whether workflow uses document-aware agents')
    vector_collections = models.JSONField(default=list, help_text='Milvus collections for RAG-enabled agents')
    generated_code = models.TextField(blank=True, help_text='Generated orchestration code for execution')
    code_generation_timestamp = models.DateTimeField(null=True, blank=True, help_text='When orchestration code was last generated')
    
    # 📊 EXECUTION TRACKING FIELDS (From Migration 0014)
    total_executions = models.IntegerField(default=0)
    successful_executions = models.IntegerField(default=0)
    average_execution_time = models.FloatField(null=True, blank=True, help_text='Average execution time in seconds')
    
    # Agent capabilities (cloned from project)
    max_agents_limit = models.IntegerField(default=10)
    supports_function_tools = models.BooleanField(default=True)
    supports_real_time_streaming = models.BooleanField(default=True)
    sandbox_execution_enabled = models.BooleanField(default=True)
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('User', on_delete=models.CASCADE)
    last_executed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-updated_at']
        unique_together = ['project', 'name']
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"
    
    @property
    def node_count(self):
        """Get number of nodes in workflow"""
        return len(self.graph_json.get('nodes', []))
    
    @property
    def edge_count(self):
        """Get number of edges in workflow"""
        return len(self.graph_json.get('edges', []))
    
    @property
    def execution_count(self):
        """Get total number of executions (using new field)"""
        return self.total_executions
    
    @property
    def last_execution_status(self):
        """Get status of last execution"""
        # Fixed related name issue - migrations use 'simulation_runs' not 'runs'
        last_run = self.simulation_runs.order_by('-start_time').first()
        return last_run.status if last_run else 'never_executed'
    
    # 🤖 CUSTOM ORCHESTRATION INTEGRATION PROPERTIES (Phase 1)
    @property
    def has_doc_aware_agents(self):
        """Check if workflow contains document-aware agents"""
        nodes = self.graph_json.get('nodes', [])
        return any(node.get('data', {}).get('doc_aware', False) for node in nodes)
    
    @property
    def orchestration_agent_types(self):
        """Get list of custom orchestration agent types in workflow"""
        nodes = self.graph_json.get('nodes', [])
        return list(set(node['type'] for node in nodes if node['type'] not in ['StartNode', 'EndNode']))
    
    @property
    def connection_types_used(self):
        """Get list of custom orchestration connection types used"""
        edges = self.graph_json.get('edges', [])
        return list(set(edge.get('type', 'sequential') for edge in edges))
    
    @property
    def needs_code_regeneration(self):
        """Check if orchestration code needs to be regenerated"""
        # For now, always return False since we're not generating code
        return False
    
    @property
    def orchestration_complexity_score(self):
        """Calculate workflow complexity for custom orchestration execution"""
        nodes = self.graph_json.get('nodes', [])
        edges = self.graph_json.get('edges', [])
        
        base_score = len(nodes) + len(edges)
        
        # Add complexity for special features
        if self.has_doc_aware_agents:
            base_score += 5  # RAG adds complexity
        
        connection_types = self.connection_types_used
        if 'group_chat' in connection_types:
            base_score += 3  # Group chat adds complexity
        if 'conditional' in connection_types:
            base_score += 2  # Conditional routing adds complexity
        if 'reflection' in connection_types:
            base_score += 4  # Reflection loops add significant complexity
            
        return base_score
    
    @property
    def success_rate(self):
        """Calculate execution success rate"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100


class SimulationRunStatus(models.TextChoices):
    """Status choices for simulation runs"""
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    STOPPED = 'stopped', 'Stopped'
    CANCELLED = 'cancelled', 'Cancelled'


class SimulationRun(models.Model):
    """Template-independent simulation execution records"""
    # Core identification
    workflow = models.ForeignKey(AgentWorkflow, on_delete=models.CASCADE, related_name='simulation_runs')
    run_id = models.UUIDField(default=uuid.uuid4, unique=True)
    
    # Execution metadata
    status = models.CharField(max_length=20, choices=SimulationRunStatus.choices, default=SimulationRunStatus.PENDING)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # Configuration snapshot
    graph_snapshot = models.JSONField(help_text='Graph state at execution time')
    execution_parameters = models.JSONField(default=dict, help_text='Runtime parameters and settings')
    
    # Results and errors
    result_summary = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    error_traceback = models.TextField(blank=True)
    
    # Performance metrics
    total_messages = models.IntegerField(default=0)
    total_agents_involved = models.IntegerField(default=0)
    average_response_time = models.FloatField(null=True, blank=True)
    
    # Execution context
    celery_task_id = models.CharField(max_length=100, blank=True)
    executed_by = models.ForeignKey('User', on_delete=models.CASCADE)
    execution_environment = models.CharField(max_length=50, default='production')
    
    class Meta:
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.workflow.name} - Run {self.run_id.hex[:8]} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Calculate duration on save
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration_seconds = delta.total_seconds()
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if run is currently active"""
        return self.status in [SimulationRunStatus.PENDING, SimulationRunStatus.RUNNING]
    
    @property
    def formatted_duration(self):
        """Get human-readable duration"""
        if not self.duration_seconds:
            return 'N/A'
        
        if self.duration_seconds < 60:
            return f"{self.duration_seconds:.1f}s"
        elif self.duration_seconds < 3600:
            minutes = self.duration_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = self.duration_seconds / 3600
            return f"{hours:.1f}h"


class AgentMessageType(models.TextChoices):
    """Types of agent messages"""
    CHAT = 'chat', 'Chat Message'
    SYSTEM = 'system', 'System Message'
    FUNCTION_CALL = 'function_call', 'Function Call'
    FUNCTION_RESULT = 'function_result', 'Function Result'
    ERROR = 'error', 'Error Message'
    STATUS = 'status', 'Status Update'
    USER_INPUT = 'user_input', 'User Input'
    WORKFLOW_START = 'workflow_start', 'Workflow Start'
    WORKFLOW_END = 'workflow_end', 'Workflow End'


class AgentMessage(models.Model):
    """Template-independent message storage for agent conversations"""
    # Core identification
    run = models.ForeignKey(SimulationRun, on_delete=models.CASCADE, related_name='messages')
    message_id = models.UUIDField(default=uuid.uuid4, unique=True)
    
    # Message content
    agent_name = models.CharField(max_length=100)
    agent_type = models.CharField(max_length=50, default='unknown')
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=AgentMessageType.choices, default=AgentMessageType.CHAT)
    
    # Message metadata
    timestamp = models.DateTimeField(auto_now_add=True)
    sequence_number = models.IntegerField(help_text='Message order in conversation')
    parent_message_id = models.UUIDField(null=True, blank=True, help_text='Reference to parent message')
    
    # Additional data
    metadata = models.JSONField(default=dict, help_text='Additional message metadata')
    function_name = models.CharField(max_length=100, blank=True, help_text='Function name for function calls')
    function_arguments = models.JSONField(null=True, blank=True, help_text='Function call arguments')
    function_result = models.JSONField(null=True, blank=True, help_text='Function execution result')
    
    # Performance metrics
    response_time_ms = models.IntegerField(null=True, blank=True)
    token_count = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['run', 'sequence_number']
        unique_together = ['run', 'sequence_number']
    
    def __str__(self):
        content_preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.agent_name}: {content_preview}"
    
    @property
    def formatted_timestamp(self):
        """Get human-readable timestamp"""
        return self.timestamp.strftime('%H:%M:%S')
    
    @property
    def is_function_call(self):
        """Check if message is a function call"""
        return self.message_type == AgentMessageType.FUNCTION_CALL
    
    @property
    def is_user_message(self):
        """Check if message is from user"""
        return self.message_type == AgentMessageType.USER_INPUT or self.agent_type == 'UserProxyAgent'


class WorkflowTemplate(models.Model):
    """Template-independent workflow templates for reuse"""
    # Core identification
    template_id = models.UUIDField(default=uuid.uuid4, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, default='general')
    
    # Template content
    graph_template = models.JSONField(help_text='Template graph structure')
    default_parameters = models.JSONField(default=dict, help_text='Default parameters for template')
    
    # Metadata
    is_public = models.BooleanField(default=False, help_text='Whether template is publicly available')
    tags = models.JSONField(default=list, blank=True)
    version = models.CharField(max_length=20, default='1.0.0')
    created_by = models.ForeignKey('User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Usage tracking
    usage_count = models.IntegerField(default=0)
    rating_average = models.FloatField(null=True, blank=True)
    rating_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name} (v{self.version})"
    
    @property
    def template_complexity(self):
        """Get template complexity based on node count"""
        node_count = len(self.graph_template.get('nodes', []))
        if node_count <= 2:
            return 'simple'
        elif node_count <= 5:
            return 'moderate'
        else:
            return 'complex'


# ============================================================================
# WORKFLOW EXECUTION HISTORY MODELS (For Real Orchestration)
# ============================================================================

class WorkflowExecutionStatus(models.TextChoices):
    """Status choices for workflow executions"""
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    STOPPED = 'stopped', 'Stopped'


class WorkflowExecution(models.Model):
    """Stores execution history for real workflow orchestration"""
    # Core identification
    workflow = models.ForeignKey(AgentWorkflow, on_delete=models.CASCADE, related_name='executions')
    execution_id = models.CharField(max_length=100, unique=True)
    
    # Execution metadata
    status = models.CharField(max_length=20, choices=WorkflowExecutionStatus.choices, default=WorkflowExecutionStatus.PENDING)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # Execution results
    total_messages = models.IntegerField(default=0)
    total_agents_involved = models.IntegerField(default=0)
    average_response_time_ms = models.FloatField(null=True, blank=True)
    providers_used = models.JSONField(default=list)
    conversation_history = models.TextField(blank=True)
    result_summary = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    # MCP: Store outputs of executed nodes for multi-input support
    executed_nodes = models.JSONField(default=dict)
    # MCP: Store full message data for conversation history persistence
    messages_data = models.JSONField(default=list)
    
    # ============================================================================
    # HUMAN INPUT TRACKING FIELDS (UserProxyAgent Implementation - Phase 1)
    # ============================================================================
    human_input_required = models.BooleanField(default=False, help_text='Whether workflow is paused awaiting human input')
    awaiting_human_input_agent = models.CharField(max_length=100, blank=True, help_text='Name of UserProxyAgent awaiting input')
    human_input_prompt = models.TextField(blank=True, help_text='Prompt/context for human input interface')
    human_input_context = models.JSONField(default=dict, help_text='Input context from connected agents for human interface')
    human_input_requested_at = models.DateTimeField(null=True, blank=True, help_text='When human input was requested')
    human_input_received_at = models.DateTimeField(null=True, blank=True, help_text='When human input was received')
    human_input_agent_id = models.CharField(max_length=100, blank=True, help_text='ID of UserProxyAgent node awaiting input')
    
    # Metadata
    executed_by = models.ForeignKey('User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.workflow.name} - {self.execution_id} ({self.status})"
    
    @property
    def formatted_duration(self):
        """Get human-readable duration"""
        if not self.duration_seconds:
            return 'N/A'
        
        if self.duration_seconds < 60:
            return f"{self.duration_seconds:.1f}s"
        elif self.duration_seconds < 3600:
            minutes = self.duration_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = self.duration_seconds / 3600
            return f"{hours:.1f}h"


class WorkflowExecutionMessageType(models.TextChoices):
    """Types of execution messages"""
    CHAT = 'chat', 'Chat'
    WORKFLOW_START = 'workflow_start', 'Workflow Start'
    WORKFLOW_END = 'workflow_end', 'Workflow End'
    GROUP_CHAT_SUMMARY = 'group_chat_summary', 'Group Chat Summary'
    SYSTEM = 'system', 'System'
    ERROR = 'error', 'Error'
    REFLECTION_FEEDBACK = 'reflection_feedback', 'Reflection Feedback'
    REFLECTION_REVISION = 'reflection_revision', 'Reflection Revision'
    REFLECTION_FINAL = 'reflection_final', 'Reflection Final'
    TOOL_PLAN = 'tool_plan', 'Tool Plan'
    TOOL_NOTEBOOK = 'tool_notebook', 'Tool Notebook Entry'
    REFLECTION_ITERATION = 'reflection_iteration', 'Reflection Iteration'


class WorkflowExecutionMessage(models.Model):
    """Individual messages from workflow execution"""
    # Core identification
    execution = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, related_name='messages')
    sequence = models.IntegerField()
    
    # Message content
    agent_name = models.CharField(max_length=100)
    agent_type = models.CharField(max_length=50)
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=WorkflowExecutionMessageType.choices, default=WorkflowExecutionMessageType.CHAT)
    
    # Message metadata
    timestamp = models.DateTimeField()
    response_time_ms = models.IntegerField(default=0)
    token_count = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['execution', 'sequence']
        unique_together = ['execution', 'sequence']
    
    def __str__(self):
        content_preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.agent_name}: {content_preview}"

# Note: AgentWorkflow, SimulationRun, and AgentMessage models are defined above
# in the AGENT ORCHESTRATION MODELS section. This section removes duplicate definitions.


# ============================================================================
# HUMAN INPUT INTERACTION MODEL (UserProxyAgent Implementation - Phase 1)
# ============================================================================

class HumanInputInteraction(models.Model):
    """Tracks individual human input interactions during workflow execution"""
    # Core identification
    execution = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, related_name='human_inputs')
    agent_name = models.CharField(max_length=100, help_text='Name of UserProxyAgent that requested input')
    agent_id = models.CharField(max_length=100, help_text='Node ID of UserProxyAgent in workflow graph')
    
    # Input context from connected agents
    input_messages = models.JSONField(default=list, help_text='Messages from agents connected to this UserProxyAgent')
    conversation_context = models.TextField(blank=True, help_text='Full conversation history at time of human input request')
    aggregated_input_summary = models.TextField(blank=True, help_text='Summary of all input sources for human review')
    
    # Human response
    human_response = models.TextField(help_text='The actual human input/response provided')
    response_timestamp = models.DateTimeField(auto_now_add=True, help_text='When human submitted their response')
    response_time_seconds = models.FloatField(null=True, blank=True, help_text='Time taken for human to respond')
    
    # Request metadata
    requested_at = models.DateTimeField(help_text='When human input was initially requested')
    input_sources_count = models.IntegerField(default=0, help_text='Number of connected agents that provided input')
    workflow_paused_at_sequence = models.IntegerField(default=0, help_text='Sequence number where workflow was paused')
    
    # Processing metadata
    processed_successfully = models.BooleanField(default=True, help_text='Whether human input was processed without errors')
    processing_error = models.TextField(blank=True, help_text='Error message if processing failed')
    workflow_resumed = models.BooleanField(default=False, help_text='Whether workflow was successfully resumed after input')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['execution', 'agent_id']),
            models.Index(fields=['requested_at']),
            models.Index(fields=['response_timestamp']),
        ]
    
    def __str__(self):
        return f"{self.agent_name} - Human Input ({self.response_timestamp.strftime('%H:%M:%S') if self.response_timestamp else 'Pending'})"


# ============================================================================
# WORKFLOW EVALUATION MODELS
# ============================================================================

class EvaluationStatus(models.TextChoices):
    """Status choices for workflow evaluations"""
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class WorkflowEvaluation(models.Model):
    """Stores evaluation run metadata"""
    workflow = models.ForeignKey(AgentWorkflow, on_delete=models.CASCADE, related_name='evaluations')
    evaluation_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    csv_filename = models.CharField(max_length=255)
    total_rows = models.IntegerField()
    completed_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=EvaluationStatus.choices, default=EvaluationStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_by = models.ForeignKey('User', on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workflow', 'status']),
            models.Index(fields=['evaluation_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.workflow.name} - Evaluation {self.evaluation_id.hex[:8]} ({self.status})"


class EvaluationResultStatus(models.TextChoices):
    """Status choices for individual evaluation results"""
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    PENDING = 'pending', 'Pending'


class WorkflowEvaluationResult(models.Model):
    """Stores individual evaluation result for each CSV row"""
    evaluation = models.ForeignKey(WorkflowEvaluation, on_delete=models.CASCADE, related_name='results')
    row_number = models.IntegerField()
    input_text = models.TextField()
    expected_output = models.TextField()
    workflow_output = models.TextField(blank=True, help_text='Aggregated End node input messages')
    execution_id = models.CharField(max_length=100, blank=True, help_text='Reference to WorkflowExecution')
    
    # Metric scores
    rouge_1_score = models.FloatField(null=True, blank=True)
    rouge_2_score = models.FloatField(null=True, blank=True)
    rouge_l_score = models.FloatField(null=True, blank=True)
    bleu_score = models.FloatField(null=True, blank=True)
    bert_score = models.FloatField(null=True, blank=True)
    semantic_similarity = models.FloatField(null=True, blank=True)
    
    # Average score for quick reference
    average_score = models.FloatField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=EvaluationResultStatus.choices, default=EvaluationResultStatus.PENDING)
    error_message = models.TextField(blank=True)
    execution_time_seconds = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['row_number']
        indexes = [
            models.Index(fields=['evaluation', 'row_number']),
            models.Index(fields=['evaluation', 'status']),
            models.Index(fields=['average_score']),
        ]
        unique_together = ['evaluation', 'row_number']
    
    def __str__(self):
        return f"Evaluation {self.evaluation.evaluation_id.hex[:8]} - Row {self.row_number} ({self.status})"
    
    @property
    def formatted_execution_time(self):
        """Get human-readable execution time"""
        if not self.execution_time_seconds:
            return 'N/A'
        
        if self.execution_time_seconds < 60:
            return f"{self.execution_time_seconds:.1f}s"
        elif self.execution_time_seconds < 3600:
            minutes = self.execution_time_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = self.execution_time_seconds / 3600
            return f"{hours:.1f}h"


class ExperimentMetric(models.Model):
    """
    Store experiment metrics for System Performance Analysis
    
    This model stores structured experiment metrics from various system components
    (intelligent delegation, workflow execution, DocAware, etc.) for analysis
    and reporting in the System Performance Analysis page.
    """
    project = models.ForeignKey(IntelliDocProject, on_delete=models.CASCADE, related_name='experiment_metrics')
    experiment_type = models.CharField(
        max_length=50,
        help_text="Type of experiment: intelligent_delegation, workflow_execution, docaware_single, docaware_context"
    )
    metric_data = models.JSONField(
        default=dict,
        help_text="All metric values for this experiment (timing, counts, percentages, etc.)"
    )
    configuration = models.JSONField(
        default=dict,
        help_text="Experiment configuration (delegate count, threshold, agent count, RAG status, etc.)"
    )
    execution_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional: Link to WorkflowExecution if this metric is from a workflow execution"
    )
    evaluation_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional: Link to WorkflowEvaluation if this metric is from an evaluation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'experiment_type', '-created_at']),
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['experiment_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.experiment_type} - {self.project.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
