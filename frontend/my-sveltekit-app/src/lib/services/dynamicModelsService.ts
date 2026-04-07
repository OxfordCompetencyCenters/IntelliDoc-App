/**
 * Dynamic LLM Models Service - API Key Based Frontend Client
 * 
 * Provides client-side functionality for fetching LLM models based on API key availability.
 * No hardcoded fallbacks - only shows models when API keys are configured and working.
 */

import api from './api';

export interface ModelInfo {
  id: string;
  name: string;
  display_name: string;
  provider: string;
  context_length?: number;
  cost_per_1k_tokens?: number;
  capabilities?: string[];
  recommended_for?: string[];
  is_available: boolean;
  last_checked?: string;
}

export interface ProviderStatus {
  provider: string;
  name: string;
  has_api_key: boolean;
  api_key_valid: boolean;
  models_available: boolean;
  message: string;
}

export interface ModelsResponse {
  models: ModelInfo[];
  total_count: number;
  filter_type: string;
  provider_id?: string;
  agent_type?: string;
  provider_statuses?: Record<string, ProviderStatus>;
  api_version: string;
  system_type: string;
  cache_used: boolean;
  force_refresh: boolean;
  requires_api_keys: boolean;
  message?: string;
}

export interface ProviderInfo {
  id: string;
  name: string;
  description: string;
  status: {
    available: boolean;
    has_api_key: boolean;
    api_key_valid: boolean;
    message: string;
    models_count: number;
  };
  models: string[];
}

class DynamicModelsService {
  private cache: Map<string, { data: ModelInfo[]; timestamp: number }> = new Map();
  private readonly CACHE_TTL = 30 * 60 * 1000; // 30 minutes

  /**
   * Get cache key for provider and filters
   */
  private getCacheKey(provider?: string, agentType?: string): string {
    const parts = ['models'];
    if (provider) parts.push(`provider_${provider}`);
    if (agentType) parts.push(`agent_${agentType}`);
    return parts.join('_');
  }

  /**
   * Check if cached data is still valid
   */
  private isCacheValid(timestamp: number): boolean {
    return Date.now() - timestamp < this.CACHE_TTL;
  }

  /**
   * Get models from cache
   */
  private getCachedModels(cacheKey: string): ModelInfo[] | null {
    const cached = this.cache.get(cacheKey);
    if (cached && this.isCacheValid(cached.timestamp)) {
      console.log(`🎯 DYNAMIC MODELS: Retrieved ${cached.data.length} models from frontend cache`);
      return cached.data;
    }
    return null;
  }

  /**
   * Cache models data
   */
  private cacheModels(cacheKey: string, models: ModelInfo[]): void {
    this.cache.set(cacheKey, {
      data: models,
      timestamp: Date.now()
    });
    console.log(`💾 DYNAMIC MODELS: Cached ${models.length} models with key ${cacheKey}`);
  }

  /**
   * Get all available LLM providers with API key status
   */
  async getProviders(): Promise<ProviderInfo[]> {
    try {
      console.log('🤖 DYNAMIC MODELS: Fetching providers with API key status...');
      
      const response = await api.get('/llm/providers/');
      
      console.log('✅ DYNAMIC MODELS: Providers fetched successfully', response.data);
      return response.data.providers || [];
      
    } catch (error) {
      console.error('❌ DYNAMIC MODELS: Failed to fetch providers:', error);
      
      // Return empty array instead of fallback providers
      return [];
    }
  }

  /**
   * Get models for a specific provider or all providers - only if API keys are available
   */
  async getModels(options: {
    providerId?: string;
    agentType?: string;
    useCache?: boolean;
    forceRefresh?: boolean;
  } = {}): Promise<ModelInfo[]> {
    try {
      const {
        providerId,
        agentType,
        useCache = true,
        forceRefresh = false
      } = options;

      console.log(`🤖 DYNAMIC MODELS: Fetching models`, {
        providerId,
        agentType,
        useCache,
        forceRefresh
      });

      // Check cache first (unless force refresh)
      if (!forceRefresh && useCache) {
        const cacheKey = this.getCacheKey(providerId, agentType);
        const cachedModels = this.getCachedModels(cacheKey);
        if (cachedModels) {
          return cachedModels;
        }
      }

      // Build query parameters
      const params = new URLSearchParams();
      if (providerId) params.append('provider_id', providerId);
      if (agentType) params.append('agent_type', agentType);
      if (!useCache) params.append('use_cache', 'false');
      if (forceRefresh) params.append('force_refresh', 'true');

      const response = await api.get(`/llm/models/?${params.toString()}`);
      const data: ModelsResponse = response.data;

      console.log(`✅ DYNAMIC MODELS: Fetched ${data.models.length} models`, {
        filterType: data.filter_type,
        cacheUsed: data.cache_used,
        requiresApiKeys: data.requires_api_keys,
        message: data.message
      });

      // If no models returned due to missing API key, show appropriate message
      if (data.models.length === 0 && data.message) {
        console.warn(`⚠️ DYNAMIC MODELS: ${data.message}`);
      }

      // Cache the results only if we got models
      if (useCache && data.models.length > 0) {
        const cacheKey = this.getCacheKey(providerId, agentType);
        this.cacheModels(cacheKey, data.models);
      }

      return data.models;

    } catch (error) {
      console.error('❌ DYNAMIC MODELS: Failed to fetch models:', error);
      
      // Return empty array instead of fallback models
      return [];
    }
  }

