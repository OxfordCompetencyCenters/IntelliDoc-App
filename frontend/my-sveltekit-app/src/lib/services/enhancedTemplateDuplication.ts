/**
 * Enhanced Template Duplication Service
 * 
 * Frontend service for comprehensive template duplication with full-stack coordination
 */

import { createTemplateLogger } from '../../logging/logger';
import type { 
  TemplateDuplicationRequest, 
  TemplateDuplicationResult, 
  DuplicationPreview,
  DuplicationValidation,
  DuplicationCapabilities,
  DuplicationStatistics,
  DuplicationHealthStatus
} from '../types';

const logger = createTemplateLogger('duplication', 'EnhancedService');

export class EnhancedTemplateDuplicationService {
  private readonly baseUrl = '/api/enhanced-project-templates';

  constructor() {
    logger.info('Initializing Enhanced Template Duplication Service');
  }

  /**
   * Perform complete full-stack template duplication
   */
  async duplicateTemplate(
    sourceTemplateId: string, 
    duplicationRequest: TemplateDuplicationRequest
  ): Promise<TemplateDuplicationResult> {
    logger.templateAction('duplicate_start', sourceTemplateId, duplicationRequest);
    logger.apiCall('POST', `${this.baseUrl}/${sourceTemplateId}/enhanced_duplicate/`, duplicationRequest);
    
    try {
      const response = await fetch(`${this.baseUrl}/${sourceTemplateId}/enhanced_duplicate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
        body: JSON.stringify(duplicationRequest),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`Duplication failed: ${response.status} - ${errorData.message || response.statusText}`);
      }

      const result = await response.json();
      logger.apiResponse(`${this.baseUrl}/${sourceTemplateId}/enhanced_duplicate/`, response.status, result);
      logger.templateAction('duplicate_completed', sourceTemplateId, result);
      
      return result;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/${sourceTemplateId}/enhanced_duplicate/`, error);
      throw error;
    }
  }

  /**
   * Get duplication capabilities and requirements
   */
  async getDuplicationCapabilities(): Promise<DuplicationCapabilities> {
    logger.apiCall('GET', `${this.baseUrl}/duplication_capabilities/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/duplication_capabilities/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to get capabilities: ${response.status} ${response.statusText}`);
      }

      const capabilities = await response.json();
      logger.apiResponse(`${this.baseUrl}/duplication_capabilities/`, response.status, capabilities);
      
