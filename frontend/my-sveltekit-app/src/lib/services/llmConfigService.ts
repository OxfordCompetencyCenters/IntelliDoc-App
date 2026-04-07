// LLM Configuration Service - Template Independent Agent LLM Management
import {
  type LLMProvider,
  type LLMModel,
  type AgentLLMConfig,
  DEFAULT_LLM_PROVIDERS,
  DEFAULT_LLM_MODELS,
  DEFAULT_AGENT_LLM_CONFIGS,
  getProviderIcon
} from '$lib/types/llm-config';
import dynamicModelsService, {
  type ModelInfo,
  type ProviderInfo
} from '$lib/services/dynamicModelsService';

class LLMConfigurationService {
  private baseUrl = '/api';

  constructor() {
    console.log('🤖 LLM CONFIG: Service initialized');
  }

  /**
   * Get all available LLM providers
   */
  async getProviders(): Promise<LLMProvider[]> {
    try {
      console.log('📋 LLM CONFIG: Fetching LLM providers (dynamic)');

      // Prefer dynamic, API-key-aware providers from backend
      const dynamicProviders: ProviderInfo[] = await dynamicModelsService.getProviders();

      if (dynamicProviders && dynamicProviders.length > 0) {
        const mappedProviders: LLMProvider[] = dynamicProviders.map((provider) => {
          // Try to enrich from defaults if we have a matching entry
          const defaultDef = DEFAULT_LLM_PROVIDERS.find((p: LLMProvider) => p.id === provider.id);

          return {
            id: provider.id,
            name: provider.name,
            description: provider.description,
            icon: defaultDef?.icon || getProviderIcon(provider.id),
            // Cast is safe because backend only returns known providers today
            type: (provider.id as any) ?? 'custom',
            baseUrl: defaultDef?.baseUrl,
            apiKeyRequired: true,
            supportedFeatures: defaultDef?.supportedFeatures || ['chat', 'completion']
          };
        });

        console.log(`✅ LLM CONFIG: Loaded ${mappedProviders.length} providers from dynamicModelsService`);
        return mappedProviders;
      }

      // Fallback: static defaults (no API key awareness)
      console.warn('⚠️ LLM CONFIG: dynamicModelsService returned no providers, falling back to DEFAULT_LLM_PROVIDERS');
      return DEFAULT_LLM_PROVIDERS;
      
    } catch (error) {
      console.error('❌ LLM CONFIG: Failed to load providers:', error);
      // Fallback to default providers
      return DEFAULT_LLM_PROVIDERS;
    }
  }

  /**
   * Get all available LLM models
   */
  async getModels(providerId?: string): Promise<LLMModel[]> {
    try {
      console.log('📋 LLM CONFIG: Fetching LLM models (dynamic only)', { providerId });

      // Prefer dynamic, API-key aware models from backend
      const dynamicModels: ModelInfo[] = await dynamicModelsService.getModels({
        providerId,
        useCache: true,
        forceRefresh: false
      });

      const models: LLMModel[] = (dynamicModels || []).map((model) => {
        const costPer1k = model.cost_per_1k_tokens ?? 0.01;
        const context = model.context_length ?? 8192;

        return {
          id: model.id,
          name: model.display_name || model.name,
          providerId: model.provider,
          description: model.display_name || model.name,
          maxTokens: context,
          supportsStreaming: true,
          supportsFunctionCalling: (model.capabilities || []).includes('function-calling'),
          costPerToken: costPer1k / 1000,
          contextWindow: context,
          capabilities: model.capabilities || []
        };
      });

      // Filter by provider if specified
      if (providerId) {
        models = models.filter((model) => model.providerId === providerId);
      }

      console.log(`✅ LLM CONFIG: Loaded ${models.length} models for provider ${providerId || 'ALL'} (dynamic)`);
      return models;
      
    } catch (error) {
      console.error('❌ LLM CONFIG: Failed to load models:', error);
      // If dynamic loading fails we return an empty list so the UI
      // can clearly surface that no models are available for this
      // project/API key instead of silently falling back to a tiny
      // hard-coded default list.
      return [];
    }
  }

  /**
   * Get LLM configuration for a specific agent.
   *
   * Agent LLM config is persisted in the workflow graph (node.data.llm_provider, node.data.llm_model).
   * When nodeDataFromGraph is provided (e.g. from the selected workflow's node), returns config from it.
   * Otherwise returns null so callers use defaults (e.g. in NodePropertiesPanel, nodeConfig is bound
   * directly to node.data and is persisted when the workflow is saved).
   *
   * @param projectId - Project ID (for future backend API if added)
   * @param agentId - Agent/node ID
   * @param nodeDataFromGraph - Optional node.data from the workflow graph (source of truth for persistence)
   */
  async getAgentLLMConfig(
    projectId: string,
    agentId: string,
    nodeDataFromGraph?: { llm_provider?: string; llm_model?: string; [key: string]: unknown }
  ): Promise<AgentLLMConfig | null> {
    try {
      console.log('🎯 LLM CONFIG: Fetching agent LLM config', { projectId, agentId });
      
      if (nodeDataFromGraph && (nodeDataFromGraph.llm_provider || nodeDataFromGraph.llm_model)) {
        const defaults = this.getDefaultConfigForAgentType('AssistantAgent') || {};
        return {
          agentId,
          agentName: '',
          providerId: nodeDataFromGraph.llm_provider || (defaults.providerId as string) || 'openai',
          modelId: nodeDataFromGraph.llm_model || (defaults.modelId as string) || 'gpt-4',
          temperature: (defaults.temperature as number) ?? 0.7,
          maxTokens: (defaults.maxTokens as number) ?? 2048,
          topP: (defaults.topP as number) ?? 1.0,
          frequencyPenalty: (defaults.frequencyPenalty as number) ?? 0,
          presencePenalty: (defaults.presencePenalty as number) ?? 0
        };
      }
      return null;
    } catch (error) {
      console.error('❌ LLM CONFIG: Failed to load agent config:', error);
      return null;
    }
  }