  /**
   * Get models for a specific provider only
   */
  async getModelsForProvider(providerId: string, options: {
    useCache?: boolean;
    forceRefresh?: boolean;
  } = {}): Promise<ModelInfo[]> {
    return this.getModels({
      providerId,
      ...options
    });
  }

  /**
   * Get recommended models for an agent type
   */
  async getRecommendedModelsForAgent(agentType: string, options: {
    useCache?: boolean;
    forceRefresh?: boolean;
  } = {}): Promise<ModelInfo[]> {
    return this.getModels({
      agentType,
      ...options
    });
  }

  /**
   * Get default configuration for an agent type
   */
  async getDefaultAgentConfig(agentType: string): Promise<{
    agent_type: string;
    default_config: {
      llm_provider: string;
      llm_model: string;
      temperature: number;
      max_tokens: number;
    };
    recommended_models: Array<{
      provider: string;
      model: string;
      display_name: string;
      cost_per_1k?: number;
      capabilities: string[];
      reason: string;
    }>;
    available_providers: string[];
    has_valid_providers: boolean;
  }> {
    try {
      console.log(`🎯 DYNAMIC MODELS: Fetching default config for ${agentType}`);
      
      const response = await api.get(`/llm/defaults/${agentType}/`);
      
      console.log(`✅ DYNAMIC MODELS: Default config fetched for ${agentType}`);
      return response.data;
      
    } catch (error) {
      console.error(`❌ DYNAMIC MODELS: Failed to fetch default config for ${agentType}:`, error);
      
      // Return minimal default configuration without API key assumptions
      return {
        agent_type: agentType,
        default_config: {
          llm_provider: 'openai',
          llm_model: 'gpt-4-turbo',
          temperature: 0.7,
          max_tokens: 2048
        },
        recommended_models: [],
        available_providers: [],
        has_valid_providers: false
      };
    }
  }

  /**
   * Get provider status information
   */
  async getProviderStatus(providerId: string): Promise<ProviderStatus> {
    try {
      const providers = await this.getProviders();
      const provider = providers.find(p => p.id === providerId);
      
      if (provider) {
        return {
          provider: provider.id,
          name: provider.name,
          has_api_key: provider.status.has_api_key,
          api_key_valid: provider.status.api_key_valid,
          models_available: provider.status.available,
          message: provider.status.message
        };
      }
      
      return {
        provider: providerId,
        name: providerId,
        has_api_key: false,
        api_key_valid: false,
        models_available: false,
        message: 'Provider not found'
      };
      
    } catch (error) {
      console.error(`❌ DYNAMIC MODELS: Failed to get provider status for ${providerId}:`, error);
      
      return {
        provider: providerId,
        name: providerId,
        has_api_key: false,
        api_key_valid: false,
        models_available: false,
        message: 'Failed to check provider status'
      };
    }
  }

  /**
   * Get no-API-key message for provider dropdown
   */
  getNoApiKeyMessage(providerId: string): string {
    const providerNames = {
      'openai': 'OpenAI',
      'anthropic': 'Anthropic',
      'google': 'Google AI',
      'ollama': 'Ollama (Local)'
    };
    
    const providerName = providerNames[providerId as keyof typeof providerNames] || providerId;
    return `${providerName} API key not configured`;
  }

  /**
   * Clear cache for specific provider or all providers
   */
  clearCache(providerId?: string, agentType?: string): void {
    if (providerId || agentType) {
      const cacheKey = this.getCacheKey(providerId, agentType);
      this.cache.delete(cacheKey);
      console.log(`🧹 DYNAMIC MODELS: Cleared cache for key ${cacheKey}`);
    } else {
      this.cache.clear();
      console.log('🧹 DYNAMIC MODELS: Cleared all model caches');
    }
  }

  /**
   * Get cache statistics for debugging
   */
  getCacheStats(): {
    totalEntries: number;
    validEntries: number;
    expiredEntries: number;
    cacheKeys: string[];
  } {
    const totalEntries = this.cache.size;
    let validEntries = 0;
    let expiredEntries = 0;
    const cacheKeys: string[] = [];

    for (const [key, value] of this.cache.entries()) {
      cacheKeys.push(key);
      if (this.isCacheValid(value.timestamp)) {
        validEntries++;
      } else {
        expiredEntries++;
      }
    }

    return {
      totalEntries,
      validEntries,
      expiredEntries,
      cacheKeys
    };
  }

  /**
   * Test if any providers have valid API keys
   */
  async hasAnyValidApiKeys(): Promise<boolean> {
    try {
      const providers = await this.getProviders();
      return providers.some(provider => provider.status.api_key_valid);
    } catch (error) {
      console.error('❌ DYNAMIC MODELS: Failed to check API key status:', error);
      return false;
    }
  }

  /**
   * Get all providers with valid API keys
   */
  async getProvidersWithValidApiKeys(): Promise<ProviderInfo[]> {
    try {
      const providers = await this.getProviders();
      return providers.filter(provider => provider.status.api_key_valid);
    } catch (error) {
      console.error('❌ DYNAMIC MODELS: Failed to get providers with valid API keys:', error);
      return [];
    }
  }
}

// Export singleton instance
export const dynamicModelsService = new DynamicModelsService();
export default dynamicModelsService;
