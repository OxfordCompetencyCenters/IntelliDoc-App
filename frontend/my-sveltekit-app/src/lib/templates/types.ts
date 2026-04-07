/**
 * Template-Specific TypeScript Types for Phase 2 Implementation
 * 
 * Defines interfaces for template-specific functionality while ensuring
 * projects remain completely independent through universal interfaces
 */

// Base template interface
export interface BaseTemplate {
  id: string;
  name: string;
  description: string;
  version: string;
  template_type: string;
  icon_class: string;
  color_theme: string;
  independence_level: 'complete' | 'shared';
  backend_endpoints: string[];
  frontend_routes: string[];
}

// AICC-IntelliDoc specific types
export interface AICCIntelliDocTemplate extends BaseTemplate {
  template_type: 'aicc-intellidoc';
  navigation_pages: AICCNavigationPage[];
  processing_capabilities: AICCProcessingCapabilities;
  analysis_focus: string;
  has_navigation: boolean;
  total_pages: number;
}

export interface AICCNavigationPage {
  id: number;
  title: string;
  description: string;
  icon: string;
  route: string;
  features: string[];
}

export interface AICCProcessingCapabilities {
  supports_ai_analysis: boolean;
  supports_document_upload: boolean;
  supports_vector_search: boolean;
  supports_hierarchical_processing: boolean;
  max_file_size: number;
  supported_file_types: string[];
}

// Legal template specific types
export interface LegalTemplate extends BaseTemplate {
  template_type: 'legal';
  legal_document_types: LegalDocumentType[];
  jurisdiction_support: string[];
  compliance_features: LegalComplianceFeature[];
}

export interface LegalDocumentType {
  type: string;
  description: string;
  processing_rules: string[];
}

export interface LegalComplianceFeature {
  feature: string;
  description: string;
  regulations: string[];
}

// Medical template specific types
export interface MedicalTemplate extends BaseTemplate {
  template_type: 'medical';
  medical_document_types: MedicalDocumentType[];
  hipaa_compliance: boolean;
  clinical_features: ClinicalFeature[];
}

export interface MedicalDocumentType {
  type: string;
  description: string;
  privacy_level: 'public' | 'restricted' | 'confidential';
}

export interface ClinicalFeature {
  feature: string;
  description: string;
  medical_standards: string[];
}

// History template specific types
export interface HistoryTemplate extends BaseTemplate {
  template_type: 'history';
  historical_periods: HistoricalPeriod[];
  source_types: HistoricalSourceType[];
  research_methodologies: ResearchMethodology[];
}

export interface HistoricalPeriod {
  period: string;
  start_year: number;
  end_year: number;
  key_themes: string[];
}

export interface HistoricalSourceType {
  type: string;
  description: string;
  authenticity_checks: string[];
}

export interface ResearchMethodology {
  method: string;
  description: string;
  application_areas: string[];
}

// Union type for all templates
export type Template = AICCIntelliDocTemplate | LegalTemplate | MedicalTemplate | HistoryTemplate;

// Template discovery and management types
export interface TemplateDiscoveryResult {
  templates: Template[];
  total_count: number;
  available_types: string[];
  backend_status: 'operational' | 'partial' | 'offline';
}

export interface TemplateDuplicationRequest {
  source_template_id: string;
  new_template_id: string;
  new_template_name: string;
  new_template_description: string;
  copy_frontend: boolean;
  copy_backend: boolean;
  update_references: boolean;
}

export interface TemplateDuplicationResult {
  status: 'success' | 'error';
  new_template_id: string;
  backend_endpoints: string[];
  frontend_routes: string[];
  independence_level: 'complete' | 'shared';
  error_message?: string;
}

// CRITICAL: Universal Project Types (SAME for ALL projects regardless of source template)
export interface UniversalProject {
  // Core project data (cloned from template at creation)
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  
  // Template data snapshot (cloned, not referenced)
  template_name: string;
  template_type: string;
  template_version: string;
  
  // Cloned template configuration (completely independent)
  analysis_focus: string;
  instructions: string;
  suggested_questions: string[];
  icon_class: string;
  color_theme: string;
  has_navigation: boolean;
  total_pages: number;
  navigation_pages: any[];
  processing_capabilities: any;
  validation_rules: any;
  ui_configuration: any;
  
  // Project-specific data
  document_count: number;
  processing_status: 'pending' | 'processing' | 'completed' | 'error';
  last_processed: string | null;
  user_id: string;
}

// Universal project operations (SAME for ALL projects)
export interface UniversalProjectOperations {
  uploadDocuments(projectId: string, files: File[]): Promise<UploadResult>;
  processDocuments(projectId: string): Promise<ProcessingResult>;
  searchDocuments(projectId: string, query: string): Promise<SearchResult>;
  getProjectStatus(projectId: string): Promise<ProjectStatus>;
  deleteProject(projectId: string): Promise<void>;
}

