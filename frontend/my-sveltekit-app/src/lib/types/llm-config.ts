
// 🤖 PHASE 3: Multi-Provider Utility Functions
export function getProviderIcon(providerId: string): string {
  const icons: Record<string, string> = {
    'openai': 'fa-robot',
    'anthropic': 'fa-brain',
    'google': 'fa-google',
    'local': 'fa-server',
    'custom': 'fa-cog'
  };
  return icons[providerId] || 'fa-question';
}

export function getProviderColor(providerId: string): string {
  return LLM_PROVIDER_COLORS[providerId] || 'bg-gray-600';
}

export function getProviderGradient(providerId: string): string {
  return LLM_PROVIDER_GRADIENTS[providerId] || 'from-gray-500 to-gray-700';
}

export function formatCost(cost: number): string {
  if (cost < 0.000001) {
    return '<$0.000001';
  }
  if (cost < 0.001) {
    return `${cost.toFixed(6)}`;
  }
  return `${cost.toFixed(4)}`;
}

export function getCapabilityIcon(capability: string): string {
  return LLM_CAPABILITY_ICONS[capability] || 'fa-star';
}

export function getRecommendedProvidersForAgent(agentType: string): string[] {
  return AGENT_TYPE_LLM_RECOMMENDATIONS[agentType]?.recommended_providers || ['openai'];
}

export function getOptimizationProfile(profileName: string) {
  return PROVIDER_OPTIMIZATION_PROFILES[profileName] || PROVIDER_OPTIMIZATION_PROFILES['balanced'];
}// LLM Configuration Types - Template Independent Agent Management
export interface LLMProvider {
  id: string;
  name: string;
  description: string;
  icon: string;
  type: 'openai' | 'anthropic' | 'google' | 'local' | 'custom';
  baseUrl?: string;
  apiKeyRequired: boolean;
  supportedFeatures: string[];
}

export interface LLMModel {
  id: string;
  name: string;
  providerId: string;
  description: string;
  maxTokens: number;
  supportsStreaming: boolean;
  supportsFunctionCalling: boolean;
  costPerToken: number;
  contextWindow: number;
  capabilities: string[];
}

export interface AgentLLMConfig {
  agentId: string;
  agentName: string;
  providerId: string;
  modelId: string;
  temperature: number;
  maxTokens: number;
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;
  customConfig?: Record<string, any>;
  systemMessage?: string;
}

export interface LLMConfigurationState {
  providers: LLMProvider[];
  models: LLMModel[];
  agentConfigs: AgentLLMConfig[];
  loading: boolean;
  error: string | null;
}

// 🤖 PHASE 3: Enhanced LLM Providers with Status Information
export interface LLMProviderStatus {
  available: boolean;
  provider_name: string;
  requires_api_key: boolean;
  api_key_configured: boolean;
  supported_features: string[];
  rate_limits: Record<string, number>;
  error?: string;
}

export interface EnhancedLLMProvider extends LLMProvider {
  status: LLMProviderStatus;
  rate_limits: Record<string, number>;
}

// Enhanced LLM Models with Recommendations
export interface EnhancedLLMModel extends LLMModel {
  recommended_for: string[];
  cost_per_1k_tokens: number;
  optimization_score: number;
}

// Multi-Provider Configuration
export interface MultiProviderLLMConfig extends AgentLLMConfig {
  provider_status: LLMProviderStatus;
  model_info: {
    supports_streaming: boolean;
    supports_function_calling: boolean;
    context_window: number;
    capabilities: string[];
  };
  cost_estimate: {
    cost_per_1k: number;
    estimated_monthly: number;
  };
  recommendations: {
    cost_effective_alternative?: string;
    performance_alternative?: string;
  };
}

// Predefined LLM Providers (Enhanced)
export const DEFAULT_LLM_PROVIDERS: LLMProvider[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT models from OpenAI - Industry leading performance',
    icon: 'fa-robot',
    type: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    apiKeyRequired: true,
    supportedFeatures: ['chat', 'completion', 'function-calling', 'streaming']
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    description: 'Claude models from Anthropic - Excellent reasoning and safety',
    icon: 'fa-brain',
    type: 'anthropic',
    baseUrl: 'https://api.anthropic.com/v1',
    apiKeyRequired: true,
    supportedFeatures: ['chat', 'completion', 'streaming', 'large-context']
  },
  {
    id: 'google',
    name: 'Google AI',
    description: 'Gemini models from Google - Advanced multimodal capabilities',
    icon: 'fa-google',
    type: 'google',
    baseUrl: 'https://generativelanguage.googleapis.com/v1',
    apiKeyRequired: true,
    supportedFeatures: ['chat', 'completion', 'function-calling', 'vision']
  }
];

