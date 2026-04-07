/**
 * Enhanced Template Router - Phase 3 Frontend
 * ============================================
 * 
 * Comprehensive frontend routing service for template discovery,
 * navigation, and dynamic route generation with full logging.
 */

import { createUniversalLogger } from '../logging/logger';
import type { 
  Template,
  TemplateDiscoveryResult,
  TemplateDuplicationRequest,
  TemplateDuplicationResult,
  UniversalProject
} from '../templates/types';

const logger = createUniversalLogger('TemplateRouter');

export interface TemplateRouteInfo {
  template_id: string;
  selection_route: string;
  project_creation_api: string;
  universal_project_route: string;
  backend_endpoints: string[];
  frontend_capabilities: any;
  independence_level: 'complete' | 'partial' | 'basic';
}

export interface RoutingDecision {
  destination_route: string;
  route_type: 'template_selection' | 'universal_project' | 'template_management';
  template_id?: string;
  project_id?: string;
  reasoning: string;
}

export class EnhancedTemplateRouter {
  private readonly baseApiUrl = '/api/enhanced-project-templates';
  private routingCache = new Map<string, TemplateRouteInfo>();
  private cacheTimeout = 30 * 60 * 1000; // 30 minutes
  private lastCacheUpdate = 0;

  constructor() {
    logger.info('Initializing Enhanced Template Router for Phase 3');
    this.initializeRouting();
  }

  private async initializeRouting() {
    logger.info('Initializing template routing system');
    
    try {
      await this.refreshRoutingCache();
      logger.info('Template routing system initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize template routing system', error);
    }
  }