export interface UploadResult {
  status: 'success' | 'error';
  uploaded_files: UploadedFile[];
  total_files: number;
  total_size: number;
  error_message?: string;
}

export interface UploadedFile {
  filename: string;
  size: number;
  type: string;
  upload_status: 'success' | 'error';
  error_message?: string;
}

export interface ProcessingResult {
  status: 'success' | 'processing' | 'error';
  processed_documents: number;
  total_documents: number;
  processing_time: number;
  error_message?: string;
}

export interface SearchResult {
  status: 'success' | 'error';
  results: SearchResultItem[];
  total_results: number;
  search_time: number;
  error_message?: string;
}

export interface SearchResultItem {
  document_id: string;
  document_name: string;
  content_excerpt: string;
  relevance_score: number;
  metadata: any;
}

export interface ProjectStatus {
  project_id: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'error';
  document_count: number;
  last_activity: string;
  health_status: 'healthy' | 'warning' | 'error';
}

// Template management vs Project operations distinction
export interface TemplateManagementOperations {
  discoverTemplates(): Promise<TemplateDiscoveryResult>;
  getTemplateConfiguration(templateId: string): Promise<Template>;
  duplicateTemplate(request: TemplateDuplicationRequest): Promise<TemplateDuplicationResult>;
  deleteTemplate(templateId: string): Promise<void>;
}

// API Service interfaces for template-specific management
export interface TemplateApiService {
  discover(): Promise<TemplateDiscoveryResult>;
  getConfiguration(): Promise<Template>;
  duplicate(request: TemplateDuplicationRequest): Promise<TemplateDuplicationResult>;
  // REMOVED: Project creation - templates are for discovery/management only
}

// Universal Project API Service (SAME for ALL projects)
export interface UniversalProjectApiService {
  getProject(projectId: string): Promise<UniversalProject>;
  updateProject(projectId: string, data: Partial<UniversalProject>): Promise<UniversalProject>;
  uploadDocuments(projectId: string, files: File[]): Promise<UploadResult>;
  processDocuments(projectId: string): Promise<ProcessingResult>;
  searchDocuments(projectId: string, query: string): Promise<SearchResult>;
  getStatus(projectId: string): Promise<ProjectStatus>;
  deleteProject(projectId: string): Promise<void>;
}

// Logging and monitoring types
export interface FrontendLogEvent {
  timestamp: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  component: string;
  message: string;
  data?: any;
}

export interface TemplateMetrics {
  template_id: string;
  usage_count: number;
  project_creation_rate: number;
  average_processing_time: number;
  error_rate: number;
  user_satisfaction: number;
}

export interface ProjectMetrics {
  project_id: string;
  document_processing_count: number;
  search_query_count: number;
  average_response_time: number;
  error_count: number;
  last_activity: string;
}

// Enhanced Template Duplication Types
export interface TemplateDuplicationRequest {
  new_template_id: string;
  source_template_id?: string;
  template_config?: TemplateConfig;
  duplication_options?: DuplicationOptions;
  skip_verification?: boolean;
  enable_rollback?: boolean;
}

export interface TemplateConfig {
  name: string;
  description: string;
  version?: string;
  author?: string;
  template_type: string;
  icon_class?: string;
  color_theme?: string;
  analysis_focus?: string;
  navigation_pages?: NavigationPage[];
  processing_capabilities?: ProcessingCapabilities;
  features?: Record<string, any>;
  ui_configuration?: Record<string, any>;
  validation_rules?: Record<string, any>;
}

export interface DuplicationOptions {
  preserve_metadata?: boolean;
  update_version?: boolean;
  custom_modifications?: Record<string, any>;
  target_environment?: 'development' | 'staging' | 'production';
}

export interface TemplateDuplicationResult {
  source_template: string;
  new_template: string;
  status: 'in_progress' | 'completed' | 'failed' | 'rolled_back';
  backend_results: BackendDuplicationResults;
  frontend_results: FrontendDuplicationResults;
  integration_results: IntegrationResults;
  verification_results: VerificationResults;
  errors: string[];
  warnings: string[];
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  new_template_endpoints?: Record<string, string>;
  next_steps?: string[];
}

export interface BackendDuplicationResults {
  template_directory: boolean;
  definition_file: boolean;
  views_file: boolean;
  serializers_file: boolean;
  urls_file: boolean;
  services_file: boolean;
  components_directory: boolean;
  metadata_file: boolean;
  hierarchical_config: boolean;
  files_updated: string[];
  directories_created: string[];
}

export interface FrontendDuplicationResults {
  routes_directory: boolean;
  template_services: boolean;
  template_components: boolean;
  template_types: boolean;
  selection_page: boolean;
  files_updated: string[];
  directories_created: string[];
}

export interface IntegrationResults {
  django_urls_updated: boolean;
  api_endpoints_registered: boolean;
  frontend_api_services_updated: boolean;
  type_coordination: boolean;
  authentication_flows: boolean;
  integration_verified: boolean;
}

