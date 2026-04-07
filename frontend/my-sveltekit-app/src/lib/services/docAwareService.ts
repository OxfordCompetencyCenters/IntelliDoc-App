/**
 * DocAware Service
 * ================
 * 
 * Frontend service for DocAware agent configuration and search methods.
 */

import api from './api';

export interface SearchMethodParameter {
  type: 'select' | 'multiselect' | 'number' | 'text' | 'boolean';
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
  description: string;
}

export interface SearchMethod {
  id: string;
  name: string;
  description: string;
  parameters: Record<string, SearchMethodParameter>;
  default_values: Record<string, any>;
  requires_embedding: boolean;
}

export interface SearchMethodsResponse {
  methods: SearchMethod[];
  count: number;
}

export interface ValidationResponse {
  valid: boolean;
  validated_parameters: Record<string, any>;
  method: string;
  error?: string;
}

export interface TestSearchResponse {
  success: boolean;
  query: string;
  method: string;
  results_count: number;
  sample_results: Array<{
    content_preview: string;
    score: number;
    source: string;
    page?: number;
    search_method: string;
  }>;
  parameters_used: Record<string, any>;
  error?: string;
}

export interface CollectionsResponse {
  project_id: string;
  collections: string[];
  count: number;
}

export interface HierarchicalPathItem {
  id: string;
  name: string;
  path: string;
  type: 'folder' | 'file';
  displayName: string;
  isFolder: boolean;
  document_id?: string;
}

export interface HierarchicalPathsResponse {
  project_id: string;
  hierarchical_paths: HierarchicalPathItem[];
  folders_count: number;
  files_count: number;
  total_count: number;
}

class DocAwareService {
  /**
   * Get available search methods
   */
  async getSearchMethods(): Promise<SearchMethodsResponse> {
    try {
      console.log('📚 DOCAWARE SERVICE: Fetching search methods');
      console.log('📚 DOCAWARE SERVICE: API URL:', '/agent-orchestration/docaware/search_methods/');
      
      // FIXED: Remove duplicate /api/ prefix since api.ts already has baseURL with /api
      const response = await api.get('/agent-orchestration/docaware/search_methods/');
      
      console.log('✅ DOCAWARE SERVICE: Raw API response:', response);
      console.log('✅ DOCAWARE SERVICE: Response data:', response.data);
      console.log('✅ DOCAWARE SERVICE: Got search methods count:', response.data.count);
      return response.data;
      
    } catch (error) {
      console.error('❌ DOCAWARE SERVICE: Failed to get search methods:', error);
      console.error('❌ DOCAWARE SERVICE: Error details:', {
        message: error.message,
        response: error.response,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      });
      throw error;
    }
  }
  
  /**
   * Validate search method parameters
   */
  async validateParameters(method: string, parameters: Record<string, any>): Promise<ValidationResponse> {
    try {
      console.log('📚 DOCAWARE SERVICE: Validating parameters for method:', method);
      
      const response = await api.post('/agent-orchestration/docaware/validate_parameters/', {
        method,
        parameters
      });
      
      console.log('✅ DOCAWARE SERVICE: Parameters validated:', response.data.valid);
      return response.data;
      
    } catch (error) {
      console.error('❌ DOCAWARE SERVICE: Parameter validation failed:', error);
      if (error.response?.data) {
        return {
          valid: false,
          validated_parameters: {},
          method,
          error: error.response.data.error || 'Validation failed'
        };
      }
      throw error;
    }
  }
  
  /**
   * Test search functionality with multi-select content filters
   */
  async testSearch(
    projectId: string,
    method: string,
    parameters: Record<string, any>,
    query?: string,
    contentFilters?: string[]
  ): Promise<TestSearchResponse> {
    try {
      console.log('📚 DOCAWARE SERVICE: Testing search for project:', projectId, 'method:', method);

      // CRITICAL FIX: Use meaningful default query instead of hardcoded test query
      const searchQuery = query || 'quarterly business performance analysis and market trends';

      console.log('📚 DOCAWARE SERVICE: Using search query:', searchQuery);
      console.log('📚 DOCAWARE SERVICE: Content filters (array):', contentFilters);

      const response = await api.post('/agent-orchestration/docaware/test_search/', {
        project_id: projectId,
        method,
        parameters,
        query: searchQuery,
        content_filters: contentFilters || []  // Send array instead of string
      });

      console.log('✅ DOCAWARE SERVICE: Search test completed:', response.data.results_count, 'results');
      return response.data;

    } catch (error) {
      console.error('❌ DOCAWARE SERVICE: Search test failed:', error);
      if (error.response?.data) {
        return {
          success: false,
          query: query || 'quarterly business performance analysis and market trends',
          method,
          results_count: 0,
          sample_results: [],
          parameters_used: parameters,
          error: error.response.data.error || 'Search test failed'
        };
      }
      throw error;
    }
  }
  
  /**
   * Get available collections for a project
   */
  async getCollections(projectId: string): Promise<CollectionsResponse> {
    try {
      console.log('📚 DOCAWARE SERVICE: Fetching collections for project:', projectId);

      const response = await api.get('/agent-orchestration/docaware/collections/', {
        params: { project_id: projectId }
      });

      console.log('✅ DOCAWARE SERVICE: Got collections:', response.data.count);
      return response.data;

    } catch (error) {
      console.error('❌ DOCAWARE SERVICE: Failed to get collections:', error);
      throw error;
    }
  }

  /**
   * Get hierarchical paths (folders and files) for content filtering
   */
  async getHierarchicalPaths(projectId: string, includeFiles: boolean = true): Promise<HierarchicalPathsResponse> {
    try {
      console.log('📚 DOCAWARE SERVICE: Fetching hierarchical paths for project:', projectId);
      console.log('📚 DOCAWARE SERVICE: Include files:', includeFiles);

      const response = await api.get('/agent-orchestration/docaware/hierarchical_paths/', {
        params: {
          project_id: projectId,
          include_files: includeFiles
        }
      });

      console.log('✅ DOCAWARE SERVICE: Got hierarchical paths:',
        response.data.folders_count, 'folders,',
        response.data.files_count, 'files');
      return response.data;

    } catch (error) {
      console.error('❌ DOCAWARE SERVICE: Failed to get hierarchical paths:', error);
      throw error;
    }
  }
  
  /**
   * Get default parameters for a search method
   */
  getDefaultParameters(method: SearchMethod): Record<string, any> {
    return { ...method.default_values };
  }
  
  /**
   * Generate parameter input component data
   */
  generateParameterInputs(method: SearchMethod): Array<{
    key: string;
    parameter: SearchMethodParameter;
    defaultValue: any;
  }> {
    const inputs = [];
    
    for (const [key, parameter] of Object.entries(method.parameters)) {
      inputs.push({
        key,
        parameter,
        defaultValue: method.default_values[key]
      });
    }
    
    return inputs.sort((a, b) => {
      // Sort by parameter type priority
      const typePriority = {
        'select': 1,
        'multiselect': 2,
        'number': 3,
        'boolean': 4,
        'text': 5
      };
      
      return (typePriority[a.parameter.type] || 99) - (typePriority[b.parameter.type] || 99);
    });
  }
}

export const docAwareService = new DocAwareService();
