"""
Agent LLM Configuration API Views - Enhanced with API Key Based Model Fetching

Provides REST API endpoints for multi-provider LLM configuration management.
Only shows models when API keys are available and working - no hardcoded fallbacks.
"""

import logging
import asyncio
import concurrent.futures
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from agent_orchestration.dynamic_models_service import dynamic_models_service
from agent_orchestration.llm_bulk_loader import llm_bulk_loader
from users.models import IntelliDocProject, AgentWorkflow

logger = logging.getLogger('agent_llm_api')

def get_user_project(user, project_id=None):
    """
    Get user's project - either specific project_id or user's first project
    Uses project permission system to check access (not just creator)
    """
    try:
        if project_id:
            # Get specific project and check if user has access
            project = IntelliDocProject.objects.get(project_id=project_id)
            # Use project permission system to verify access
            if not project.has_user_access(user):
                logger.warning(f"🚫 PROJECT ACCESS: User {user.email} denied access to project {project.name} (project_id: {project_id})")
                return None
            return project
        else:
            # Get user's first accessible project as default
            # Superusers and admin users can see all projects
            if user.is_superuser or user.is_admin:
                return IntelliDocProject.objects.first()
            
            # Get projects where user is creator or has permissions
            from django.db.models import Q
            created_projects = Q(created_by=user)
            user_permissions = Q(user_permissions__user=user)
            user_groups = user.groups.all()
            group_permissions = Q(group_permissions__group__in=user_groups)
            
            return IntelliDocProject.objects.filter(
                created_projects | user_permissions | group_permissions
            ).distinct().first()
    except IntelliDocProject.DoesNotExist:
        return None

