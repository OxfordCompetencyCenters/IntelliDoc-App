// src/lib/types.ts

export enum UserRole {
  ADMIN = 'ADMIN',
  STAFF = 'STAFF',
  USER = 'USER'
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  is_active: boolean;
  date_joined: string;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
  duration?: number;
}

export interface DashboardIcon {
  id: number;
  name: string;
  description: string;
  icon_class: string;
  color: string;
  route: string;
  order: number;
  is_active: boolean;
}

export interface UserIconPermission {
  id: number;
  user: number;
  icon: number;
  icon_name: string;
  user_email: string;
  granted_at: string;
}

export interface Group {
  id: number;
  name: string;
}

export interface GroupIconPermission {
  id: number;
  group: number;
  icon: number;
  icon_name: string;
  group_name: string;
  granted_at: string;
}

// Project Permission Types
export interface UserProjectPermission {
  id: number;
  user: number;
  project: number;
  project_name: string;
  user_email: string;
  user_name: string;
  granted_at: string;
}

export interface GroupProjectPermission {
  id: number;
  group: number;
  project: number;
  project_name: string;
  group_name: string;
  granted_at: string;
}

// Template System Types (Phase 1 Enhancement)
export interface TemplateInfo {
  id: string;                    // Folder name (e.g., 'aicc-intellidoc')
  template_type: string;         // Template type identifier
  name: string;                  // Display name
  description: string;           // Template description
  icon_class: string;            // FontAwesome icon class
  color_theme: string;           // Color theme identifier
  analysis_focus: string;        // What this template analyzes
  source: 'folder';              // Always 'folder' for new system
  metadata: TemplateMetadata;    // Complete metadata from folder
}

export interface TemplateMetadata {
  version: string;
  author: string;
  created_date: string;
  features: Record<string, boolean>;
  requirements: {
    min_django_version: string;
    python_packages: string[];
    external_services: string[];
  };
  ui_assets: {
    icon: string;
    logo?: string;
    stylesheet?: string;
  };
}

export interface NavigationPage {
  page_number: number;
  name: string;
  short_name: string;
  icon: string;
  features: string[];        // What features this page includes
}

export interface ProcessingCapabilities {
  supports_ai_analysis: boolean;
  supports_vector_search: boolean;
  max_file_size: number;
  supported_formats: string[];
  ai_models: {
    content_analysis: string;
    embedding_model: string;
  };
}

export interface ValidationRules {
  required_fields: string[];
  max_documents: number;
  allowed_file_types: string[];
}

export interface UIConfiguration {
  layout: string;                    // 'single_page' | 'multi_page_navigation'
  theme: string;                     // Theme identifier
  features: {
    drag_drop_upload: boolean;
    real_time_processing: boolean;
    export_options: boolean;
  };
}

export interface CompleteTemplateConfig {
  // Basic template data
  name: string;
  template_type: string;
  description: string;
  instructions: string;
  suggested_questions: string[];
  required_fields: string[];
  analysis_focus: string;
  icon_class: string;
  color_theme: string;
  
  // Enhanced configuration (5 new fields)
  has_navigation: boolean;
  total_pages: number;
  navigation_pages: NavigationPage[];
  processing_capabilities: ProcessingCapabilities;
  validation_rules: ValidationRules;
  ui_configuration: UIConfiguration;
}

// Project Types with Enhanced Configuration
// ✅ PHASE 4: Projects are INDEPENDENT from templates after creation
export interface IntelliDocProject {
  // Basic project info
  id: string;
  project_id: string;
  name: string;
  description: string;
  created_by: User;
  created_at: string;
  updated_at: string;
  
  // ✅ CLONED template data (complete independence from template files)
  template_name: string;
  template_type: string;
  template_description: string;
  instructions: string;
  suggested_questions: string[];
  required_fields: string[];
  analysis_focus: string;
  icon_class: string;
  color_theme: string;
  
  // ✅ CLONED complete configuration (template independence achieved)
  has_navigation: boolean;
  total_pages: number;
  navigation_pages: NavigationPage[];
  processing_capabilities: ProcessingCapabilities;
  validation_rules: ValidationRules;
  ui_configuration: UIConfiguration;
}

// ✅ PHASE 4: Project creation handled by cleanUniversalApi.createProject()
// Templates only provide discovery - project creation is universal
export interface ProjectCreateRequest {
  name: string;                 // Project name
  description: string;          // Project description
  template_id: string;          // Template folder name (e.g., 'aicc-intellidoc')
}

// ✅ PHASE 4: Template duplication - management function only
// Does NOT affect existing projects
export interface TemplateDuplicateRequest {
  source_template: string;      // Source template folder name
  new_template_id: string;      // New template folder name
  new_name?: string;            // Optional new display name
  new_description?: string;     // Optional new description
  new_author?: string;          // Optional author
}

// LLM Eval Types
export interface LLMProvider {
  id: number;
  name: string;
  provider_type: 'openai' | 'gemini' | 'claude' | 'huggingface';
  api_endpoint: string;
  is_active: boolean;
  default_model: string;
  max_tokens: number;
  timeout_seconds: number;
  created_at: string;
}

export interface APIKeyConfig {
  id: number;
  provider: number;
  key_name: string;
  usage_limit_daily?: number;
  usage_count_today: number;
  is_active: boolean;
  created_at: string;
}

export interface LLMComparison {
  id: number;
  prompt: string;
  title: string;
  created_at: string;
  responses: LLMResponse[];
}

export interface LLMResponse {
  id: number;
  provider_name: string;
  model_name: string;
  response_text: string;
  response_time_ms: number;
  token_count?: number;
  cost_estimate?: number;
  error_message: string;
  created_at: string;
}

export interface LLMComparisonRequest {
  prompt: string;
  title?: string;
  provider_configs: ProviderConfig[];
  temperature?: number;
}

export interface ProviderConfig {
  provider_id: number;
  model_name: string;
}

export interface LLMModel {
  id: string;
  name?: string;
  displayName?: string;
  object?: string;
}

export interface LLMComparisonResult {
  success: boolean;
  comparison?: LLMComparison;
  summary?: {
    total_providers: number;
    successful_responses: number;
    errors: string[];
  };
  error?: string;
}