// 🤖 PHASE 3: Enhanced LLM Models with Recommendations
export const DEFAULT_LLM_MODELS: LLMModel[] = [
  // OpenAI Models
  {
    id: 'gpt-4',
    name: 'GPT-4',
    providerId: 'openai',
    description: 'Most capable GPT-4 model for complex reasoning and analysis',
    maxTokens: 8192,
    supportsStreaming: true,
    supportsFunctionCalling: true,
    costPerToken: 0.00003,
    contextWindow: 8192,
    capabilities: ['reasoning', 'analysis', 'coding', 'creative-writing']
  },
  {
    id: 'gpt-4-turbo',
    name: 'GPT-4 Turbo',
    providerId: 'openai',
    description: 'Latest GPT-4 Turbo with improved performance and larger context',
    maxTokens: 4096,
    supportsStreaming: true,
    supportsFunctionCalling: true,
    costPerToken: 0.00001,
    contextWindow: 128000,
    capabilities: ['reasoning', 'analysis', 'coding', 'creative-writing', 'vision']
  },
  {
    id: 'gpt-3.5-turbo',
    name: 'GPT-3.5 Turbo',
    providerId: 'openai',
    description: 'Fast and cost-effective for most agent tasks',
    maxTokens: 4096,
    supportsStreaming: true,
    supportsFunctionCalling: true,
    costPerToken: 0.000002,
    contextWindow: 16385,
    capabilities: ['reasoning', 'analysis', 'coding']
  },
  // Anthropic Models
  {
    id: 'claude-3-opus',
    name: 'Claude 3 Opus',
    providerId: 'anthropic',
    description: 'Most powerful Claude model for complex analysis and reasoning',
    maxTokens: 4096,
    supportsStreaming: true,
    supportsFunctionCalling: false,
    costPerToken: 0.000015,
    contextWindow: 200000,
    capabilities: ['reasoning', 'analysis', 'creative-writing', 'math', 'large-context']
  },
  {
    id: 'claude-3-sonnet',
    name: 'Claude 3 Sonnet',
    providerId: 'anthropic',
    description: 'Balanced Claude model with excellent reasoning and large context',
    maxTokens: 4096,
    supportsStreaming: true,
    supportsFunctionCalling: false,
    costPerToken: 0.000003,
    contextWindow: 200000,
    capabilities: ['reasoning', 'analysis', 'creative-writing', 'large-context']
  },
  {
    id: 'claude-3-haiku',
    name: 'Claude 3 Haiku',
    providerId: 'anthropic',
    description: 'Fast and cost-effective Claude model for simple tasks',
    maxTokens: 4096,
    supportsStreaming: true,
    supportsFunctionCalling: false,
    costPerToken: 0.00000025,
    contextWindow: 200000,
    capabilities: ['reasoning', 'analysis', 'large-context']
  },
  // Google Models
  {
    id: 'gemini-pro',
    name: 'Gemini Pro',
    providerId: 'google',
    description: 'Google\'s most capable AI model with multimodal abilities',
    maxTokens: 2048,
    supportsStreaming: true,
    supportsFunctionCalling: true,
    costPerToken: 0.000001,
    contextWindow: 32768,
    capabilities: ['reasoning', 'analysis', 'coding', 'vision', 'multimodal']
  },
  {
    id: 'gemini-pro-vision',
    name: 'Gemini Pro Vision',
    providerId: 'google',
    description: 'Gemini with enhanced vision and image understanding capabilities',
    maxTokens: 2048,
    supportsStreaming: true,
    supportsFunctionCalling: true,
    costPerToken: 0.000001,
    contextWindow: 16384,
    capabilities: ['reasoning', 'analysis', 'vision', 'image-understanding', 'multimodal']
  }
];

