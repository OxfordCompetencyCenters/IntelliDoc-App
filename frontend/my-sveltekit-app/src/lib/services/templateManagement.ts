// src/lib/services/templateManagement.ts
// Template Management API Service

import { get } from 'svelte/store';
import authStore from '$lib/stores/auth';

const API_BASE = '/api';

interface Template {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  created_date?: string;
  template_type: string;
  icon_class?: string;
  color_theme?: string;
}

interface TemplateDuplicationRequest {
  source_template: string;
  new_template_id: string;
  new_name: string;
  new_description: string;
  version: string;
  author: string;
}

interface TemplateDuplicationResponse {
  success: boolean;
  new_template_id?: string;
  message: string;
  errors: string[];
}

class TemplateManagementService {
  private getAuthHeaders() {
    const auth = get(authStore);
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${auth?.token}`
    };
  }

  /**
   * Get all available templates for duplication
   */
  async getAvailableTemplates(): Promise<Template[]> {
    try {
      const response = await fetch(`${API_BASE}/enhanced-project-templates/`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch templates: ${response.status}`);
      }

      const data = await response.json();
      return data.templates || [];
    } catch (error) {
      console.error('❌ Failed to fetch templates:', error);
      throw error;
    }
  }

  /**
   * Duplicate a template with new configuration
   */
  async duplicateTemplate(request: TemplateDuplicationRequest): Promise<TemplateDuplicationResponse> {
    try {
      console.log('🔄 Duplicating template:', request);
      
      const response = await fetch(`${API_BASE}/enhanced-project-templates/duplicate/`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(request)
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || `Template duplication failed: ${response.status}`);
      }

      console.log('✅ Template duplication response:', data);
      return data;
    } catch (error) {
      console.error('❌ Template duplication failed:', error);
      throw error;
    }
  }

  /**
   * Get template configuration for a specific template
   */
  async getTemplateConfiguration(templateId: string): Promise<any> {
    try {
      const response = await fetch(`${API_BASE}/enhanced-project-templates/${templateId}/configuration/`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch template configuration: ${response.status}`);
      }

      const data = await response.json();
      return data.configuration || {};
    } catch (error) {
      console.error(`❌ Failed to fetch template configuration for ${templateId}:`, error);
      throw error;
    }
  }

  /**
   * Validate template ID format
   */
  validateTemplateId(templateId: string): { valid: boolean; error?: string } {
    if (!templateId || templateId.trim().length === 0) {
      return { valid: false, error: 'Template ID is required' };
    }

    if (!/^[a-z0-9-]+$/.test(templateId)) {
      return { valid: false, error: 'Template ID must contain only lowercase letters, numbers, and hyphens' };
    }

    if (templateId.startsWith('-') || templateId.endsWith('-')) {
      return { valid: false, error: 'Template ID cannot start or end with hyphen' };
    }

    if (templateId.includes('--')) {
      return { valid: false, error: 'Template ID cannot contain consecutive hyphens' };
    }

    return { valid: true };
  }

  /**
   * Generate template ID from name
   */
  generateTemplateId(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '') // Remove special characters
      .replace(/\s+/g, '-') // Replace spaces with hyphens
      .replace(/-+/g, '-') // Replace multiple hyphens with single
      .replace(/^-|-$/g, ''); // Remove leading/trailing hyphens
  }

  /**
   * Validate semantic version format
   */
  validateVersion(version: string): { valid: boolean; error?: string } {
    if (!version || version.trim().length === 0) {
      return { valid: false, error: 'Version is required' };
    }

    if (!/^\d+\.\d+\.\d+$/.test(version)) {
      return { valid: false, error: 'Version must be in format X.Y.Z (e.g., 1.0.0)' };
    }

    return { valid: true };
  }

  /**
   * Check if template ID already exists
   */
  async checkTemplateIdExists(templateId: string, availableTemplates?: Template[]): Promise<boolean> {
    try {
      const templates = availableTemplates || await this.getAvailableTemplates();
      return templates.some(template => template.id === templateId);
    } catch (error) {
      console.error('❌ Failed to check template ID existence:', error);
      return false; // Assume doesn't exist if can't check
    }
  }

  /**
   * Get template icon class based on template type
   */
  getTemplateIcon(template: Template): string {
    if (template.icon_class) return template.icon_class;

    switch (template.template_type) {
      case 'aicc-intellidoc':
        return 'fa-brain';
      case 'legal':
        return 'fa-balance-scale';
      case 'medical':
        return 'fa-user-md';
      case 'history':
        return 'fa-university';
      default:
        return 'fa-file-alt';
    }
  }

  /**
   * Format date for display
   */
  formatDate(dateString?: string): string {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }

  /**
   * Get template type display name
   */
  getTemplateTypeDisplayName(templateType: string): string {
    switch (templateType) {
      case 'aicc-intellidoc':
        return 'AICC IntelliDoc';
      case 'legal':
        return 'Legal Documents';
      case 'medical':
        return 'Medical Records';
      case 'history':
        return 'Historical Analysis';
      default:
        return templateType.split('-').map(word => 
          word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }
  }
}

// Export singleton instance
export const templateManagement = new TemplateManagementService();

// Export types
export type { 
  Template, 
  TemplateDuplicationRequest, 
  TemplateDuplicationResponse 
};
