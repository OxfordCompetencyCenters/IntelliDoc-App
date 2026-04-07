// src/lib/services/templateService.ts - PHASE 4: Template Management ONLY
// NO PROJECT OPERATIONS - Templates handle discovery/management only
import api from './api';
import type {
  TemplateInfo,
  CompleteTemplateConfig,
  TemplateDuplicateRequest
} from '$lib/types';

// ✅ PHASE 4: Removed ProjectCreateRequest and IntelliDocProject - no project operations

export interface TemplateListResponse {
  count: number;
  templates: TemplateInfo[];
}

export interface TemplateConfigResponse {
  template_id: string;
  configuration: CompleteTemplateConfig;
}

export interface TemplateDuplicateResponse {
  success: boolean;
  new_template_id: string;
  message: string;
  errors?: string[];
  warnings?: string[];
}

export interface TemplateDiscoveryResponse {
  discovered_count: number;
  synced_count: number;
  templates: string[];
  message: string;
}

export class TemplateService {
  /**
   * ✅ PHASE 4: Template Discovery/Management ONLY
   * NO project operations - templates handle discovery and management only
   */

  /**
   * Load all available templates from folder discovery
   * Template management only - does NOT create projects
   */
  async loadTemplates(): Promise<TemplateInfo[]> {
    try {
      console.log('🔍 Loading templates from folder discovery...');
      const response = await api.get('/enhanced-project-templates/');
      
      // Handle the structured response from backend
      const data: TemplateListResponse = response.data;
      console.log(`✅ Loaded ${data.count} templates:`, data.templates?.map(t => t.id) || []);
      
      // Return the templates array, ensuring it's always an array
      return Array.isArray(data.templates) ? data.templates : [];
    } catch (error) {
      console.error('❌ Failed to load templates:', error);
      throw new Error(`Failed to load templates: ${error.response?.data?.detail || error.message}`);
    }
  }

  /**
   * Force template discovery and refresh cache
   * Template management only - does NOT affect existing projects
   */
  async refreshTemplates(): Promise<TemplateDiscoveryResponse> {
    try {
      console.log('🔄 Refreshing template discovery...');
      const response = await api.get('/enhanced-project-templates/discover/');
      
      const data: TemplateDiscoveryResponse = response.data;
      console.log(`✅ Template refresh completed: ${data.discovered_count} discovered`);
      
      return data;
    } catch (error) {
      console.error('❌ Failed to refresh templates:', error);
      throw new Error(`Failed to refresh templates: ${error.response?.data?.detail || error.message}`);
    }
  }

  /**
   * Get complete template configuration
   * Template discovery only - does NOT create or modify projects
   */
  async getTemplateConfiguration(templateId: string): Promise<CompleteTemplateConfig> {
    try {
      console.log(`🔧 Loading configuration for template: ${templateId}`);
      const response = await api.get(`/enhanced-project-templates/${templateId}/configuration/`);
      
      const data: TemplateConfigResponse = response.data;
      console.log(`✅ Configuration loaded for ${templateId}:`, {
        total_pages: data.configuration.total_pages,
        has_navigation: data.configuration.has_navigation,
        navigation_pages: data.configuration.navigation_pages?.length || 0
      });
      
      return data.configuration;
    } catch (error) {
      console.error(`❌ Failed to load template configuration for ${templateId}:`, error);
      throw new Error(`Failed to load template configuration: ${error.response?.data?.detail || error.message}`);
    }
  }

  /**
   * ❌ PHASE 4: PROJECT CREATION REMOVED
   * Project creation now handled ONLY by cleanUniversalApi.createProject()
   * Templates are for discovery/management only
   */

  /**
   * Duplicate an existing template (admin only)
   * Template management only - does NOT affect existing projects
   */
  async duplicateTemplate(request: TemplateDuplicateRequest): Promise<TemplateDuplicateResponse> {
    try {
      console.log('📋 Duplicating template:', request);
      
      // Validate request
      if (!request.source_template?.trim()) {
        throw new Error('Source template is required');
      }
      if (!request.new_template_id?.trim()) {
        throw new Error('New template ID is required');
      }
      
      const response = await api.post('/enhanced-project-templates/duplicate/', request);
      
      const data: TemplateDuplicateResponse = response.data;
      console.log(`✅ Template duplicated: ${request.source_template} → ${data.new_template_id}`);
      
      return data;
    } catch (error) {
      console.error('❌ Failed to duplicate template:', error);
      throw new Error(`Failed to duplicate template: ${error.response?.data?.detail || error.message}`);
    }
  }

  /**
   * ❌ PHASE 4: PROJECT OPERATIONS REMOVED
   * Project operations now handled ONLY by cleanUniversalApi
   * Templates are for discovery/management only
   */
}

// Export singleton instance
export const templateService = new TemplateService();

// ✅ PHASE 4: Export template discovery/management functions ONLY
// Project operations removed - use cleanUniversalApi instead
export const {
  loadTemplates,
  refreshTemplates,
  getTemplateConfiguration,
  duplicateTemplate
} = templateService;

// ❌ PHASE 4: PROJECT FUNCTIONS REMOVED
// Use cleanUniversalApi.createProject() instead of templateService.createProject()
// Use cleanUniversalApi.getProject() instead of templateService.getProject()

export default templateService;