// 🤖 PHASE 3: Enhanced Default LLM Configuration for Different Agent Types
export const DEFAULT_AGENT_LLM_CONFIGS: Record<string, Partial<AgentLLMConfig>> = {
  'AssistantAgent': {
    providerId: 'openai',
    modelId: 'gpt-4',
    temperature: 0.7,
    maxTokens: 2048,
    topP: 1.0,
    frequencyPenalty: 0.0,
    presencePenalty: 0.0
  },
  'UserProxyAgent': {
    providerId: 'openai',
    modelId: 'gpt-3.5-turbo',
    temperature: 0.3,
    maxTokens: 1024,
    topP: 1.0,
    frequencyPenalty: 0.0,
    presencePenalty: 0.0
  },
  'GroupChatManager': {
    providerId: 'anthropic',
    modelId: 'claude-3-sonnet',
    temperature: 0.5,
    maxTokens: 1024,
    topP: 1.0,
    frequencyPenalty: 0.0,
    presencePenalty: 0.0
  },
  'MCPServer': {
    providerId: 'openai',
    modelId: 'gpt-3.5-turbo',
    temperature: 0.1,
    maxTokens: 512,
    topP: 0.9,
    frequencyPenalty: 0.0,
    presencePenalty: 0.0
  }
};

// 🤖 PHASE 3: Multi-Provider Optimization Profiles
export const PROVIDER_OPTIMIZATION_PROFILES = {
  'cost_effective': {
    name: 'Cost Effective',
    description: 'Optimized for lowest cost per operation',
    preferred_providers: ['google', 'anthropic', 'openai'],
    preferred_models: ['gemini-pro', 'claude-3-haiku', 'gpt-3.5-turbo']
  },
  'performance': {
    name: 'High Performance',
    description: 'Optimized for best reasoning and analysis capabilities',
    preferred_providers: ['openai', 'anthropic', 'google'],
    preferred_models: ['gpt-4', 'claude-3-opus', 'gpt-4-turbo']
  },
  'balanced': {
    name: 'Balanced',
    description: 'Good balance of cost and performance',
    preferred_providers: ['anthropic', 'openai', 'google'],
    preferred_models: ['claude-3-sonnet', 'gpt-4-turbo', 'gemini-pro']
  },
  'large_context': {
    name: 'Large Context',
    description: 'Optimized for handling large documents and context',
    preferred_providers: ['anthropic', 'openai', 'google'],
    preferred_models: ['claude-3-sonnet', 'gpt-4-turbo', 'claude-3-opus']
  }
};

// 🤖 PHASE 3: Enhanced Capability and UI Mappings
export const LLM_CAPABILITY_ICONS: Record<string, string> = {
  'reasoning': 'fa-brain',
  'analysis': 'fa-chart-line',
  'coding': 'fa-code',
  'creative-writing': 'fa-pen-fancy',
  'vision': 'fa-eye',
  'image-understanding': 'fa-image',
  'math': 'fa-calculator',
  'function-calling': 'fa-function',
  'large-context': 'fa-expand-arrows-alt',
  'multimodal': 'fa-layer-group',
  'streaming': 'fa-stream'
};

export const LLM_PROVIDER_COLORS: Record<string, string> = {
  'openai': 'bg-green-600',
  'anthropic': 'bg-orange-600',
  'google': 'bg-blue-600',
  'local': 'bg-gray-600',
  'custom': 'bg-purple-600'
};

export const LLM_PROVIDER_GRADIENTS: Record<string, string> = {
  'openai': 'from-green-500 to-green-700',
  'anthropic': 'from-orange-500 to-orange-700',
  'google': 'from-blue-500 to-blue-700',
  'local': 'from-gray-500 to-gray-700',
  'custom': 'from-purple-500 to-purple-700'
};

// 🤖 PHASE 3: Agent Type Recommendations
export const AGENT_TYPE_LLM_RECOMMENDATIONS: Record<string, {
  recommended_providers: string[];
  optimization_focus: string;
  typical_use_cases: string[];
}> = {
  'AssistantAgent': {
    recommended_providers: ['openai', 'anthropic'],
    optimization_focus: 'reasoning and analysis',
    typical_use_cases: ['complex problem solving', 'document analysis', 'creative tasks']
  },
  'UserProxyAgent': {
    recommended_providers: ['openai', 'google'],
    optimization_focus: 'code execution and interaction',
    typical_use_cases: ['human-AI interaction', 'code execution', 'task coordination']
  },
  'GroupChatManager': {
    recommended_providers: ['anthropic', 'openai'],
    optimization_focus: 'conversation orchestration',
    typical_use_cases: ['multi-agent coordination', 'conversation flow management', 'decision making']
  },
  'MCPServer': {
    recommended_providers: ['google', 'openai'],
    optimization_focus: 'MCP server integration and external service access',
    typical_use_cases: ['Google Drive integration', 'SharePoint integration', 'external service access', 'document retrieval']
  }
};