def run_async(async_func):
    """Helper to run async functions in sync context"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create task in executor
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, async_func())
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(async_func())
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(async_func())

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_llm_providers(request):
    """
    Get all available LLM providers with API key status
    
    Query Parameters:
        project_id (optional): Specific project ID to check API keys for
    
    Returns:
        JSON response with list of LLM providers and their API key availability
    """
    try:
        project_id = request.GET.get('project_id')
        project = get_user_project(request.user, project_id)
        
        logger.info(f"🤖 LLM API: Fetching LLM providers with API key status for user {request.user.id}, project: {project.name if project else 'None'}")
        
        providers = []

        for provider_id in ['openai', 'anthropic', 'google']:
            provider_status = dynamic_models_service.get_provider_status(provider_id, project)

            provider_data = {
                'id': provider_id,
                'name': provider_status['name'],
                'description': f"{provider_status['name']} models",
                'status': {
                    'available': provider_status['api_key_valid'],
                    'has_api_key': provider_status['has_api_key'],
                    'api_key_valid': provider_status['api_key_valid'],
                    'message': provider_status['message'],
                    'models_count': 0  # Will be updated after fetching models
                },
                'models': []
            }

            # If provider has valid API key, try to get model count
            if provider_status['api_key_valid']:
                try:
                    # Get models count (use cached if available)
                    async def get_models():
                        return await dynamic_models_service.get_models_for_provider(provider_id, project=project)

                    models = run_async(get_models)
                    provider_data['status']['models_count'] = len(models)
                    provider_data['models'] = [model.id for model in models[:5]]  # Show first 5 model IDs
                except Exception as e:
                    logger.warning(f"⚠️ LLM API: Could not get model count for {provider_id}: {e}")
                    provider_data['status']['models_count'] = 0

            providers.append(provider_data)

        # Add Ollama (local) provider
        ollama_provider = {
            'id': 'ollama',
            'name': 'Ollama (Local)',
            'description': 'Local AI models via Docker - no API key required',
            'status': {
                'available': False,
                'has_api_key': True,
                'api_key_valid': True,
                'message': 'Local AI models via Docker - no API key required',
                'models_count': 0,
            },
            'models': []
        }
        try:
            import urllib.request, json as _json
            req = urllib.request.Request('http://127.0.0.1:11434/api/tags')
            resp = urllib.request.urlopen(req, timeout=5)
            data = _json.loads(resp.read().decode())
            ollama_models = data.get('models', [])
            ollama_provider['status']['available'] = True
            ollama_provider['status']['models_count'] = len(ollama_models)
            ollama_provider['models'] = [m.get('name', '') for m in ollama_models[:5]]
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            ollama_provider['status']['message'] = 'Ollama is not running. Start Docker Desktop and Ollama container.'
        providers.append(ollama_provider)
        
        available_count = sum(1 for p in providers if p['status']['available'])
        
        logger.info(f"✅ LLM API: Returning {len(providers)} providers ({available_count} available)")
        
        return Response({
            'providers': providers,
            'total_count': len(providers),
            'available_count': available_count,
            'api_version': 'api_key_based_v1',
            'system_type': 'api_key_based_aicc_llm',
            'supports_dynamic_fetching': True,
            'requires_api_keys': True
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ LLM API: Failed to fetch providers: {e}")
        return Response({
            'error': 'Failed to fetch LLM providers',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_llm_models(request):
    """
    Get all available LLM models based on API key availability
    
    Query Parameters:
        provider_id (optional): Filter models by provider
        agent_type (optional): Get recommended models for agent type
        use_cache (optional): Whether to use cached results (default: true)
        force_refresh (optional): Force refresh from API (default: false)
        project_id (optional): Specific project ID to check API keys for
    """
    try:
        provider_id = request.GET.get('provider_id')
        agent_type = request.GET.get('agent_type')
        use_cache = request.GET.get('use_cache', 'true').lower() == 'true'
        force_refresh = request.GET.get('force_refresh', 'false').lower() == 'true'
        project_id = request.GET.get('project_id')
        
        project = get_user_project(request.user, project_id)
        
        logger.info(f"🤖 DYNAMIC LLM API: Fetching models (provider: {provider_id}, agent_type: {agent_type}, use_cache: {use_cache}, force_refresh: {force_refresh}, project: {project.name if project else 'None'})")
        
        # Handle force refresh
        if force_refresh:
            if provider_id:
                dynamic_models_service.clear_cache(provider_id)
            else:
                dynamic_models_service.clear_cache()
            use_cache = False
        
        async def fetch_models_async():
            if provider_id:
                # Check if provider has valid API key
                provider_status = dynamic_models_service.get_provider_status(provider_id, project)
                
                if not provider_status['api_key_valid']:
                    # Return special response for providers without API keys
                    return {
                        'provider': provider_id,
                        'models': [],
                        'status': provider_status,
                        'message': f"Models not available: {provider_status['message']}"
                    }
                
                # Get models for specific provider
                models = await dynamic_models_service.get_models_for_provider(
                    provider_id, 
                    use_cache=use_cache,
                    project=project
                )
                return {provider_id: models}
            else:
                # Get models for all providers with valid API keys
                return await dynamic_models_service.get_all_models(
                    use_cache=use_cache,
                    project=project
                )
        
        # Run async function
        provider_models = run_async(fetch_models_async)
        
        # Handle single provider response with no API key
        if provider_id and isinstance(provider_models, dict) and 'provider' in provider_models:
            return Response({
                'models': [],
                'total_count': 0,
                'filter_type': f'provider_{provider_id}',
                'provider_id': provider_id,
                'provider_status': provider_models['status'],
                'message': provider_models['message'],
                'api_version': 'api_key_based_v1',
                'system_type': 'api_key_based_aicc_llm',
                'requires_api_keys': True
            }, status=status.HTTP_200_OK)
        
        # Format response
        if provider_id == 'ollama':
            # Handle Ollama provider separately — query local Ollama instance
            models_list = []
            try:
                import urllib.request, json as _json
                req = urllib.request.Request('http://127.0.0.1:11434/api/tags')
                resp = urllib.request.urlopen(req, timeout=10)
                data = _json.loads(resp.read().decode())
                for m in data.get('models', []):
                    models_list.append({
                        'id': m.get('name', ''),
                        'name': m.get('name', ''),
                        'display_name': m.get('name', '').split(':')[0].title(),
                        'provider': 'ollama',
                        'context_length': 0,
                        'cost_per_1k_tokens': 0,
                        'capabilities': ['chat', 'completion'],
                        'recommended_for': [],
                        'is_available': True,
                        'last_checked': m.get('modified_at', ''),
                        'parameter_size': m.get('details', {}).get('parameter_size', ''),
                        'family': m.get('details', {}).get('family', ''),
                        'quantization': m.get('details', {}).get('quantization_level', ''),
                    })
            except Exception as e:
                logger.debug(f"Ollama not available for model listing: {e}")
            response_type = 'provider_ollama'
        elif provider_id:
            models_list = provider_models.get(provider_id, [])
            response_type = f'provider_{provider_id}'
        else:
            models_list = []
            providers_with_models = []
            providers_without_keys = []

            for provider, models in provider_models.items():
                if len(models) > 0:
                    providers_with_models.append(provider)
                    for model in models:
                        model_dict = {
                            'id': model.id,
                            'name': model.name,
                            'display_name': model.display_name,
                            'provider': model.provider,
                            'context_length': model.context_length,
                            'cost_per_1k_tokens': model.cost_per_1k_tokens,
                            'capabilities': model.capabilities or [],
                            'recommended_for': model.recommended_for or [],
                            'is_available': model.is_available,
                            'last_checked': model.last_checked
                        }
                        models_list.append(model_dict)
                else:
                    providers_without_keys.append(provider)

            # Also include local Ollama models in the full listing
            try:
                import urllib.request, json as _json
                req = urllib.request.Request('http://127.0.0.1:11434/api/tags')
                resp = urllib.request.urlopen(req, timeout=5)
                data = _json.loads(resp.read().decode())
                for m in data.get('models', []):
                    models_list.append({
                        'id': m.get('name', ''),
                        'name': m.get('name', ''),
                        'display_name': m.get('name', '').split(':')[0].title(),
                        'provider': 'ollama',
                        'context_length': 0,
                        'cost_per_1k_tokens': 0,
                        'capabilities': ['chat', 'completion'],
                        'recommended_for': [],
                        'is_available': True,
                        'last_checked': m.get('modified_at', ''),
                    })
                if data.get('models'):
                    providers_with_models.append('ollama')
            except Exception:
                pass  # Ollama not available, skip silently

            response_type = 'all'
        
        # Convert ModelInfo objects to dict for specific provider
        if provider_id and models_list:
            formatted_models = []
            for model in models_list:
                if hasattr(model, 'id'):  # ModelInfo object
                    model_dict = {
                        'id': model.id,
                        'name': model.name,
                        'display_name': model.display_name,
                        'provider': model.provider,
                        'context_length': model.context_length,
                        'cost_per_1k_tokens': model.cost_per_1k_tokens,
                        'capabilities': model.capabilities or [],
                        'recommended_for': model.recommended_for or [],
                        'is_available': model.is_available,
                        'last_checked': model.last_checked
                    }
                    formatted_models.append(model_dict)
                else:  # Already a dict
                    formatted_models.append(model)
            models_list = formatted_models
        
        # Filter by agent type if requested
        if agent_type and response_type == 'all':
            recommended_models = dynamic_models_service.get_recommended_models_for_agent(agent_type, project)
            recommended_ids = [model.id for model in recommended_models]
            # Filter and prioritize recommended models
            recommended_list = [model for model in models_list if model['id'] in recommended_ids]
            other_list = [model for model in models_list if model['id'] not in recommended_ids]
            models_list = recommended_list + other_list
        
        # Get provider statuses for summary
        provider_statuses = {}
        for provider in ['openai', 'anthropic', 'google']:
            provider_statuses[provider] = dynamic_models_service.get_provider_status(provider, project)
        # Add Ollama status
        try:
            import urllib.request as _urllib
            _urllib.urlopen('http://127.0.0.1:11434', timeout=3)
            provider_statuses['ollama'] = {
                'name': 'Ollama (Local)',
                'has_api_key': True,
                'api_key_valid': True,
                'message': 'Local AI models via Docker - no API key required',
            }
        except Exception:
            provider_statuses['ollama'] = {
                'name': 'Ollama (Local)',
                'has_api_key': True,
                'api_key_valid': False,
                'message': 'Ollama is not running',
            }
        
        logger.info(f"✅ DYNAMIC LLM API: Returning {len(models_list)} models ({response_type})")
        
        return Response({
            'models': models_list,
            'total_count': len(models_list),
            'filter_type': response_type,
            'provider_id': provider_id,
            'agent_type': agent_type,
            'provider_statuses': provider_statuses,
            'api_version': 'api_key_based_v1',
            'system_type': 'api_key_based_aicc_llm',
            'cache_used': use_cache,
            'force_refresh': force_refresh,
            'requires_api_keys': True
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ DYNAMIC LLM API: Failed to fetch models: {e}")
        import traceback
        logger.error(f"❌ DYNAMIC LLM API: Traceback: {traceback.format_exc()}")
        return Response({
            'error': 'Failed to fetch LLM models',
            'message': str(e),
            'api_version': 'api_key_based_v1',
            'requires_api_keys': True
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_agent_llm_config(request, project_id, agent_id):
    """
    Get LLM configuration for a specific agent
    
    Args:
        project_id: Project identifier
        agent_id: Agent identifier
    """
    try:
        logger.info(f"🎯 LLM API: Fetching agent LLM config (project: {project_id}, agent: {agent_id})")
        
        # Verify project access using proper permission system
        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            return Response({
                'error': 'Project not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not project.has_user_access(request.user):
            return Response({
                'error': 'You do not have access to this project'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Return default configuration based on available providers
        available_providers = []
        for provider in ['openai', 'anthropic', 'google']:
            provider_status = dynamic_models_service.get_provider_status(provider, project)
            if provider_status['api_key_valid']:
                available_providers.append(provider)
        
        # Use first available provider, or default to openai with warning
        if available_providers:
            default_provider = available_providers[0]
            default_model = 'gpt-4-turbo' if default_provider == 'openai' else \
                           'claude-3-5-sonnet-20241022' if default_provider == 'anthropic' else \
                           'gemini-1.5-flash'
        else:
            default_provider = 'openai'
            default_model = 'gpt-4-turbo'
        
        default_config = {
            'llm_provider': default_provider,
            'llm_model': default_model,
            'temperature': 0.7,
            'max_tokens': 2048,
            'top_p': 1.0,
            'frequency_penalty': 0.0,
            'presence_penalty': 0.0,
            'timeout': 30
        }
        
        config_summary = {
            'provider_name': default_provider.title(),
            'model_name': default_model,
            'has_valid_api_key': len(available_providers) > 0,
            'available_providers': available_providers
        }
        
        logger.info(f"✅ LLM API: Returning agent LLM config")
        
        return Response({
            'agent_id': agent_id,
            'project_id': project_id,
            'llm_config': default_config,
            'config_summary': config_summary,
            'api_version': 'api_key_based_v1',
            'system_type': 'api_key_based_aicc_llm'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ LLM API: Failed to get agent LLM config: {e}")
        return Response({
            'error': 'Failed to get agent LLM configuration',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_agent_llm_config(request, project_id, agent_id):
    """
    Update LLM configuration for a specific agent
    """
    try:
        logger.info(f"💾 LLM API: Updating agent LLM config (project: {project_id}, agent: {agent_id})")
        
        # Verify project access using proper permission system
        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            return Response({
                'error': 'Project not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not project.has_user_access(request.user):
            return Response({
                'error': 'You do not have access to this project'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Extract and validate configuration
        config_data = {
            'llm_provider': request.data.get('llm_provider', 'openai'),
            'llm_model': request.data.get('llm_model', 'gpt-4'),
            'temperature': float(request.data.get('temperature', 0.7)),
            'max_tokens': int(request.data.get('max_tokens', 2048)),
            'top_p': float(request.data.get('top_p', 1.0)),
            'frequency_penalty': float(request.data.get('frequency_penalty', 0.0)),
            'presence_penalty': float(request.data.get('presence_penalty', 0.0)),
            'timeout': int(request.data.get('timeout', 30))
        }
        
        # Validate that the selected provider has a valid API key
        provider_status = dynamic_models_service.get_provider_status(config_data['llm_provider'], project)
        
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check API key validity
        if not provider_status['api_key_valid']:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Provider {config_data['llm_provider']} does not have a valid API key configured")
        
        # Validate temperature
        if not 0 <= config_data['temperature'] <= 2:
            validation_result['valid'] = False
            validation_result['errors'].append('Temperature must be between 0 and 2')
        
        # Validate max_tokens
        if not 1 <= config_data['max_tokens'] <= 32000:
            validation_result['valid'] = False
            validation_result['errors'].append('Max tokens must be between 1 and 32000')
        
        if not validation_result['valid']:
            return Response({
                'error': 'Invalid LLM configuration',
                'validation_errors': validation_result['errors'],
                'warnings': validation_result.get('warnings', [])
            }, status=status.HTTP_400_BAD_REQUEST)
        
        config_summary = {
            'provider_name': config_data['llm_provider'].title(),
            'model_name': config_data['llm_model'],
            'temperature': config_data['temperature'],
            'max_tokens': config_data['max_tokens'],
            'api_key_valid': provider_status['api_key_valid']
        }
        
        logger.info(f"✅ LLM API: Agent LLM config updated successfully")
        
        return Response({
            'agent_id': agent_id,
            'project_id': project_id,
            'llm_config': config_data,
            'config_summary': config_summary,
            'validation_result': validation_result,
            'api_version': 'api_key_based_v1',
            'system_type': 'api_key_based_aicc_llm'
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid parameter values',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"❌ LLM API: Failed to update agent LLM config: {e}")
        return Response({
            'error': 'Failed to update agent LLM configuration',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_llm_config(request):
    """
    Validate LLM configuration without saving
    """
    try:
        logger.info(f"🔍 LLM API: Validating LLM configuration")
        
        # Get project context - required for project-specific API keys
        project_id = request.data.get('project_id')
        project = get_user_project(request.user, project_id)
        
        if not project:
            return Response({
                'error': 'Project context required for LLM configuration validation',
                'message': 'Please specify a project_id to validate LLM configuration'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        config_data = {
            'llm_provider': request.data.get('llm_provider'),
            'llm_model': request.data.get('llm_model'),
            'temperature': request.data.get('temperature'),
            'max_tokens': request.data.get('max_tokens'),
            'top_p': request.data.get('top_p'),
            'frequency_penalty': request.data.get('frequency_penalty'),
            'presence_penalty': request.data.get('presence_penalty')
        }
        
        # Remove None values
        config_data = {k: v for k, v in config_data.items() if v is not None}
        
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check API key validity for provider
        if 'llm_provider' in config_data:
            provider_status = dynamic_models_service.get_provider_status(config_data['llm_provider'], project)
            if not provider_status['api_key_valid']:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Provider {config_data['llm_provider']} does not have a valid project-specific API key")
        
        # Basic validation checks
        if 'temperature' in config_data:
            temp = float(config_data['temperature'])
            if not 0 <= temp <= 2:
                validation_result['valid'] = False
                validation_result['errors'].append('Temperature must be between 0 and 2')
        
        if 'max_tokens' in config_data:
            tokens = int(config_data['max_tokens'])
            if not 1 <= tokens <= 32000:
                validation_result['valid'] = False
                validation_result['errors'].append('Max tokens must be between 1 and 32000')
        
        # Calculate estimated cost if valid
        estimated_cost = None
        if validation_result['valid'] and 'llm_model' in config_data:
            estimated_tokens = request.data.get('estimated_tokens', 1000)
            # Try to get actual cost from model info
            try:
                async def get_models():
                    return await dynamic_models_service.get_models_for_provider(config_data['llm_provider'], project=project)
                
                models = run_async(get_models)
                model = next((m for m in models if m.id == config_data['llm_model']), None)
                cost_rate = model.cost_per_1k_tokens if model else 0.01
            except:
                cost_rate = 0.01  # Fallback rate
            
            estimated_cost = {
                'cost': (estimated_tokens / 1000) * cost_rate,
                'currency': 'USD',
                'tokens': estimated_tokens,
                'rate_per_1k': cost_rate
            }
        
        config_summary = {
            'provider': config_data.get('llm_provider', 'Unknown'),
            'model': config_data.get('llm_model', 'Unknown'),
            'valid': validation_result['valid']
        }
        
        logger.info(f"✅ LLM API: Configuration validation completed (valid: {validation_result['valid']})")
        
        return Response({
            'validation_result': validation_result,
            'config_summary': config_summary,
            'estimated_cost': estimated_cost,
            'config_data': config_data,
            'api_version': 'api_key_based_v1',
            'system_type': 'api_key_based_aicc_llm'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ LLM API: Configuration validation failed: {e}")
        return Response({
            'error': 'Configuration validation failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_default_agent_config(request, agent_type):
    """
    Get default LLM configuration for agent type - based on available providers
    """
    try:
        logger.info(f"🎯 LLM API: Fetching default config for {agent_type}")
        
        # Get project context - this endpoint requires project context for project-specific API keys
        project_id = request.GET.get('project_id')
        project = get_user_project(request.user, project_id)
        
        if not project:
            return Response({
                'error': 'Project context required for agent configuration',
                'message': 'Please specify a project_id to configure agent LLM settings'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get available providers for this project
        available_providers = []
        for provider in ['openai', 'anthropic', 'google']:
            provider_status = dynamic_models_service.get_provider_status(provider, project)
            if provider_status['api_key_valid']:
                available_providers.append(provider)
        
        # Agent type specific defaults - prefer available providers
        agent_defaults = {
            'AssistantAgent': {
                'preferred_providers': ['openai', 'anthropic'],
                'models': {'openai': 'gpt-4-turbo', 'anthropic': 'claude-3-5-sonnet-20241022'},
                'temperature': 0.7,
                'max_tokens': 2048
            },
            'UserProxyAgent': {
                'preferred_providers': ['openai', 'anthropic'],
                'models': {'openai': 'gpt-3.5-turbo', 'anthropic': 'claude-3-5-haiku-20241022'},
                'temperature': 0.3,
                'max_tokens': 1024
            },
            'GroupChatManager': {
                'preferred_providers': ['anthropic', 'openai'],
                'models': {'anthropic': 'claude-3-5-sonnet-20241022', 'openai': 'gpt-4-turbo'},
                'temperature': 0.5,
                'max_tokens': 1024
            },
            'DelegateAgent': {
                'preferred_providers': ['anthropic', 'openai'],
                'models': {'anthropic': 'claude-3-5-haiku-20241022', 'openai': 'gpt-3.5-turbo'},
                'temperature': 0.4,
                'max_tokens': 1024
            }
        }
        
        defaults = agent_defaults.get(agent_type, agent_defaults['AssistantAgent'])
        
        # Find best available provider
        selected_provider = None
        selected_model = None
        
        for preferred_provider in defaults['preferred_providers']:
            if preferred_provider in available_providers:
                selected_provider = preferred_provider
                selected_model = defaults['models'].get(preferred_provider)
                break
        
        # If no preferred provider available, use any available provider
        if not selected_provider and available_providers:
            selected_provider = available_providers[0]
            selected_model = defaults['models'].get(selected_provider, 'gpt-4-turbo')
        
        # Fallback if no providers available
        if not selected_provider:
            selected_provider = 'openai'
            selected_model = 'gpt-4-turbo'
        
        default_config = {
            'llm_provider': selected_provider,
            'llm_model': selected_model,
            'temperature': defaults['temperature'],
            'max_tokens': defaults['max_tokens']
        }
        
        # Get recommended models from available providers only
        recommended_models = []
        for provider in available_providers:
            try:
                async def get_models():
                    return await dynamic_models_service.get_models_for_provider(provider, project=project)
                
                models = run_async(get_models)
                for model in models[:3]:  # Top 3 models per provider
                    if model.recommended_for and agent_type in model.recommended_for:
                        recommended_models.append({
                            'provider': model.provider,
                            'model': model.id,
                            'display_name': model.display_name,
                            'cost_per_1k': model.cost_per_1k_tokens,
                            'capabilities': model.capabilities or [],
                            'reason': f'Optimized for {agent_type}'
                        })
            except Exception as e:
                logger.warning(f"Could not get models for {provider}: {e}")
        
        config_summary = {
            'agent_type': agent_type,
            'recommended_provider': selected_provider,
            'recommended_model': selected_model,
            'available_providers': available_providers,
            'has_valid_providers': len(available_providers) > 0
        }
        
        logger.info(f"✅ LLM API: Returning default config for {agent_type}")
        
        return Response({
            'agent_type': agent_type,
            'default_config': default_config,
            'recommended_models': recommended_models,
            'config_summary': config_summary,
            'available_providers': available_providers,
            'api_version': 'api_key_based_v1',
            'system_type': 'api_key_based_aicc_llm'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ LLM API: Failed to get default config: {e}")
        return Response({
            'error': 'Failed to get default agent configuration',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _inject_ollama_into_bulk_data(bulk_data):
    """Inject Ollama models and status into bulk data dict (works on cached or fresh data)."""
    ollama_models_list = []
    try:
        import urllib.request, json as _json
        req = urllib.request.Request('http://127.0.0.1:11434/api/tags')
        resp = urllib.request.urlopen(req, timeout=5)
        tag_data = _json.loads(resp.read().decode())
        for m in tag_data.get('models', []):
            ollama_models_list.append({
                'id': m.get('name', ''),
                'name': m.get('name', ''),
                'display_name': m.get('name', '').split(':')[0].title(),
                'provider': 'ollama',
                'context_length': 0,
                'cost_per_1k_tokens': 0,
                'capabilities': ['chat', 'completion'],
                'recommended_for': [],
                'is_available': True,
            })
    except Exception:
        pass

    bulk_data.setdefault('provider_models', {})
    bulk_data.setdefault('provider_statuses', {})
    bulk_data.setdefault('statistics', {'total_models': 0, 'available_providers': 0})

    bulk_data['provider_models']['ollama'] = ollama_models_list
    bulk_data['provider_statuses']['ollama'] = {
        'has_api_key': True,
        'api_key_valid': True,
        'models_available': len(ollama_models_list) > 0,
        'message': f'Local AI - {len(ollama_models_list)} model(s)' if ollama_models_list else 'Ollama unavailable - start Docker',
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bulk_load_all_models(request):
    """
    Bulk load all models from all providers for Agent Orchestration interface
    This endpoint pre-loads and caches all models to eliminate repetitive API calls
    
    Query Parameters:
        force_refresh (optional): Force refresh from APIs (default: false)
        max_age_minutes (optional): Maximum age of cached data in minutes (default: 60)
        project_id (optional): Specific project ID to check API keys for
    """
    try:
        force_refresh = request.GET.get('force_refresh', 'false').lower() == 'true'
        max_age_minutes = int(request.GET.get('max_age_minutes', '60'))
        project_id = request.GET.get('project_id')
        
        logger.info(f"🔍 BULK LOAD API: Request received - project_id param: {project_id}, user: {request.user.email}")
        
        project = get_user_project(request.user, project_id)
        
        if not project:
            logger.error(f"❌ BULK LOAD API: Project not found or user doesn't have access - project_id: {project_id}, user: {request.user.email}")
        else:
            logger.info(f"✅ BULK LOAD API: Project found - {project.name} (ID: {project.project_id})")
        
        logger.info(f"🚀 BULK LOAD API: Starting bulk model loading (force_refresh: {force_refresh}, project: {project.name if project else 'None'})")
        
        # Check if we have valid cached data for this project
        if not force_refresh and llm_bulk_loader.is_cache_valid(max_age_minutes, project=project):
            cached_data = llm_bulk_loader.get_cached_bulk_data(project=project)
            if cached_data:
                logger.info(f"✅ BULK LOAD API: Returning cached bulk model data for project {project.name if project else 'global'}")
                # Always inject Ollama (even into cached data)
                _inject_ollama_into_bulk_data(cached_data)
                return Response({
                    **cached_data,
                    'source': 'cache',
                    'cache_hit': True
                }, status=status.HTTP_200_OK)
        
        # Perform bulk loading
        async def bulk_load():
            return await llm_bulk_loader.pre_load_all_models(force_refresh=force_refresh, project=project)
        
        bulk_data = run_async(bulk_load)

        # Inject Ollama into bulk data (always — ensure it shows in provider dropdown)
        _inject_ollama_into_bulk_data(bulk_data)

        # Add response metadata
        response_data = {
            **bulk_data,
            'source': 'api' if force_refresh else 'fresh_load',
            'cache_hit': False,
            'request_params': {
                'force_refresh': force_refresh,
                'max_age_minutes': max_age_minutes
            }
        }

        logger.info(
            f"✅ BULK LOAD API: Completed bulk loading - "
            f"{response_data['statistics']['total_models']} models from "
            f"{response_data['statistics']['available_providers']} providers"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ BULK LOAD API: Bulk loading failed: {e}")
        import traceback
        logger.error(f"❌ BULK LOAD API: Traceback: {traceback.format_exc()}")
        return Response({
            'error': 'Bulk model loading failed',
            'message': str(e),
            'api_version': 'bulk_loader_v1',
            'fallback_available': True
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_provider_models(request, provider_id):
    """
    Refresh models for a specific provider and update bulk cache
    
    Args:
        provider_id: Provider to refresh ('openai', 'anthropic', 'google')
    Query Parameters:
        project_id (optional): Specific project ID to check API keys for
    """
    try:
        project_id = request.GET.get('project_id') or request.data.get('project_id')
        project = get_user_project(request.user, project_id)
        
        logger.info(f"🔄 PROVIDER REFRESH API: Refreshing models for {provider_id} (project: {project.name if project else 'None'})")
        
        if provider_id not in ['openai', 'anthropic', 'google', 'ollama']:
            return Response({
                'error': 'Invalid provider ID',
                'valid_providers': ['openai', 'anthropic', 'google', 'ollama']
            }, status=status.HTTP_400_BAD_REQUEST)

        # Handle Ollama refresh separately (local, no bulk loader)
        if provider_id == 'ollama':
            ollama_models = []
            try:
                import urllib.request, json as _json
                req = urllib.request.Request('http://127.0.0.1:11434/api/tags')
                resp = urllib.request.urlopen(req, timeout=10)
                data = _json.loads(resp.read().decode())
                for m in data.get('models', []):
                    ollama_models.append({
                        'id': m.get('name', ''),
                        'name': m.get('name', ''),
                        'display_name': m.get('name', '').split(':')[0].title(),
                        'provider': 'ollama',
                    })
            except Exception as e:
                logger.warning(f"Ollama refresh failed: {e}")
            return Response({
                'provider_id': 'ollama',
                'models_count': len(ollama_models),
                'models': ollama_models,
                'api_version': 'bulk_loader_v1'
            }, status=status.HTTP_200_OK)

        # Refresh models for specific provider with project context
        async def refresh_provider():
            return await llm_bulk_loader.refresh_models_for_provider(provider_id, project=project)

        updated_bulk_data = run_async(refresh_provider)

        provider_models_count = len(updated_bulk_data['provider_models'].get(provider_id, []))

        logger.info(f"✅ PROVIDER REFRESH API: Refreshed {provider_models_count} models for {provider_id}")

        return Response({
            'provider_id': provider_id,
            'models_count': provider_models_count,
            'bulk_data': updated_bulk_data,
            'refresh_timestamp': updated_bulk_data['metadata']['loaded_at'],
            'api_version': 'bulk_loader_v1'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ PROVIDER REFRESH API: Failed to refresh {provider_id}: {e}")
        return Response({
            'error': f'Failed to refresh provider {provider_id}',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_model_cache(request):
    """
    Clear all model caches to force fresh loading
    """
    try:
        logger.info("🧹 CACHE CLEAR API: Clearing all model caches")
        
        # Clear both individual provider caches and bulk cache
        dynamic_models_service.clear_cache()
        llm_bulk_loader.clear_bulk_cache()
        
        logger.info("✅ CACHE CLEAR API: All caches cleared successfully")
        
        return Response({
            'message': 'All model caches cleared successfully',
            'cleared_caches': ['provider_models', 'bulk_models'],
            'next_load_will_be_fresh': True,
            'api_version': 'bulk_loader_v1'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CACHE CLEAR API: Failed to clear caches: {e}")
        return Response({
            'error': 'Failed to clear model caches',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_cost_estimate(request):
    """
    Calculate cost estimate for LLM configuration - only for available providers
    """
    try:
        logger.info(f"💰 LLM API: Calculating cost estimate")
        
        # Get project context - required for project-specific API keys
        project_id = request.data.get('project_id')
        project = get_user_project(request.user, project_id)
        
        if not project:
            return Response({
                'error': 'Project context required for cost estimation',
                'message': 'Please specify a project_id to calculate LLM costs'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        provider = request.data.get('llm_provider', 'openai')
        model = request.data.get('llm_model', 'gpt-4')
        estimated_tokens = int(request.data.get('estimated_tokens', 1000))
        workflow_complexity = request.data.get('workflow_complexity', 'medium')
        
        # Check if provider has valid API key
        provider_status = dynamic_models_service.get_provider_status(provider, project)
        
        if not provider_status['api_key_valid']:
            return Response({
                'error': f'Provider {provider} does not have a valid API key',
                'provider_status': provider_status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get actual cost from model info
        try:
            async def get_models():
                return await dynamic_models_service.get_models_for_provider(provider, project=project)
            
            models = run_async(get_models)
            model_info = next((m for m in models if m.id == model), None)
            if model_info and model_info.cost_per_1k_tokens:
                cost_rate = model_info.cost_per_1k_tokens
            else:
                # Fallback cost rates
                cost_per_1k = {
                    'gpt-4-turbo': 0.01,
                    'gpt-4': 0.03,
                    'gpt-3.5-turbo': 0.002,
                    'claude-3-5-sonnet-20241022': 0.003,
                    'claude-3-opus-20240229': 0.015,
                    'gemini-1.5-flash': 0.00075
                }
                cost_rate = cost_per_1k.get(model, 0.01)
        except Exception as e:
            logger.warning(f"Could not get model cost info: {e}")
            cost_rate = 0.01
        
        # Complexity multipliers
        complexity_multipliers = {
            'simple': 0.5,
            'medium': 1.0,
            'complex': 2.0,
            'enterprise': 5.0
        }
        
        adjusted_tokens = int(estimated_tokens * complexity_multipliers.get(workflow_complexity, 1.0))
        total_cost = (adjusted_tokens / 1000) * cost_rate
        
        cost_estimate = {
            'cost': total_cost,
            'currency': 'USD',
            'tokens': adjusted_tokens,
            'cost_per_1k_tokens': cost_rate
        }
        
        cost_breakdown = {
            'base_tokens': estimated_tokens,
            'complexity_multiplier': complexity_multipliers.get(workflow_complexity, 1.0),
            'adjusted_tokens': adjusted_tokens,
            'cost_per_token': total_cost / adjusted_tokens if adjusted_tokens > 0 else 0,
            'workflow_complexity': workflow_complexity,
            'provider_has_api_key': provider_status['api_key_valid']
        }
        
        logger.info(f"✅ LLM API: Cost estimate calculated: ${total_cost:.6f}")
        
        return Response({
            'cost_estimate': cost_estimate,
            'cost_breakdown': cost_breakdown,
            'provider_status': provider_status,
            'api_version': 'api_key_based_v1',
            'system_type': 'api_key_based_aicc_llm'
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid parameters for cost calculation',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"❌ LLM API: Cost calculation failed: {e}")
        return Response({
            'error': 'Cost calculation failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
