"""
LLM Bulk Model Loader Service
============================

Optimized service for pre-loading all available models from all providers
to eliminate repetitive API calls and reduce LAG in the Agent Orchestration interface.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from django.core.cache import cache
from concurrent.futures import ThreadPoolExecutor
from .dynamic_models_service import dynamic_models_service, ModelInfo

logger = logging.getLogger('llm_bulk_loader')

class LLMBulkLoaderService:
    """Service for efficient bulk loading of all LLM models"""
    
    BULK_CACHE_KEY_PREFIX = "agent_orchestration_all_models_bulk"
    BULK_CACHE_TTL = 3600  # 1 hour cache for bulk data
    LAST_LOADED_KEY_PREFIX = "agent_orchestration_models_last_loaded"
    
    def __init__(self):
        self.is_loading = False
        self.load_lock = asyncio.Lock()
    
    def _get_cache_key(self, project=None) -> str:
        """Generate project-specific cache key"""
        if project and hasattr(project, 'project_id'):
            return f"{self.BULK_CACHE_KEY_PREFIX}_{project.project_id}"
        return f"{self.BULK_CACHE_KEY_PREFIX}_global"
    
    def _get_last_loaded_key(self, project=None) -> str:
        """Generate project-specific last loaded timestamp key"""
        if project and hasattr(project, 'project_id'):
            return f"{self.LAST_LOADED_KEY_PREFIX}_{project.project_id}"
        return f"{self.LAST_LOADED_KEY_PREFIX}_global"
    
    async def pre_load_all_models(self, force_refresh: bool = False, project=None) -> Dict[str, Any]:
        """
        Pre-load all models from all providers in parallel for maximum efficiency
        
        Args:
            force_refresh: Force refresh from APIs even if cached
            
        Returns:
            Comprehensive model data with provider status and metadata
        """
        async with self.load_lock:
            if self.is_loading:
                logger.info("🔄 BULK LOADER: Loading already in progress, waiting...")
                # Wait for existing load to complete
                while self.is_loading:
                    await asyncio.sleep(0.1)
                return self.get_cached_bulk_data(project)
            
            try:
                self.is_loading = True
                start_time = time.time()
                
                logger.info("🚀 BULK LOADER: Starting parallel model pre-loading from all providers")
                
                # Check if we need to refresh
                if not force_refresh:
                    cached_data = self.get_cached_bulk_data(project)
                    if cached_data:
                        logger.info(f"✅ BULK LOADER: Returning cached bulk model data for project {project.name if project else 'global'}")
                        return cached_data
                
                # Clear individual provider caches if force refresh
                if force_refresh:
                    dynamic_models_service.clear_cache()
                
                # Get all provider statuses first
                provider_statuses = {}
                available_providers = []
                
                for provider_id in ['openai', 'anthropic', 'google']:
                    status = await dynamic_models_service.get_provider_status_async(provider_id, project)
                    provider_statuses[provider_id] = status
                    
                    if status['api_key_valid']:
                        available_providers.append(provider_id)
                        logger.info(f"✅ BULK LOADER: Provider {provider_id} available for bulk loading")
                    else:
                        logger.warning(f"⚠️ BULK LOADER: Provider {provider_id} not available: {status['message']}")
                
                # Pre-load models from all available providers in parallel
                provider_models = {}
                provider_errors = {}
                
                if available_providers:
                    logger.info(f"🔄 BULK LOADER: Loading models from {len(available_providers)} providers in parallel")
                    
                    # Create tasks for parallel execution
                    tasks = []
                    for provider_id in available_providers:
                        task = asyncio.create_task(
                            self._load_provider_models_with_error_handling(provider_id, project)
                        )
                        tasks.append((provider_id, task))
                    
                    # Wait for all tasks to complete
                    for provider_id, task in tasks:
                        try:
                            models = await task
                            provider_models[provider_id] = models
                            logger.info(f"✅ BULK LOADER: Loaded {len(models)} models from {provider_id}")
                        except Exception as e:
                            provider_errors[provider_id] = str(e)
                            provider_models[provider_id] = []
                            logger.error(f"❌ BULK LOADER: Failed to load models from {provider_id}: {e}")
                
                # Process and organize the bulk data
                bulk_data = self._process_bulk_model_data(
                    provider_models, 
                    provider_statuses, 
                    provider_errors
                )
                
                # Cache the bulk data (with project context)
                self._cache_bulk_data(bulk_data, project)
                
                end_time = time.time()
                total_models = sum(len(models) for models in provider_models.values())
                
                logger.info(
                    f"🎉 BULK LOADER: Completed in {end_time - start_time:.2f}s | "
                    f"Loaded {total_models} models from {len(available_providers)} providers"
                )
                
                return bulk_data
                
            except Exception as e:
                logger.error(f"❌ BULK LOADER: Critical error during bulk loading: {e}")
                raise
            finally:
                self.is_loading = False
    
    async def _load_provider_models_with_error_handling(self, provider_id: str, project=None) -> List[ModelInfo]:
        """Load models for a single provider with comprehensive error handling"""
        try:
            logger.info(f"🔄 BULK LOADER: Loading models for {provider_id}")
            models = await dynamic_models_service.get_models_for_provider(
                provider_id, 
                use_cache=False,  # Force fresh load for bulk operation
                project=project
            )
            logger.info(f"✅ BULK LOADER: Successfully loaded {len(models)} models for {provider_id}")
            return models
        except Exception as e:
            logger.error(f"❌ BULK LOADER: Error loading models for {provider_id}: {e}")
            return []  # Return empty list on error
    
    def _process_bulk_model_data(
        self, 
        provider_models: Dict[str, List[ModelInfo]], 
        provider_statuses: Dict[str, Any],
        provider_errors: Dict[str, str]
    ) -> Dict[str, Any]:
        """Process and organize bulk model data for frontend consumption"""
        
        # Convert ModelInfo objects to dictionaries for JSON serialization
        serialized_provider_models = {}
        for provider_id, models in provider_models.items():
            serialized_provider_models[provider_id] = [
                asdict(model) for model in models
            ]
        
        # Create unified models list with provider information
        all_models = []
        for provider_id, models in provider_models.items():
            for model in models:
                model_dict = asdict(model)
                model_dict['provider_status'] = provider_statuses.get(provider_id, {})
                all_models.append(model_dict)
        
        # Group models by agent type recommendations
        models_by_agent_type = {}
        for agent_type in ['AssistantAgent', 'UserProxyAgent', 'GroupChatManager', 'DelegateAgent']:
            recommended_models = []
            for model in all_models:
                if model.get('recommended_for') and agent_type in model['recommended_for']:
                    recommended_models.append(model)
            models_by_agent_type[agent_type] = recommended_models
        
        # Calculate statistics
        total_models = len(all_models)
        available_providers = len([p for p in provider_statuses.values() if p['api_key_valid']])
        total_providers = len(provider_statuses)
        
        # Provider summary
        provider_summary = {}
        for provider_id, status in provider_statuses.items():
            models_count = len(provider_models.get(provider_id, []))
            provider_summary[provider_id] = {
                **status,
                'models_count': models_count,
                'load_error': provider_errors.get(provider_id)
            }
        
        return {
            # Core model data
            'provider_models': serialized_provider_models,
            'all_models': all_models,
            'models_by_agent_type': models_by_agent_type,
            
            # Provider information
            'provider_statuses': provider_statuses,
            'provider_summary': provider_summary,
            'provider_errors': provider_errors,
            
            # Statistics
            'statistics': {
                'total_models': total_models,
                'available_providers': available_providers,
                'total_providers': total_providers,
                'models_per_provider': {
                    provider_id: len(models) 
                    for provider_id, models in provider_models.items()
                }
            },
            
            # Metadata
            'metadata': {
                'loaded_at': time.strftime("%Y-%m-%d %H:%M:%S"),
                'cache_ttl': self.BULK_CACHE_TTL,
                'api_version': 'bulk_loader_v1',
                'supports_agent_orchestration': True,
                'optimized_for_frontend': True
            }
        }
    
    def _cache_bulk_data(self, bulk_data: Dict[str, Any], project=None):
        """Cache bulk model data with project-specific key"""
        try:
            cache_key = self._get_cache_key(project)
            last_loaded_key = self._get_last_loaded_key(project)
            project_name = project.name if project and hasattr(project, 'name') else 'global'
            
            cache.set(cache_key, bulk_data, self.BULK_CACHE_TTL)
            cache.set(last_loaded_key, time.time(), self.BULK_CACHE_TTL)
            logger.info(f"💾 BULK LOADER: Cached bulk model data successfully for project {project_name}")
        except Exception as e:
            logger.error(f"❌ BULK LOADER: Failed to cache bulk data: {e}")
    
    def get_cached_bulk_data(self, project=None) -> Optional[Dict[str, Any]]:
        """Get cached bulk model data with project-specific key"""
        try:
            cache_key = self._get_cache_key(project)
            last_loaded_key = self._get_last_loaded_key(project)
            project_name = project.name if project and hasattr(project, 'name') else 'global'
            
            bulk_data = cache.get(cache_key)
            if bulk_data:
                last_loaded = cache.get(last_loaded_key, 0)
                age_minutes = (time.time() - last_loaded) / 60
                logger.info(f"📦 BULK LOADER: Retrieved cached bulk data for project {project_name} (age: {age_minutes:.1f} minutes)")
                return bulk_data
            return None
        except Exception as e:
            logger.error(f"❌ BULK LOADER: Failed to get cached bulk data: {e}")
            return None
    
    def is_cache_valid(self, max_age_minutes: int = 60, project=None) -> bool:
        """Check if cached data is still valid for the given project"""
        try:
            last_loaded_key = self._get_last_loaded_key(project)
            last_loaded = cache.get(last_loaded_key, 0)
            age_minutes = (time.time() - last_loaded) / 60
            return age_minutes < max_age_minutes
        except:
            return False
    
    def clear_bulk_cache(self, project=None):
        """Clear bulk model cache for the given project"""
        try:
            cache_key = self._get_cache_key(project)
            last_loaded_key = self._get_last_loaded_key(project)
            project_name = project.name if project and hasattr(project, 'name') else 'global'
            
            cache.delete(cache_key)
            cache.delete(last_loaded_key)
            logger.info(f"🧹 BULK LOADER: Cleared bulk model cache for project {project_name}")
        except Exception as e:
            logger.error(f"❌ BULK LOADER: Failed to clear bulk cache: {e}")
    
    async def refresh_models_for_provider(self, provider_id: str, project=None) -> Dict[str, Any]:
        """Refresh models for a specific provider and update bulk cache"""
        try:
            logger.info(f"🔄 BULK LOADER: Refreshing models for {provider_id}")
            
            # Clear cache for this provider
            dynamic_models_service.clear_cache(provider_id)
            
            # Load fresh models
            models = await dynamic_models_service.get_models_for_provider(
                provider_id, 
                use_cache=False,
                project=project
            )
            
            # Get cached bulk data and update it
            bulk_data = self.get_cached_bulk_data(project)
            if bulk_data:
                # Update the provider's models in bulk data
                bulk_data['provider_models'][provider_id] = [asdict(model) for model in models]
                
                # Update statistics
                bulk_data['statistics']['models_per_provider'][provider_id] = len(models)
                bulk_data['statistics']['total_models'] = sum(
                    len(provider_models) 
                    for provider_models in bulk_data['provider_models'].values()
                )
                
                # Update metadata
                bulk_data['metadata']['loaded_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Re-cache updated data (with project context)
                self._cache_bulk_data(bulk_data, project)
                
                logger.info(f"✅ BULK LOADER: Refreshed {len(models)} models for {provider_id}")
                return bulk_data
            else:
                # No bulk data cached, trigger full reload
                return await self.pre_load_all_models(force_refresh=True, project=project)
                
        except Exception as e:
            logger.error(f"❌ BULK LOADER: Failed to refresh models for {provider_id}: {e}")
            raise

# Global bulk loader instance
llm_bulk_loader = LLMBulkLoaderService()