  /**
   * Update LLM configuration for a specific agent.
   *
   * Persistence: There is no separate backend API for per-agent LLM config. Config is stored in the
   * workflow graph (node.data.llm_provider, node.data.llm_model). Callers in the workflow designer
   * should update the node's data and then save the workflow to persist. This method returns the
   * config for in-memory use; the actual persistence happens when the workflow is saved.
   */
  async updateAgentLLMConfig(projectId: string, agentId: string, config: AgentLLMConfig): Promise<AgentLLMConfig> {
    try {
      console.log('💾 LLM CONFIG: Updating agent LLM config (persist by saving workflow)', { projectId, agentId });
      return config;
    } catch (error) {
      console.error('❌ LLM CONFIG: Failed to update agent config:', error);
      throw error;
    }
  }

  /**
   * Get default LLM configuration for an agent type
   */
  getDefaultConfigForAgentType(agentType: string): Partial<AgentLLMConfig> {
    const defaultConfig = DEFAULT_AGENT_LLM_CONFIGS[agentType];
    
    if (defaultConfig) {
      console.log(`🎯 LLM CONFIG: Using default config for ${agentType}`);
      return defaultConfig;
    }
    
    console.log(`⚠️ LLM CONFIG: No default config for ${agentType}, using AssistantAgent defaults`);
    return DEFAULT_AGENT_LLM_CONFIGS['AssistantAgent'];
  }

  /**
   * Get a complete LLM configuration with defaults filled in
   */
  getCompleteAgentConfig(
    agentId: string,
    agentName: string,
    agentType: string,
    partialConfig?: Partial<AgentLLMConfig>
  ): AgentLLMConfig {
    const defaults = this.getDefaultConfigForAgentType(agentType);
    
    return {
      agentId,
      agentName,
      providerId: partialConfig?.providerId || defaults.providerId || 'openai',
      modelId: partialConfig?.modelId || defaults.modelId || 'gpt-4',
      temperature: partialConfig?.temperature ?? defaults.temperature ?? 0.7,
      maxTokens: partialConfig?.maxTokens || defaults.maxTokens || 2048,
      topP: partialConfig?.topP ?? defaults.topP ?? 1.0,
      frequencyPenalty: partialConfig?.frequencyPenalty ?? defaults.frequencyPenalty ?? 0.0,
      presencePenalty: partialConfig?.presencePenalty ?? defaults.presencePenalty ?? 0.0,
      customConfig: partialConfig?.customConfig || defaults.customConfig || {},
      systemMessage: partialConfig?.systemMessage || defaults.systemMessage
    };
  }

  /**
   * Validate LLM configuration
   */
  validateConfig(config: AgentLLMConfig): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!config.agentId) {
      errors.push('Agent ID is required');
    }

    if (!config.agentName) {
      errors.push('Agent name is required');
    }

    if (!config.providerId) {
      errors.push('LLM provider is required');
    }

    if (!config.modelId) {
      errors.push('LLM model is required');
    }

    if (config.temperature < 0 || config.temperature > 2) {
      errors.push('Temperature must be between 0 and 2');
    }

    if (config.maxTokens < 1 || config.maxTokens > 32000) {
      errors.push('Max tokens must be between 1 and 32000');
    }

    if (config.topP < 0 || config.topP > 1) {
      errors.push('Top P must be between 0 and 1');
    }

    if (config.frequencyPenalty < -2 || config.frequencyPenalty > 2) {
      errors.push('Frequency penalty must be between -2 and 2');
    }

    if (config.presencePenalty < -2 || config.presencePenalty > 2) {
      errors.push('Presence penalty must be between -2 and 2');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Get LLM provider by ID
   */
  async getProvider(providerId: string): Promise<LLMProvider | null> {
    const providers = await this.getProviders();
    return providers.find(p => p.id === providerId) || null;
  }

  /**
   * Get LLM model by ID
   */
  async getModel(modelId: string): Promise<LLMModel | null> {
    const models = await this.getModels();
    return models.find(m => m.id === modelId) || null;
  }

  /**
   * Get models for a specific provider
   */
  async getModelsForProvider(providerId: string): Promise<LLMModel[]> {
    return this.getModels(providerId);
  }

  /**
   * Calculate estimated cost for a configuration
   */
  async calculateEstimatedCost(config: AgentLLMConfig, estimatedTokens: number): Promise<number> {
    const model = await this.getModel(config.modelId);
    if (!model) return 0;
    
    return model.costPerToken * estimatedTokens;
  }

  /**
   * Get configuration summary for display
   */
  async getConfigSummary(config: AgentLLMConfig): Promise<{
    provider: LLMProvider | null;
    model: LLMModel | null;
    estimatedCostPer1K: number;
  }> {
    const [provider, model] = await Promise.all([
      this.getProvider(config.providerId),
      this.getModel(config.modelId)
    ]);

    const estimatedCostPer1K = model ? model.costPerToken * 1000 : 0;

    return {
      provider,
      model,
      estimatedCostPer1K
    };
  }
}

// Export singleton instance
export const llmConfigService = new LLMConfigurationService();

// Export utility functions
export {
  DEFAULT_LLM_PROVIDERS,
  DEFAULT_LLM_MODELS,
  DEFAULT_AGENT_LLM_CONFIGS
} from '$lib/types/llm-config';