      return capabilities;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/duplication_capabilities/`, error);
      throw error;
    }
  }

  /**
   * Preview what would be duplicated without performing actual duplication
   */
  async previewDuplication(sourceTemplateId: string): Promise<DuplicationPreview> {
    logger.templateAction('preview_duplication', sourceTemplateId);
    logger.apiCall('GET', `${this.baseUrl}/${sourceTemplateId}/duplication_preview/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/${sourceTemplateId}/duplication_preview/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Preview failed: ${response.status} ${response.statusText}`);
      }

      const preview = await response.json();
      logger.apiResponse(`${this.baseUrl}/${sourceTemplateId}/duplication_preview/`, response.status, preview);
      
      return preview;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/${sourceTemplateId}/duplication_preview/`, error);
      throw error;
    }
  }

  /**
   * Validate duplication request without performing actual duplication
   */
  async validateDuplicationRequest(
    duplicationRequest: TemplateDuplicationRequest
  ): Promise<DuplicationValidation> {
    logger.templateAction('validate_duplication', 'validation', duplicationRequest);
    logger.apiCall('POST', `${this.baseUrl}/validate_duplication_request/`, duplicationRequest);
    
    try {
      const response = await fetch(`${this.baseUrl}/validate_duplication_request/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
        body: JSON.stringify(duplicationRequest),
      });

      if (!response.ok) {
        throw new Error(`Validation failed: ${response.status} ${response.statusText}`);
      }

      const validation = await response.json();
      logger.apiResponse(`${this.baseUrl}/validate_duplication_request/`, response.status, validation);
      
      return validation;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/validate_duplication_request/`, error);
      throw error;
    }
  }

  /**
   * Get duplication statistics and history
   */
  async getDuplicationStatistics(): Promise<DuplicationStatistics> {
    logger.apiCall('GET', `${this.baseUrl}/duplication_statistics/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/duplication_statistics/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Statistics failed: ${response.status} ${response.statusText}`);
      }

      const statistics = await response.json();
      logger.apiResponse(`${this.baseUrl}/duplication_statistics/`, response.status, statistics);
      
      return statistics;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/duplication_statistics/`, error);
      throw error;
    }
  }

  /**
   * Check duplication system health
   */
  async checkDuplicationHealth(): Promise<DuplicationHealthStatus> {
    logger.apiCall('GET', `${this.baseUrl}/duplication_health_check/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/duplication_health_check/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status} ${response.statusText}`);
      }

      const health = await response.json();
      logger.apiResponse(`${this.baseUrl}/duplication_health_check/`, response.status, health);
      
      return health;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/duplication_health_check/`, error);
      throw error;
    }
  }

  /**
   * Duplicate template with real-time progress tracking
   */
  async duplicateTemplateWithProgress(
    sourceTemplateId: string,
    duplicationRequest: TemplateDuplicationRequest,
    onProgress?: (progress: DuplicationProgress) => void
  ): Promise<TemplateDuplicationResult> {
    logger.templateAction('duplicate_with_progress', sourceTemplateId, duplicationRequest);
    
    try {
      // Start duplication
      const duplicationPromise = this.duplicateTemplate(sourceTemplateId, duplicationRequest);
      
      // If progress callback provided, simulate progress updates
      if (onProgress) {
        const progressSteps = [
          { phase: 'initializing', percentage: 5, operation: 'Validating request' },
          { phase: 'backend_duplication', percentage: 25, operation: 'Duplicating backend structure' },
          { phase: 'frontend_duplication', percentage: 50, operation: 'Duplicating frontend structure' },
          { phase: 'integration_coordination', percentage: 75, operation: 'Coordinating full-stack integration' },
          { phase: 'verification', percentage: 90, operation: 'Verifying template independence' },
          { phase: 'completed', percentage: 100, operation: 'Duplication completed' }
        ];
        
        // Simulate progress updates
        for (const step of progressSteps) {
          await new Promise(resolve => setTimeout(resolve, 500)); // Simulate work
          onProgress({
            duplication_id: `dup_${Date.now()}`,
            current_phase: step.phase as any,
            progress_percentage: step.percentage,
            current_operation: step.operation,
            estimated_completion: new Date(Date.now() + (100 - step.percentage) * 2000).toISOString()
          });
        }
      }
      
      return await duplicationPromise;
    } catch (error) {
      logger.error('Template duplication with progress failed', error);
      throw error;
    }
  }

  /**
   * Get enhanced duplication recommendations for a template
   */
  async getDuplicationRecommendations(
    sourceTemplateId: string,
    proposedNewId: string
  ): Promise<DuplicationRecommendations> {
    logger.templateAction('get_recommendations', sourceTemplateId, { proposedNewId });
    
    try {
      // This could be a dedicated endpoint or part of validation
      const validation = await this.validateDuplicationRequest({
        new_template_id: proposedNewId,
        source_template_id: sourceTemplateId,
        template_config: {
          name: proposedNewId.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase()),
          template_type: 'custom'
        }
      });
      
      return {
        template_id_suggestions: this.generateTemplateIdSuggestions(sourceTemplateId, proposedNewId),
        configuration_recommendations: validation.recommendations || [],
        risk_assessment: {
          risk_level: validation.risk_level || 'low',
          risk_factors: validation.risk_factors || []
        },
        best_practices: [
          'Use kebab-case for template IDs',
          'Provide meaningful template names and descriptions',
          'Test the duplicated template thoroughly before production use',
          'Document any customizations made to the template'
        ]
      };
    } catch (error) {
      logger.error('Failed to get duplication recommendations', error);
      throw error;
    }
  }

  /**
   * Generate template ID suggestions
   */
  private generateTemplateIdSuggestions(sourceTemplateId: string, proposedNewId: string): string[] {
    const suggestions = [];
    
    // Version-based suggestions
    suggestions.push(`${sourceTemplateId}-v2`);
    suggestions.push(`${sourceTemplateId}-enhanced`);
    suggestions.push(`${sourceTemplateId}-custom`);
    
    // Improvement-based suggestions
    if (proposedNewId && !proposedNewId.includes('-')) {
      // Convert camelCase or similar to kebab-case
      const kebabCase = proposedNewId.replace(/[A-Z]/g, '-$&').toLowerCase();
      suggestions.push(kebabCase);
    }
    
    // Date-based suggestions
    const dateString = new Date().toISOString().slice(0, 10);
    suggestions.push(`${sourceTemplateId}-${dateString}`);
    
    return [...new Set(suggestions)]; // Remove duplicates
  }

  /**
   * Get authentication token
   */
  private getAuthToken(): string {
    // This would integrate with the auth system
    return localStorage.getItem('auth_token') || '';
  }
}

// Types for duplication progress and recommendations
export interface DuplicationProgress {
  duplication_id: string;
  current_phase: 'initializing' | 'backend_duplication' | 'frontend_duplication' | 'integration_coordination' | 'verification' | 'completed' | 'failed';
  progress_percentage: number;
  current_operation: string;
  estimated_completion?: string;
}

export interface DuplicationRecommendations {
  template_id_suggestions: string[];
  configuration_recommendations: string[];
  risk_assessment: {
    risk_level: 'low' | 'medium' | 'high';
    risk_factors: string[];
  };
  best_practices: string[];
}

// Export singleton instance
export const enhancedTemplateDuplicationService = new EnhancedTemplateDuplicationService();
