/**
 * Prompt Generation Service
 * 
 * Service for generating system prompts from simple agent descriptions using LLM
 */

import api from './api';

const API_BASE = '/agent-orchestration';

export interface PromptGenerationRequest {
  description: string;
  agent_type: string;
  doc_aware: boolean;
  project_id?: string;
  llm_provider?: string;
  llm_model?: string;
}

export interface PromptGenerationResponse {
  success: boolean;
  generated_prompt?: string;
  metadata?: {
    generated_at: string;
    llm_provider: string;
    llm_model: string;
    agent_type: string;
    doc_aware: boolean;
    description_length: number;
    prompt_length: number;
    tokens_used: number;
    response_time_ms: number;
    fallback_used?: boolean;
  };
  error?: string;
}

// Simple in-memory cache
const promptCache: Map<string, { data: PromptGenerationResponse; timestamp: number }> = new Map();
const CACHE_DURATION_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * Generate a cache key from request parameters
 */
function generateCacheKey(request: PromptGenerationRequest): string {
  const keyParts = [
    request.description,
    request.agent_type,
    request.doc_aware.toString(),
    request.llm_provider || 'openai',
    request.llm_model || 'gpt-4'
  ];
  return btoa(keyParts.join('|')).replace(/[^a-zA-Z0-9]/g, '');
}

/**
 * Get cached prompt if available and not expired
 */
function getCachedPrompt(key: string): PromptGenerationResponse | null {
  const cached = promptCache.get(key);
  if (!cached) return null;
  
  const now = Date.now();
  if (now - cached.timestamp > CACHE_DURATION_MS) {
    promptCache.delete(key);
    return null;
  }
  
  return cached.data;
}

/**
 * Cache a prompt generation result
 */
function cachePrompt(key: string, data: PromptGenerationResponse): void {
  promptCache.set(key, { data, timestamp: Date.now() });
}

/**
 * Generate a system prompt from an agent description
 */
export async function generateSystemPrompt(
  request: PromptGenerationRequest
): Promise<PromptGenerationResponse> {
  // Validate request
  if (!request.description || request.description.trim().length < 10) {
    return {
      success: false,
      error: 'Description must be at least 10 characters'
    };
  }
  
  // Note: Maximum length validation (10,000 characters) is handled by the backend
  
  // Check cache
  const cacheKey = generateCacheKey(request);
  const cached = getCachedPrompt(cacheKey);
  if (cached) {
    console.log('💾 PROMPT GEN: Using cached prompt');
    return cached;
  }
  
  try {
    const response = await api.post(`${API_BASE}/generate-prompt/generate/`, {
      description: request.description.trim(),
      agent_type: request.agent_type || 'AssistantAgent',
      doc_aware: request.doc_aware || false,
      project_id: request.project_id,
      llm_provider: request.llm_provider || 'openai',
      llm_model: request.llm_model || 'gpt-4'
    });
    
    const data: PromptGenerationResponse = response.data;
    
    // Cache successful results
    if (data.success && data.generated_prompt) {
      cachePrompt(cacheKey, data);
    }
    
    return data;
    
  } catch (error: any) {
    console.error('❌ PROMPT GEN: Error generating prompt:', error);
    const errorMessage = error?.response?.data?.error || error?.message || 'Failed to generate prompt';
    return {
      success: false,
      error: errorMessage
    };
  }
}

/**
 * Preview a generated prompt (for UI preview before applying)
 * This is a convenience function that calls generateSystemPrompt
 */
export async function previewGeneratedPrompt(
  request: PromptGenerationRequest
): Promise<PromptGenerationResponse> {
  return generateSystemPrompt(request);
}

/**
 * Clear the prompt cache
 */
export function clearPromptCache(): void {
  promptCache.clear();
  console.log('🗑️ PROMPT GEN: Cache cleared');
}