export interface VerificationResults {
  template_isolation: boolean;
  project_independence: boolean;
  file_independence: boolean;
  api_separation: boolean;
  no_cross_dependencies: boolean;
  verification_passed: boolean;
  issues_found: string[];
}

export interface DuplicationPreview {
  source_template: string;
  backend_structure: BackendStructurePreview;
  frontend_structure: FrontendStructurePreview;
  integration_points: string[];
  verification_checks: string[];
  estimated_duration: string;
  complexity_level: 'low' | 'medium' | 'high' | 'very_high';
}

export interface BackendStructurePreview {
  source_exists: boolean;
  files_to_duplicate: string[];
  directories_to_duplicate: string[];
}

export interface FrontendStructurePreview {
  routes_to_duplicate: string[];
  libraries_to_duplicate: string[];
  files_to_update: string[];
}

export interface DuplicationValidation {
  request_valid: boolean;
  validation_errors: string[];
  requirements_check: RequirementsCheck;
  recommendations: string[];
  risk_level?: 'low' | 'medium' | 'high';
  risk_factors?: string[];
}

export interface RequirementsCheck {
  source_template_exists: boolean;
  new_template_id_unique: boolean;
  valid_template_id_format: boolean;
  sufficient_filesystem_permissions: boolean;
  frontend_structure_accessible: boolean;
}

export interface DuplicationCapabilities {
  supported_features: string[];
  backend_duplication: {
    files_duplicated: string[];
    directories_duplicated: string[];
  };
  frontend_duplication: {
    routes_duplicated: string[];
    libraries_duplicated: string[];
    files_updated: string[];
  };
  integration_coordination: string[];
  independence_verification: string[];
  requirements: Record<string, boolean>;
}

export interface DuplicationStatistics {
  total_duplications: number;
  successful_duplications: number;
  failed_duplications: number;
  success_rate: number;
  average_duration_minutes: number;
  most_duplicated_templates: string[];
  recent_duplications: RecentDuplication[];
  duplication_trends: {
    last_30_days: number;
    last_7_days: number;
    today: number;
  };
}

export interface RecentDuplication {
  id: string;
  source_template: string;
  new_template: string;
  status: string;
  created_at: string;
  duration_seconds?: number;
}

export interface DuplicationHealthStatus {
  status: 'healthy' | 'warning' | 'unhealthy';
  checks: Record<string, boolean>;
  warnings: string[];
  last_check: string;
  system_info: {
    duplication_service_version: string;
    supported_template_types: string[];
    max_concurrent_duplications: number;
  };
}

// Enhanced Template Discovery Types
export interface EnhancedTemplateDiscovery {
  templates: EnhancedTemplate[];
  discovery_metadata: DiscoveryMetadata;
  architectural_status: ArchitecturalStatus;
}

export interface EnhancedTemplate extends Template {
  backend_capabilities: BackendCapabilities;
  frontend_capabilities: FrontendCapabilities;
  full_stack_status: 'complete' | 'partial' | 'basic' | 'unknown';
  independence_analysis: IndependenceAnalysis;
  duplication_support: DuplicationSupport;
}

export interface BackendCapabilities {
  has_custom_views: boolean;
  has_custom_serializers: boolean;
  has_custom_urls: boolean;
  has_custom_services: boolean;
  endpoints: {
    custom_views: string[];
    api_patterns: string[];
  };
  architecture_score: number;
}

export interface FrontendCapabilities {
  has_selection_page: boolean;
  has_custom_components: boolean;
  has_api_services: boolean;
  frontend_capabilities: {
    routes: {
      selection_page: string;
      route_files: string[];
    };
    services: {
      api_service: string;
      service_files: string[];
    };
    components: string[];
  };
  ui_completeness_score: number;
}

export interface IndependenceAnalysis {
  independence_level: 'complete' | 'partial' | 'basic' | 'unknown';
  project_isolation: boolean;
  file_independence: boolean;
  api_separation: boolean;
  independence_score: number;
}

export interface DuplicationSupport {
  can_be_duplicated: boolean;
  duplication_complexity: 'low' | 'medium' | 'high';
  estimated_duration_minutes: number;
  requirements_met: boolean;
  blocking_issues: string[];
}

export interface DiscoveryMetadata {
  total_templates: number;
  discovery_timestamp: string;
  discovery_duration_ms: number;
  discovery_method: 'filesystem' | 'database' | 'hybrid';
  cache_status: 'hit' | 'miss' | 'partial';
}

export interface ArchitecturalStatus {
  system_health: 'excellent' | 'good' | 'fair' | 'poor';
  total_templates: number;
  complete_templates: number;
  independent_templates: number;
  template_independence_rate: number;
  full_stack_coverage: number;
  recommendations: string[];
  architectural_score: number;
}