  /**
   * Enhanced template discovery with comprehensive capabilities
   */
  async discoverTemplates(forceRefresh = false): Promise<TemplateDiscoveryResult> {
    logger.info('Starting enhanced template discovery');
    logger.info(`Force refresh: ${forceRefresh}`);

    try {
      const params = new URLSearchParams({
        force_refresh: forceRefresh.toString(),
        include_metadata: 'true',
        include_architectural_status: 'true'
      });

      const response = await fetch(`${this.baseApiUrl}/enhanced_discover/?${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Discovery failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      logger.info(`Enhanced discovery completed: ${result.templates?.length || 0} templates found`);
      logger.info(`Discovery method: ${result.discovery_method}`);

      // Update routing cache with discovery results
      if (result.templates) {
        this.updateRoutingCacheFromDiscovery(result.templates);
      }

      return result;
    } catch (error) {
      logger.error('Enhanced template discovery failed', error);
      throw error;
    }
  }

  /**
   * Get comprehensive routing information for a template
   */
  async getTemplateRoutingInfo(templateId: string): Promise<TemplateRouteInfo> {
    logger.info(`Getting routing info for template: ${templateId}`);

    // Check cache first
    const cached = this.routingCache.get(templateId);
    if (cached && this.isCacheValid()) {
      logger.info(`Returning cached routing info for template: ${templateId}`);
      return cached;
    }

    try {
      const response = await fetch(`${this.baseApiUrl}/${templateId}/routing_info/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Routing info failed: ${response.status} ${response.statusText}`);
      }

      const routingInfo = await response.json();
      logger.info(`Routing info retrieved for template: ${templateId}`);

      // Transform to our interface
      const templateRouteInfo: TemplateRouteInfo = {
        template_id: templateId,
        selection_route: `/features/${templateId}/`,
        project_creation_api: routingInfo.navigation?.project_creation_api || `/api/templates/${templateId}/projects/`,
        universal_project_route: routingInfo.navigation?.universal_project_interface || '/features/intellidoc/project/{id}/',
        backend_endpoints: routingInfo.backend_routes?.endpoints || [],
        frontend_capabilities: routingInfo.frontend_routes || {},
        independence_level: this.determineIndependenceLevel(routingInfo)
      };

      // Cache the result
      this.routingCache.set(templateId, templateRouteInfo);
      logger.info(`Cached routing info for template: ${templateId}`);

      return templateRouteInfo;
    } catch (error) {
      logger.error(`Failed to get routing info for template ${templateId}`, error);
      throw error;
    }
  }

  /**
   * Make intelligent routing decisions
   */
  makeRoutingDecision(
    action: 'select_template' | 'create_project' | 'access_project' | 'manage_template',
    templateId?: string,
    projectId?: string
  ): RoutingDecision {
    logger.info(`Making routing decision: ${action}`, { templateId, projectId });

    let decision: RoutingDecision;

    switch (action) {
      case 'select_template':
        if (!templateId) {
          throw new Error('Template ID required for template selection');
        }
        decision = {
          destination_route: `/features/${templateId}/`,
          route_type: 'template_selection',
          template_id: templateId,
          reasoning: `Navigate to template-specific selection page for ${templateId}`
        };
        break;

      case 'create_project':
        if (!templateId) {
          throw new Error('Template ID required for project creation');
        }
        decision = {
          destination_route: `/features/${templateId}/`,
          route_type: 'template_selection',
          template_id: templateId,
          reasoning: `Navigate to template selection page where user can create project from ${templateId}`
        };
        break;

      case 'access_project':
        if (!projectId) {
          throw new Error('Project ID required for project access');
        }
        decision = {
          destination_route: `/features/intellidoc/project/${projectId}/`,
          route_type: 'universal_project',
          project_id: projectId,
          reasoning: `Navigate to universal project interface (template-independent) for project ${projectId}`
        };
        break;

      case 'manage_template':
        if (!templateId) {
          throw new Error('Template ID required for template management');
        }
        decision = {
          destination_route: `/features/${templateId}/`,
          route_type: 'template_management',
          template_id: templateId,
          reasoning: `Navigate to template management interface for ${templateId}`
        };
        break;

      default:
        throw new Error(`Unknown routing action: ${action}`);
    }

    logger.info('Routing decision made', decision);
    return decision;
  }

  /**
   * Navigate to template selection page
   */
  async navigateToTemplate(templateId: string): Promise<void> {
    logger.templateNavigation('navigation_start', 'template_selection', templateId);

    try {
      const decision = this.makeRoutingDecision('select_template', templateId);
      
      // Import goto dynamically to avoid SSR issues
      const { goto } = await import('$app/navigation');
      
      logger.templateNavigation('navigation_execute', 'template_selection', templateId, {
        destination: decision.destination_route,
        reasoning: decision.reasoning
      });

      await goto(decision.destination_route);
      
      logger.templateNavigation('navigation_complete', 'template_selection', templateId);
    } catch (error) {
      logger.error(`Failed to navigate to template ${templateId}`, error);
      throw error;
    }
  }

  /**
   * Navigate to universal project interface (template-independent)
   */
  async navigateToProject(projectId: string): Promise<void> {
    logger.projectAction('navigation_start', projectId);

    try {
      const decision = this.makeRoutingDecision('access_project', undefined, projectId);
      
      // Import goto dynamically to avoid SSR issues
      const { goto } = await import('$app/navigation');
      
      logger.projectAction('navigation_execute', projectId, {
        destination: decision.destination_route,
        reasoning: decision.reasoning
      });

      await goto(decision.destination_route);
      
      logger.projectAction('navigation_complete', projectId);
    } catch (error) {
      logger.error(`Failed to navigate to project ${projectId}`, error);
      throw error;
    }
  }

  /**
   * Create project from template and navigate to universal project interface
   */
  async createProjectAndNavigate(
    templateId: string, 
    projectData: Partial<UniversalProject>
  ): Promise<UniversalProject> {
    logger.templateAction('create_and_navigate_start', templateId, projectData);

    try {
      // Get template routing info to find the correct API endpoint
      const routingInfo = await this.getTemplateRoutingInfo(templateId);
      
      logger.apiCall('POST', routingInfo.project_creation_api, projectData);

      const response = await fetch(routingInfo.project_creation_api, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
        body: JSON.stringify(projectData),
      });

      if (!response.ok) {
        throw new Error(`Project creation failed: ${response.status} ${response.statusText}`);
      }

      const newProject = await response.json();
      logger.apiResponse(routingInfo.project_creation_api, response.status, newProject);
      logger.templateAction('project_created', templateId, newProject);

      // Navigate to universal project interface
      await this.navigateToProject(newProject.id);
      
      logger.templateAction('create_and_navigate_complete', templateId, newProject);
      return newProject;
    } catch (error) {
      logger.error(`Failed to create project from template ${templateId}`, error);
      throw error;
    }
  }

  /**
   * Validate template registration status
   */
  async validateTemplateRegistration(templateId: string): Promise<any> {
    logger.info(`Validating template registration: ${templateId}`);

    try {
      const response = await fetch(`${this.baseApiUrl}/${templateId}/validate_registration/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Validation failed: ${response.status} ${response.statusText}`);
      }

      const validation = await response.json();
      logger.info(`Template registration validation completed for ${templateId}: ${validation.validation_status}`);

      return validation;
    } catch (error) {
      logger.error(`Failed to validate template registration for ${templateId}`, error);
      throw error;
    }
  }

  /**
   * Get architectural status of template system
   */
  async getArchitecturalStatus(): Promise<any> {
    logger.info('Getting architectural status');

    try {
      const response = await fetch(`${this.baseApiUrl}/architectural_status/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Architectural status failed: ${response.status} ${response.statusText}`);
      }

      const status = await response.json();
      logger.info('Architectural status retrieved successfully');

      return status;
    } catch (error) {
      logger.error('Failed to get architectural status', error);
      throw error;
    }
  }

  /**
   * Compare template capabilities
   */
  async compareTemplates(): Promise<any> {
    logger.info('Getting template comparison data');

    try {
      const response = await fetch(`${this.baseApiUrl}/template_comparison/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Template comparison failed: ${response.status} ${response.statusText}`);
      }

      const comparison = await response.json();
      logger.info(`Template comparison completed for ${Object.keys(comparison.template_summary || {}).length} templates`);

      return comparison;
    } catch (error) {
      logger.error('Failed to get template comparison', error);
      throw error;
    }
  }

  /**
   * Refresh discovery cache
   */
  async refreshDiscoveryCache(): Promise<void> {
    logger.info('Refreshing discovery cache');

    try {
      const response = await fetch(`${this.baseApiUrl}/refresh_discovery_cache/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Cache refresh failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      logger.info(`Discovery cache refreshed successfully: ${result.templates_rediscovered} templates rediscovered`);

      // Clear local routing cache
      this.routingCache.clear();
      this.lastCacheUpdate = 0;
    } catch (error) {
      logger.error('Failed to refresh discovery cache', error);
      throw error;
    }
  }

  // Private helper methods

  private updateRoutingCacheFromDiscovery(templates: any[]) {
    logger.info(`Updating routing cache from discovery: ${templates.length} templates`);

    for (const template of templates) {
      const routeInfo: TemplateRouteInfo = {
        template_id: template.template_id,
        selection_route: `/features/${template.template_id}/`,
        project_creation_api: `/api/templates/${template.template_id}/projects/`,
        universal_project_route: '/features/intellidoc/project/{id}/',
        backend_endpoints: template.capabilities?.backend?.endpoints?.custom_views || [],
        frontend_capabilities: template.capabilities?.frontend || {},
        independence_level: template.capabilities?.independence_level || 'basic'
      };

      this.routingCache.set(template.template_id, routeInfo);
    }

    this.lastCacheUpdate = Date.now();
    logger.info(`Routing cache updated with ${templates.length} templates`);
  }

  private async refreshRoutingCache() {
    logger.info('Refreshing routing cache');

    try {
      const discovery = await this.discoverTemplates(false);
      
      if (discovery.templates) {
        this.updateRoutingCacheFromDiscovery(discovery.templates);
      }
    } catch (error) {
      logger.warning('Failed to refresh routing cache during initialization', error);
    }
  }

  private isCacheValid(): boolean {
    const now = Date.now();
    const isValid = (now - this.lastCacheUpdate) < this.cacheTimeout;
    
    if (!isValid) {
      logger.info('Routing cache is stale, will refresh');
    }
    
    return isValid;
  }

  private determineIndependenceLevel(routingInfo: any): 'complete' | 'partial' | 'basic' {
    const hasBackendEndpoints = routingInfo.backend_routes?.endpoints?.length > 0;
    const hasFrontendRoutes = routingInfo.frontend_routes?.has_selection_page;
    const hasCustomViews = routingInfo.backend_routes?.view_classes?.length > 0;

    if (hasBackendEndpoints && hasFrontendRoutes && hasCustomViews) {
      return 'complete';
    } else if (hasBackendEndpoints || hasFrontendRoutes) {
      return 'partial';
    } else {
      return 'basic';
    }
  }

  private getAuthToken(): string {
    // Check localStorage first (for browser environment)
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
      if (token) {
        return token;
      }
    }
    
    // Fallback to empty string - auth middleware will handle
    return '';
  }
}

// Export singleton instance for use across the application
export const enhancedTemplateRouter = new EnhancedTemplateRouter();

// Note: Class is already exported above - no need to re-export
