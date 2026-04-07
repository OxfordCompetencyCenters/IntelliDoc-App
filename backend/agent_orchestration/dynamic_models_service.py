"""
Dynamic LLM Models Service - API Key Based Model Fetching

Provides dynamic model listing for all supported LLM providers based on API key availability.
No hardcoded fallbacks - only shows models when API keys are available and working.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from django.core.cache import cache
from django.conf import settings
from users.models import IntelliDocProject
from project_api_keys.services import get_project_api_key_service

from llm_eval.model_service import ModelService
from llm_eval.providers.openai_provider import OpenAIProvider
from llm_eval.providers.claude_provider import ClaudeProvider
from llm_eval.providers.gemini_provider import GeminiProvider

logger = logging.getLogger('dynamic_models_service')

@dataclass
class ModelInfo:
    """Model information data structure"""
    id: str
    name: str
    display_name: str
    provider: str
    context_length: Optional[int] = None
    cost_per_1k_tokens: Optional[float] = None
    capabilities: List[str] = None
    recommended_for: List[str] = None
    is_available: bool = True
    last_checked: Optional[str] = None

class DynamicModelsService:
    """Service for dynamic LLM model fetching and management"""
    
    CACHE_TTL = 3600  # 1 hour cache
    API_TIMEOUT = 10  # 10 seconds API timeout
    
    def __init__(self):
        self.cache_prefix = "agent_models"
        self.provider_configs = {
            'openai': {
                'class': OpenAIProvider,
                'name': 'OpenAI',
                'api_key_setting': 'OPENAI_API_KEY'
            },
            'anthropic': {
                'class': ClaudeProvider,
                'name': 'Anthropic',
                'api_key_setting': 'ANTHROPIC_API_KEY'
            },
            'google': {
                'class': GeminiProvider,
                'name': 'Google',
                'api_key_setting': 'GOOGLE_API_KEY'
            },
            'ollama': {
                'class': None,  # Handled by llm_provider_manager
                'name': 'Ollama (Local)',
                'api_key_setting': None,  # No API key needed
            }
        }
    
    def get_cache_key(self, provider: str) -> str:
        """Generate cache key for provider models"""
        return f"{self.cache_prefix}_{provider}_models"
    
    def get_api_key_for_provider(self, provider: str, project: Optional[IntelliDocProject] = None) -> Optional[str]:
        """Get API key for provider from project-specific keys or fallback to settings (sync version)"""
        if provider not in self.provider_configs:
            logger.warning(f"⚠️ UNKNOWN PROVIDER: {provider} not in provider_configs")
            return None
        
        # First try to get project-specific API key
        if project:
            try:
                project_service = get_project_api_key_service()
                logger.info(f"🔍 API KEY LOOKUP: Checking for {provider} API key in project {project.name} (ID: {project.project_id})")
                project_api_key = project_service.get_project_api_key(project, provider)
                if project_api_key and project_api_key.strip():
                    logger.info(f"✅ PROJECT API KEY: Found project-specific {provider} API key for project {project.name} (length: {len(project_api_key)})")
                    return project_api_key.strip()
                else:
                    logger.warning(f"⚠️ PROJECT API KEY: No project-specific {provider} API key found for project {project.name} (ID: {project.project_id})")
            except Exception as e:
                logger.error(f"❌ PROJECT API KEY: Error retrieving project-specific {provider} API key for project {project.name}: {e}")
                import traceback
                logger.error(f"❌ PROJECT API KEY: Traceback: {traceback.format_exc()}")
        else:
            logger.warning(f"⚠️ NO PROJECT CONTEXT: Project is None - {provider} API key not available")
        
        # NO fallback to environment variables - project-specific keys ONLY
        return None

    async def get_api_key_for_provider_async(self, provider: str, project: Optional[IntelliDocProject] = None) -> Optional[str]:
        """Get API key for provider from project-specific keys (async version)"""
        if provider not in self.provider_configs:
            return None
        
        # First try to get project-specific API key
        if project:
            try:
                project_service = get_project_api_key_service()
                project_api_key = await project_service.get_project_api_key_async(project, provider)
                if project_api_key and project_api_key.strip():
                    logger.info(f"🔑 PROJECT API KEY: Using project-specific {provider} API key for project {project.name}")
                    return project_api_key.strip()
                else:
                    logger.warning(f"⚠️ PROJECT API KEY: No project-specific {provider} API key found for project {project.name}")
            except Exception as e:
                logger.error(f"❌ PROJECT API KEY: Error retrieving project-specific {provider} API key: {e}")
        
        # NO fallback to environment variables - project-specific keys ONLY
        if project:
            logger.warning(f"⚠️ NO PROJECT API KEY: No project-specific {provider} API key found for project {project.name}")
        else:
            logger.warning(f"⚠️ NO PROJECT CONTEXT: Project required for API key access - {provider} not available")
        
        return None
    
    def test_api_key(self, provider: str, api_key: str) -> bool:
        """Test if API key is valid by making a simple API call"""
        try:
            logger.info(f"🔍 API TEST: Testing API key for {provider}")
            
            if provider == 'openai':
                # Test with a simple models list call
                models = ModelService.get_openai_models(api_key)
                return len(models) > 0
                
            elif provider == 'anthropic':
                # Test with Claude models API endpoint
                models = ModelService.get_claude_models(api_key)
                return len(models) > 0
                
            elif provider == 'google':
                # Test with Gemini models
                models = ModelService.get_gemini_models(api_key)
                return len(models) > 0
                
            return False
            
        except Exception as e:
            logger.error(f"❌ API TEST: API key test failed for {provider}: {e}")
            return False

    async def fetch_models_from_api(self, provider: str, api_key: str) -> List[ModelInfo]:
        """Fetch ALL models from provider API - no hardcoded limits"""
        try:
            logger.info(f"🔄 DYNAMIC MODELS: Fetching ALL models from {provider} API")
            
            models = []
            
            if provider == 'openai':
                models_data = ModelService.get_openai_models(api_key)
                
                for model_data in models_data:
                    model_info = ModelInfo(
                        id=model_data['id'],
                        name=model_data['name'],
                        display_name=model_data.get('displayName', model_data['name']),
                        provider='openai',
                        is_available=True,
                        last_checked=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    # Enhanced model information based on model ID patterns
                    model_id = model_info.id.lower()
                    
                    # GPT-5 and future models (forward-compatible)
                    if 'gpt-5' in model_id:
                        model_info.context_length = 128000  # Default, will be updated when specs are known
                        model_info.cost_per_1k_tokens = 0.01  # Default, will be updated when pricing is known
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'latest_model']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                        logger.info(f"🚀 NEW MODEL: Detected GPT-5 model: {model_info.id}")
                    
                    elif 'gpt-4' in model_id:
                        if 'turbo' in model_id or '1106' in model_id or '0125' in model_id:
                            model_info.context_length = 128000
                            model_info.cost_per_1k_tokens = 0.01
                            model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'long_context']
                        elif 'vision' in model_id:
                            model_info.context_length = 128000
                            model_info.cost_per_1k_tokens = 0.01
                            model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'vision', 'multimodal']
                        else:
                            model_info.context_length = 8192
                            model_info.cost_per_1k_tokens = 0.03
                            model_info.capabilities = ['text_generation', 'analysis', 'reasoning']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                        
                    elif 'gpt-3.5' in model_id:
                        model_info.context_length = 16385 if 'turbo' in model_id else 4096
                        model_info.cost_per_1k_tokens = 0.002
                        model_info.capabilities = ['text_generation', 'analysis']
                        model_info.recommended_for = ['UserProxyAgent', 'DelegateAgent']
                        
                    elif 'gpt-4o' in model_id:
                        model_info.context_length = 128000
                        model_info.cost_per_1k_tokens = 0.005
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'multimodal', 'vision']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                    
                    # Default for any other GPT models not explicitly handled (future-proof)
                    elif model_id.startswith('gpt-'):
                        model_info.context_length = 128000  # Conservative default
                        model_info.cost_per_1k_tokens = 0.01  # Conservative default
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                        logger.info(f"🆕 UNKNOWN GPT MODEL: Detected new GPT model pattern: {model_info.id} - using defaults")
                        
                    elif 'davinci' in model_id or 'curie' in model_id or 'babbage' in model_id:
                        model_info.context_length = 4096
                        model_info.cost_per_1k_tokens = 0.02
                        model_info.capabilities = ['text_generation']
                        model_info.recommended_for = ['UserProxyAgent']
                    
                    models.append(model_info)
                
                logger.info(f"✅ DYNAMIC MODELS: Fetched {len(models)} OpenAI models from API")
                
            elif provider == 'google':
                models_data = ModelService.get_gemini_models(api_key)
                
                for model_data in models_data:
                    model_info = ModelInfo(
                        id=model_data['id'],
                        name=model_data['name'],
                        display_name=model_data.get('displayName', model_data['name']),
                        provider='google',
                        is_available=True,
                        last_checked=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    # Enhanced model information based on model ID patterns
                    model_id = model_info.id.lower()
                    
                    # Gemini 2.0 and future models (forward-compatible)
                    if 'gemini-2' in model_id or 'gemini-2.0' in model_id:
                        model_info.context_length = 2000000  # Default, will be updated when specs are known
                        model_info.cost_per_1k_tokens = 0.00125  # Default, will be updated when pricing is known
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'multimodal', 'vision', 'latest_model']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                        logger.info(f"🚀 NEW MODEL: Detected Gemini 2.0 model: {model_info.id}")
                    
                    elif 'gemini-1.5-pro' in model_id:
                        model_info.context_length = 2000000  # Gemini 1.5 Pro has 2M context
                        model_info.cost_per_1k_tokens = 0.00125
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'multimodal', 'vision', 'ultra_long_context']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                        
                    elif 'gemini-1.5-flash' in model_id:
                        model_info.context_length = 1000000  # Gemini 1.5 Flash has 1M context
                        model_info.cost_per_1k_tokens = 0.00075
                        model_info.capabilities = ['text_generation', 'analysis', 'fast_response', 'multimodal', 'vision']
                        model_info.recommended_for = ['DelegateAgent', 'UserProxyAgent']
                        
                    elif 'gemini-pro' in model_id and '1.5' not in model_id and '2' not in model_id:
                        model_info.context_length = 32768
                        model_info.cost_per_1k_tokens = 0.0005
                        model_info.capabilities = ['text_generation', 'analysis']
                        model_info.recommended_for = ['UserProxyAgent', 'DelegateAgent']
                        
                    elif 'gemini-ultra' in model_id:
                        model_info.context_length = 32768
                        model_info.cost_per_1k_tokens = 0.01
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'complex_tasks']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                    
                    # Default for any other Gemini models not explicitly handled (future-proof)
                    elif model_id.startswith('gemini-'):
                        model_info.context_length = 1000000  # Conservative default
                        model_info.cost_per_1k_tokens = 0.001  # Conservative default
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'multimodal']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                        logger.info(f"🆕 UNKNOWN GEMINI MODEL: Detected new Gemini model pattern: {model_info.id} - using defaults")
                    
                    models.append(model_info)
                
                logger.info(f"✅ DYNAMIC MODELS: Fetched {len(models)} Google models from API")
                
            elif provider == 'anthropic':
                models_data = ModelService.get_claude_models(api_key)
                
                for model_data in models_data:
                    model_info = ModelInfo(
                        id=model_data['id'],
                        name=model_data['name'],
                        display_name=model_data.get('displayName', model_data['name']),
                        provider='anthropic',
                        context_length=200000,  # Most Claude models have 200k context
                        is_available=True,
                        last_checked=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    # Enhanced model information based on model ID patterns
                    model_id = model_info.id.lower()
                    
                    if 'claude-3-5-sonnet' in model_id:
                        model_info.cost_per_1k_tokens = 0.003
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'long_context', 'latest_model']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager', 'DelegateAgent']
                        
                    elif 'claude-3-5-haiku' in model_id:
                        model_info.cost_per_1k_tokens = 0.001
                        model_info.capabilities = ['text_generation', 'analysis', 'fast_response', 'cost_effective']
                        model_info.recommended_for = ['DelegateAgent', 'UserProxyAgent']
                        
                    elif 'claude-3-opus' in model_id:
                        model_info.cost_per_1k_tokens = 0.015
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'complex_tasks', 'highest_quality']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                        
                    elif 'claude-3-sonnet' in model_id:
                        model_info.cost_per_1k_tokens = 0.003
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning', 'balanced_performance']
                        model_info.recommended_for = ['AssistantAgent', 'GroupChatManager']
                        
                    elif 'claude-3-haiku' in model_id:
                        model_info.cost_per_1k_tokens = 0.00025
                        model_info.capabilities = ['text_generation', 'analysis', 'fast_response', 'cost_effective']
                        model_info.recommended_for = ['UserProxyAgent', 'DelegateAgent']
                        
                    elif 'claude-2' in model_id:
                        model_info.context_length = 100000
                        model_info.cost_per_1k_tokens = 0.008
                        model_info.capabilities = ['text_generation', 'analysis', 'reasoning']
                        model_info.recommended_for = ['AssistantAgent']
                        
                    elif 'claude-instant' in model_id:
                        model_info.context_length = 100000
                        model_info.cost_per_1k_tokens = 0.0008
                        model_info.capabilities = ['text_generation', 'fast_response', 'cost_effective']
                        model_info.recommended_for = ['UserProxyAgent', 'DelegateAgent']
                    
                    models.append(model_info)
                
                logger.info(f"✅ DYNAMIC MODELS: Fetched {len(models)} Anthropic models")
            
            return models
                
        except Exception as e:
            logger.error(f"❌ DYNAMIC MODELS: API fetch failed for {provider}: {e}")
            raise  # Re-raise the exception instead of returning fallback
    
    def get_cached_models(self, provider: str) -> Optional[List[ModelInfo]]:
        """Get models from cache"""
        cache_key = self.get_cache_key(provider)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            # Convert dict back to ModelInfo objects
            models = [ModelInfo(**model_dict) for model_dict in cached_data]
            logger.info(f"🎯 DYNAMIC MODELS: Retrieved {len(models)} cached models for {provider}")
            return models
        
        return None
    
    def cache_models(self, provider: str, models: List[ModelInfo]):
        """Cache models for provider"""
        cache_key = self.get_cache_key(provider)
        # Convert ModelInfo objects to dict for caching
        models_data = [asdict(model) for model in models]
        cache.set(cache_key, models_data, self.CACHE_TTL)
        logger.info(f"💾 DYNAMIC MODELS: Cached {len(models)} models for {provider}")
    
    async def get_models_for_provider(self, provider: str, api_key: Optional[str] = None, use_cache: bool = True, project: Optional[IntelliDocProject] = None) -> List[ModelInfo]:
        """Get models for provider - ONLY if API key is available and working"""
        try:
            # Get API key from settings if not provided
            if not api_key:
                api_key = await self.get_api_key_for_provider_async(provider, project)
            
            # If no API key available, return empty list (no fallback)
            if not api_key:
                logger.warning(f"⚠️ DYNAMIC MODELS: No API key for {provider} - returning empty models list")
                return []
            
            # Test API key validity
            if not self.test_api_key(provider, api_key):
                logger.error(f"❌ DYNAMIC MODELS: Invalid API key for {provider} - returning empty models list")
                return []
            
            # Check cache first
            if use_cache:
                cached_models = self.get_cached_models(provider)
                if cached_models:
                    return cached_models
            
            # Fetch from API
            models = await self.fetch_models_from_api(provider, api_key)
            
            # Cache the results
            if use_cache and models:
                self.cache_models(provider, models)
            
            logger.info(f"✅ DYNAMIC MODELS: Successfully fetched {len(models)} models for {provider}")
            return models
            
        except Exception as e:
            logger.error(f"❌ DYNAMIC MODELS: Failed to get models for {provider}: {e}")
            # NO FALLBACK - return empty list
            return []
    
    def get_provider_status(self, provider: str, project: Optional[IntelliDocProject] = None) -> Dict[str, Any]:
        """Get status information for a provider (sync version)"""
        api_key = self.get_api_key_for_provider(provider, project)
        
        status = {
            'provider': provider,
            'name': self.provider_configs[provider]['name'],
            'has_api_key': False,
            'api_key_valid': False,
            'models_available': False,
            'message': 'API key not configured',
            'key_source': None
        }
        
        if not api_key:
            if project:
                status['message'] = f'No project-specific API key configured for {provider} in project {project.name}. Please configure API keys in the project settings.'
            else:
                status['message'] = f'Project context required for {provider} API key access. No project specified.'
            return status
        
        status['has_api_key'] = True
        
        # Set key source (always project-specific in this system)
        status['key_source'] = 'project'
        
        # Test API key
        api_key_valid = self.test_api_key(provider, api_key)
        
        status['api_key_valid'] = api_key_valid
        status['models_available'] = api_key_valid
        status['message'] = f'Project-specific API key configured and valid' if api_key_valid else f'Project-specific API key configured but invalid or expired'
        
        return status

    async def get_provider_status_async(self, provider: str, project: Optional[IntelliDocProject] = None) -> Dict[str, Any]:
        """Get status information for a provider (async version)"""
        api_key = await self.get_api_key_for_provider_async(provider, project)
        
        status = {
            'provider': provider,
            'name': self.provider_configs[provider]['name'],
            'has_api_key': False,
            'api_key_valid': False,
            'models_available': False,
            'message': 'API key not configured',
            'key_source': None
        }
        
        if not api_key:
            if project:
                status['message'] = f'No project-specific API key configured for {provider} in project {project.name}. Please configure API keys in the project settings.'
            else:
                status['message'] = f'Project context required for {provider} API key access. No project specified.'
            return status
        
        status['has_api_key'] = True
        
        # Set key source (always project-specific in this system)
        status['key_source'] = 'project'
        
        # Test API key
        api_key_valid = self.test_api_key(provider, api_key)
        
        status['api_key_valid'] = api_key_valid
        status['models_available'] = api_key_valid
        status['message'] = f'Project-specific API key configured and valid' if api_key_valid else f'Project-specific API key configured but invalid or expired'
        
        return status
    
    async def get_all_models(self, api_keys: Optional[Dict[str, str]] = None, use_cache: bool = True, project: Optional[IntelliDocProject] = None) -> Dict[str, List[ModelInfo]]:
        """Get models for all providers - only those with valid API keys"""
        all_models = {}
        api_keys = api_keys or {}
        
        for provider in self.provider_configs.keys():
            provider_api_key = api_keys.get(provider)
            models = await self.get_models_for_provider(provider, provider_api_key, use_cache, project)
            all_models[provider] = models
        
        total_models = sum(len(models) for models in all_models.values())
        logger.info(f"🌟 DYNAMIC MODELS: Retrieved {total_models} total models across {len(all_models)} providers")
        return all_models
    
    def get_recommended_models_for_agent(self, agent_type: str, project: Optional[IntelliDocProject] = None) -> List[ModelInfo]:
        """Get recommended models for specific agent type - only from providers with project-specific API keys"""
        recommended = []
        
        if not project:
            logger.warning(f"⚠️ DYNAMIC MODELS: No project context provided for agent type {agent_type} - cannot recommend models")
            return []
        
        # Only recommend models from providers that have valid project-specific API keys
        for provider in self.provider_configs.keys():
            api_key = self.get_api_key_for_provider(provider, project)
            if not api_key or not self.test_api_key(provider, api_key):
                continue  # Skip providers without valid API keys
            
            # Get cached models for this provider
            cached_models = self.get_cached_models(provider)
            if cached_models:
                for model in cached_models:
                    if model.recommended_for and agent_type in model.recommended_for:
                        recommended.append(model)
        
        # Sort by cost (cheaper first) and capabilities
        recommended.sort(key=lambda m: (m.cost_per_1k_tokens or 0, -len(m.capabilities or [])))
        
        logger.info(f"🎯 DYNAMIC MODELS: Found {len(recommended)} recommended models for {agent_type} from project {project.name}")
        return recommended
    
    def clear_cache(self, provider: Optional[str] = None):
        """Clear model cache"""
        if provider:
            cache_key = self.get_cache_key(provider)
            cache.delete(cache_key)
            logger.info(f"🧹 DYNAMIC MODELS: Cleared cache for {provider}")
        else:
            for prov in self.provider_configs.keys():
                cache_key = self.get_cache_key(prov)
                cache.delete(cache_key)
            logger.info(f"🧹 DYNAMIC MODELS: Cleared all model caches")

# Global service instance
dynamic_models_service = DynamicModelsService()
