import asyncio
from typing import List, Dict, Any
from django.contrib.auth import get_user_model
from users.models import APIKeyConfig, LLMProvider, LLMComparison, LLMResponse as LLMResponseModel, DashboardIcon
from .providers import get_provider_class
from .encryption import decrypt_api_key

User = get_user_model()

class LLMComparisonService:
    def __init__(self, user: User):
        self.user = user
    
    def has_llm_eval_access(self) -> bool:
        """Check if user has access to LLM Eval icon"""
        try:
            llm_eval_icon = DashboardIcon.objects.get(route='/features/llm-eval')
            
            # Admin users have access to all icons
            if self.user.is_admin:
                return True
            
            # Check direct user permissions
            if self.user.accessible_icons.filter(id=llm_eval_icon.id).exists():
                return True
            
            # Check group permissions
            user_groups = self.user.groups.all()
            if llm_eval_icon.authorized_groups.filter(id__in=user_groups).exists():
                return True
                
            return False
        except DashboardIcon.DoesNotExist:
            return False
    
    def get_available_providers(self) -> List[LLMProvider]:
        """Get LLM providers available to users with LLM Eval access"""
        if not self.has_llm_eval_access():
            return []
            
        # If user has LLM Eval access, they can use all active providers
        return list(LLMProvider.objects.filter(is_active=True))
    
    def get_api_config_for_provider(self, provider: LLMProvider) -> APIKeyConfig:
        """Get the first available API config for a provider (admin-managed)"""
        return APIKeyConfig.objects.filter(
            provider=provider,
            is_active=True
        ).first()
    
    async def run_comparison(self, prompt: str, provider_ids: List[int], **kwargs) -> Dict[str, Any]:
        """Run parallel comparison across multiple LLM providers"""
        comparison = LLMComparison.objects.create(
            user=self.user,
            prompt=prompt,
            title=kwargs.get('title', '')
        )
        
        providers = LLMProvider.objects.filter(id__in=provider_ids, is_active=True)
        tasks = []
        
        for provider in providers:
            api_config = self.get_api_config_for_provider(provider)
            if api_config:
                task = self._query_single_provider(comparison, provider, api_config, prompt, **kwargs)
                tasks.append(task)
        
        # Run all providers in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'comparison_id': comparison.id,
            'results': [r for r in results if not isinstance(r, Exception)],
            'errors': [str(r) for r in results if isinstance(r, Exception)]
        }
    
    async def _query_single_provider(self, comparison, provider, api_config, prompt, **kwargs):
        """Query a single LLM provider"""
        try:
            # Check usage limits
            if api_config.usage_limit_daily and api_config.usage_count_today >= api_config.usage_limit_daily:
                raise Exception(f"Daily usage limit exceeded for {provider.name}")
            
            # Get provider class and create instance
            provider_class = get_provider_class(provider.provider_type)
            if not provider_class:
                raise Exception(f"Provider type {provider.provider_type} not supported")
            
            decrypted_key = decrypt_api_key(api_config.api_key)
            provider_instance = provider_class(
                api_key=decrypted_key,
                model='default',  # Will be overridden with specific model selection
                max_tokens=provider.max_tokens,
                timeout=provider.timeout_seconds
            )
            
            # Generate response
            response = await provider_instance.generate_response(prompt, **kwargs)
            
            # Save to database
            llm_response = LLMResponseModel.objects.create(
                comparison=comparison,
                provider=provider,
                model_name=response.model,
                response_text=response.text,
                response_time_ms=response.response_time_ms,
                token_count=response.token_count,
                cost_estimate=response.cost_estimate,
                error_message=response.error or ''
            )
            
            # Update usage count
            api_config.usage_count_today += 1
            api_config.save()
            
            return {
                'provider_name': provider.name,
                'response_id': llm_response.id,
                'text': response.text,
                'response_time_ms': response.response_time_ms,
                'token_count': response.token_count,
                'cost_estimate': response.cost_estimate,
                'error': response.error
            }
            
        except Exception as e:
            # Save error to database
            LLMResponseModel.objects.create(
                comparison=comparison,
                provider=provider,
                model_name='unknown',
                response_text='',
                response_time_ms=0,
                error_message=str(e)
            )
            
            return {
                'provider_name': provider.name,
                'error': str(e)
            }
    
    def get_user_comparisons(self, limit: int = 50) -> List[LLMComparison]:
        """Get user's comparison history"""
        return LLMComparison.objects.filter(user=self.user).prefetch_related('responses__provider')[:limit]
    
    def get_comparison_details(self, comparison_id: int) -> LLMComparison:
        """Get detailed comparison with all responses"""
        return LLMComparison.objects.get(
            id=comparison_id, 
            user=self.user
        ).prefetch_related('responses__provider')
