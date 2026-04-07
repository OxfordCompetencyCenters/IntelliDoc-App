import asyncio
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
import requests
import time

from users.models import (
    LLMProvider, APIKeyConfig, LLMComparison, LLMResponse
)
from api.permissions import IsAdminUser
from .serializers import (
    LLMProviderSerializer, APIKeyConfigSerializer, LLMComparisonSerializer,
    LLMComparisonCreateSerializer, LLMResponseSerializer
)
from .services import LLMComparisonService

User = get_user_model()

class LLMProviderViewSet(viewsets.ModelViewSet):
    queryset = LLMProvider.objects.all()
    serializer_class = LLMProviderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get providers available to the current user"""
        try:
            service = LLMComparisonService(request.user)
            providers = service.get_available_providers()
            serializer = self.get_serializer(providers, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def models(self, request, pk=None):
        """Get available models for a specific provider"""
        try:
            provider = self.get_object()
            service = LLMComparisonService(request.user)
            
            # Check if user has access to LLM Eval
            if not service.has_llm_eval_access():
                return Response({'detail': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
            
            # Get API config for this provider
            api_config = service.get_api_config_for_provider(provider)
            if not api_config:
                return Response({'models': [], 'error': 'No API key configured'})
            
            # Get models from ModelService
            from .model_service import ModelService
            from .encryption import decrypt_api_key
            
            try:
                decrypted_key = decrypt_api_key(api_config.api_key)
                models = ModelService.get_models_for_provider(provider.provider_type, decrypted_key)
                return Response({'models': models})
            except Exception as model_error:
                return Response({'models': [], 'error': f'Failed to fetch models: {str(model_error)}'})
            
        except Exception as e:
            return Response({'models': [], 'error': str(e)})

class APIKeyConfigViewSet(viewsets.ModelViewSet):
    queryset = APIKeyConfig.objects.all()
    serializer_class = APIKeyConfigSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        # Only show API keys created by the current user or if user is admin
        if self.request.user.is_admin:
            return APIKeyConfig.objects.all()
        return APIKeyConfig.objects.filter(created_by=self.request.user)

class LLMComparisonViewSet(viewsets.ModelViewSet):
    queryset = LLMComparison.objects.none()  # Default queryset, will be overridden by get_queryset
    serializer_class = LLMComparisonSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LLMComparison.objects.filter(user=self.request.user).prefetch_related('responses__provider')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LLMComparisonCreateSerializer
        return LLMComparisonSerializer
    
    def create(self, request):
        """Create a new LLM comparison by running parallel queries"""
        print(f"🔍 Creating LLM comparison - User: {request.user.email}")
        print(f"📝 Request data: {request.data}")
        
        serializer = LLMComparisonCreateSerializer(data=request.data)
        if not serializer.is_valid():
            print(f"❌ Serializer validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            service = LLMComparisonService(request.user)
            
            # Check if user has access
            if not service.has_llm_eval_access():
                return Response({
                    'success': False,
                    'error': 'You do not have access to LLM Eval feature'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if any providers are available
            provider_configs = serializer.validated_data['provider_configs']
            available_providers = service.get_available_providers()
            
            if not available_providers:
                return Response({
                    'success': False,
                    'error': 'No LLM providers are configured. Please contact your administrator.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if requested providers exist
            available_ids = [p.id for p in available_providers]
            requested_ids = [config['provider_id'] for config in provider_configs]
            invalid_ids = [pid for pid in requested_ids if pid not in available_ids]
            
            if invalid_ids:
                return Response({
                    'success': False,
                    'error': f'Invalid provider IDs: {invalid_ids}. Available providers: {available_ids}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Run actual LLM comparison using the service
            try:
                # Create the comparison first
                comparison = LLMComparison.objects.create(
                    user=request.user,
                    prompt=serializer.validated_data['prompt'],
                    title=serializer.validated_data.get('title', '')
                )
                
                successful_responses = 0
                errors = []
                
                # Process each provider configuration synchronously to avoid async issues
                for config in provider_configs:
                    provider_id = config['provider_id']
                    model_name = config['model_name']
                    try:
                        provider = LLMProvider.objects.get(id=provider_id)
                        api_config = service.get_api_config_for_provider(provider)
                        
                        if not api_config:
                            errors.append(f"No API key configured for {provider.name}")
                            continue
                            
                        # Import and create provider instance
                        from llm_eval.providers import get_provider_class
                        from llm_eval.encryption import decrypt_api_key
                        
                        provider_class = get_provider_class(provider.provider_type)
                        if not provider_class:
                            errors.append(f"Provider type {provider.provider_type} not supported")
                            continue
                        
                        # Decrypt API key
                        decrypted_key = decrypt_api_key(api_config.api_key)
                        
                        # Make synchronous API call based on provider type
                        if provider.provider_type == 'openai':
                            start_time = time.time()
                            
                            headers = {
                                "Authorization": f"Bearer {decrypted_key}",
                                "Content-Type": "application/json"
                            }
                            
                            data = {
                                "model": model_name,
                                "messages": [{"role": "user", "content": serializer.validated_data['prompt']}],
                                "max_tokens": provider.max_tokens,
                                "temperature": serializer.validated_data.get('temperature', 0.7)
                            }
                            
                            print(f"🚀 Making OpenAI API call for provider {provider.name}...")
                            print(f"🔑 API key length: {len(decrypted_key)} characters")
                            print(f"📄 Request data: {data}")
                            
                            response = requests.post(
                                "https://api.openai.com/v1/chat/completions",
                                headers=headers,
                                json=data,
                                timeout=provider.timeout_seconds
                            )
                            
                            response_time_ms = int((time.time() - start_time) * 1000)
                            print(f"⚙️ Response status: {response.status_code}")
                            print(f"⏱️ Response time: {response_time_ms}ms")
                            
                            if response.status_code == 200:
                                response_data = response.json()
                                print(f"✅ Success! Response: {response_data}")
                                text = response_data["choices"][0]["message"]["content"]
                                token_count = response_data.get("usage", {}).get("total_tokens", 0)
                                
                                # Calculate cost estimate based on actual model
                                if "gpt-4" in model_name.lower():
                                    cost_estimate = (token_count / 1000) * 0.03
                                else:
                                    cost_estimate = (token_count / 1000) * 0.002
                                
                                # Create successful response
                                LLMResponse.objects.create(
                                    comparison=comparison,
                                    provider=provider,
                                    model_name=model_name,
                                    response_text=text,
                                    response_time_ms=response_time_ms,
                                    token_count=token_count,
                                    cost_estimate=cost_estimate
                                )
                                
                                successful_responses += 1
                                print(f"✅ Successfully created response for {provider.name}")
                                
                                # Update usage count
                                api_config.usage_count_today += 1
                                api_config.save()
                                
                            else:
                                print(f"❌ OpenAI API error - Status: {response.status_code}")
                                print(f"❌ Response content: {response.content}")
                                
                                try:
                                    error_data = response.json() if response.content else {}
                                    error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                                except:
                                    error_msg = f"HTTP {response.status_code} - {response.text[:200]}"
                                
                                LLMResponse.objects.create(
                                    comparison=comparison,
                                    provider=provider,
                                    model_name=model_name,
                                    response_text="",
                                    response_time_ms=response_time_ms,
                                    error_message=f"OpenAI API error: {error_msg}"
                                )
                                
                                errors.append(f"{provider.name}: {error_msg}")
                        
                        elif provider.provider_type == 'gemini':
                            start_time = time.time()
                            
                            headers = {
                                "Content-Type": "application/json"
                            }
                            
                            # Prepare request for Gemini API
                            # Use higher token limit for Gemini to avoid truncation
                            max_tokens = min(provider.max_tokens * 2, 4000)  # Increase limit but cap at 4000
                            
                            data = {
                                "contents": [{
                                    "parts": [{
                                        "text": serializer.validated_data['prompt']
                                    }]
                                }],
                                "generationConfig": {
                                    "temperature": serializer.validated_data.get('temperature', 0.7),
                                    "maxOutputTokens": max_tokens
                                }
                            }
                            
                            # Handle different model types - some models use different endpoints
                            if model_name.startswith('gemma'):
                                # Gemma models might need different handling
                                print(f"⚠️ Warning: {model_name} is a Gemma model, may have different API format")
                                # For now, try the same endpoint but be prepared for different response format
                            
                            # Construct Gemini API URL with API key
                            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={decrypted_key}"
                            
                            print(f"🚀 Making Gemini API call for provider {provider.name}...")
                            print(f"🔑 API key length: {len(decrypted_key)} characters")
                            print(f"📄 Model: {model_name}")
                            print(f"🔗 URL: {api_url}")
                            print(f"📄 Request data: {data}")
                            
                            response = requests.post(
                                api_url,
                                headers=headers,
                                json=data,
                                timeout=provider.timeout_seconds
                            )
                            
                            response_time_ms = int((time.time() - start_time) * 1000)
                            print(f"⚙️ Response status: {response.status_code}")
                            print(f"⏱️ Response time: {response_time_ms}ms")
                            
                            if response.status_code == 200:
                                response_data = response.json()
                                print(f"✅ Gemini Success! Full Response: {response_data}")
                                
                                # Extract text from Gemini response - handle different response formats
                                text = None
                                safety_blocked = False
                                
                                # Check for candidates structure
                                if 'candidates' in response_data and len(response_data['candidates']) > 0:
                                    candidate = response_data['candidates'][0]
                                    print(f"🔍 Candidate structure: {candidate}")
                                    
                                    # Check if response was blocked or incomplete
                                    if 'finishReason' in candidate:
                                        finish_reason = candidate['finishReason']
                                        print(f"🔍 Finish reason: {finish_reason}")
                                        
                                        if finish_reason in ['SAFETY', 'RECITATION', 'OTHER']:
                                            safety_blocked = True
                                            error_msg = f"Gemini blocked response due to: {finish_reason}"
                                            print(f"⚠️ {error_msg}")
                                        elif finish_reason == 'MAX_TOKENS':
                                            # Handle max tokens case - response may be incomplete
                                            print(f"⚠️ Response hit MAX_TOKENS limit - may be incomplete")
                                            # Don't block, but note this in the response
                                    
                                    if not safety_blocked and 'content' in candidate:
                                        content = candidate['content']
                                        print(f"🔍 Content structure: {content}")
                                        
                                        if 'parts' in content and len(content['parts']) > 0:
                                            part = content['parts'][0]
                                            print(f"🔍 Part structure: {part}")
                                            
                                            if 'text' in part:
                                                text = part['text']
                                                print(f"✅ Extracted text: {text[:200]}...")
                                            else:
                                                print(f"❌ No 'text' field in part: {list(part.keys())}")
                                        else:
                                            print(f"❌ No 'parts' in content or empty parts: {content}")
                                            # Check if this is a MAX_TOKENS case with empty response
                                            if 'finishReason' in candidate and candidate['finishReason'] == 'MAX_TOKENS':
                                                # Create a response indicating the issue
                                                text = "[Response was truncated - model used all available tokens for internal processing. Please try with a shorter prompt or simpler request.]"
                                                print(f"⚠️ Created fallback text for MAX_TOKENS case")
                                    elif not safety_blocked:
                                        print(f"❌ No 'content' in candidate: {list(candidate.keys())}")
                                        
                                        # Check for alternative response format
                                        if 'output' in candidate:
                                            text = candidate['output']
                                            print(f"✅ Found text in 'output' field: {text[:200]}...")
                                else:
                                    print(f"❌ No candidates in response: {list(response_data.keys())}")
                                    
                                    # Check for alternative response formats
                                    if 'text' in response_data:
                                        text = response_data['text']
                                        print(f"✅ Found text in root 'text' field: {text[:200]}...")
                                    elif 'generated_text' in response_data:
                                        text = response_data['generated_text']
                                        print(f"✅ Found text in 'generated_text' field: {text[:200]}...")
                                
                                if text:
                                    # Check if this was a MAX_TOKENS case and add note
                                    finish_reason = response_data.get('candidates', [{}])[0].get('finishReason', '')
                                    if finish_reason == 'MAX_TOKENS':
                                        text += "\n\n[Note: Response may be incomplete due to token limit.]"
                                    
                                    # Estimate token count (Gemini doesn't always provide usage stats)
                                    token_count = len(text.split()) * 1.3  # Rough estimate
                                    
                                    # Use actual token count from response if available
                                    if 'usageMetadata' in response_data:
                                        usage_meta = response_data['usageMetadata']
                                        actual_tokens = usage_meta.get('totalTokenCount', 0)
                                        if actual_tokens > 0:
                                            token_count = actual_tokens
                                            print(f"✅ Using actual token count from API: {token_count}")
                                    
                                    # Calculate cost estimate for Gemini (rough estimates)
                                    cost_estimate = (token_count / 1000) * 0.001  # Approximate Gemini pricing
                                    
                                    # Create successful response
                                    LLMResponse.objects.create(
                                        comparison=comparison,
                                        provider=provider,
                                        model_name=model_name,
                                        response_text=text,
                                        response_time_ms=response_time_ms,
                                        token_count=int(token_count),
                                        cost_estimate=cost_estimate
                                    )
                                    
                                    successful_responses += 1
                                    print(f"✅ Successfully created response for {provider.name}")
                                    
                                    # Update usage count
                                    api_config.usage_count_today += 1
                                    api_config.save()
                                elif safety_blocked:
                                    # Handle safety filter blocks specifically
                                    LLMResponse.objects.create(
                                        comparison=comparison,
                                        provider=provider,
                                        model_name=model_name,
                                        response_text="",
                                        response_time_ms=response_time_ms,
                                        error_message=f"Gemini safety filter: {error_msg}"
                                    )
                                    errors.append(f"{provider.name}: {error_msg}")
                                else:
                                    error_msg = f"Could not extract text from Gemini response. Response structure: {response_data}"
                                    print(f"❌ {error_msg}")
                                    LLMResponse.objects.create(
                                        comparison=comparison,
                                        provider=provider,
                                        model_name=model_name,
                                        response_text="",
                                        response_time_ms=response_time_ms,
                                        error_message=f"Gemini API error: {error_msg}"
                                    )
                                    errors.append(f"{provider.name}: {error_msg}")
                                    
                            else:
                                print(f"❌ Gemini API error - Status: {response.status_code}")
                                print(f"❌ Response content: {response.content}")
                                
                                try:
                                    error_data = response.json() if response.content else {}
                                    error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                                except:
                                    error_msg = f"HTTP {response.status_code} - {response.text[:200]}"
                                
                                LLMResponse.objects.create(
                                    comparison=comparison,
                                    provider=provider,
                                    model_name=model_name,
                                    response_text="",
                                    response_time_ms=response_time_ms,
                                    error_message=f"Gemini API error: {error_msg}"
                                )
                                
                                errors.append(f"{provider.name}: {error_msg}")
                        
                        elif provider.provider_type == 'claude':
                            start_time = time.time()
                            
                            headers = {
                                "x-api-key": decrypted_key,
                                "Content-Type": "application/json",
                                "anthropic-version": "2023-06-01"
                            }
                            
                            # Prepare request for Claude API
                            data = {
                                "model": model_name,
                                "max_tokens": provider.max_tokens,
                                "temperature": serializer.validated_data.get('temperature', 0.7),
                                "messages": [{
                                    "role": "user",
                                    "content": serializer.validated_data['prompt']
                                }]
                            }
                            
                            print(f"🚀 Making Claude API call for provider {provider.name}...")
                            print(f"🔑 API key length: {len(decrypted_key)} characters")
                            print(f"📄 Model: {model_name}")
                            
                            response = requests.post(
                                "https://api.anthropic.com/v1/messages",
                                headers=headers,
                                json=data,
                                timeout=provider.timeout_seconds
                            )
                            
                            response_time_ms = int((time.time() - start_time) * 1000)
                            print(f"⚙️ Response status: {response.status_code}")
                            print(f"⏱️ Response time: {response_time_ms}ms")
                            
                            if response.status_code == 200:
                                response_data = response.json()
                                print(f"✅ Claude Success! Response: {response_data}")
                                
                                # Extract text from Claude response
                                if 'content' in response_data and len(response_data['content']) > 0:
                                    text = response_data['content'][0]['text']
                                    
                                    # Get token usage from Claude response
                                    usage = response_data.get('usage', {})
                                    input_tokens = usage.get('input_tokens', 0)
                                    output_tokens = usage.get('output_tokens', 0)
                                    token_count = input_tokens + output_tokens
                                    
                                    # Calculate cost estimate for Claude
                                    if 'claude-3-opus' in model_name.lower():
                                        cost_estimate = (input_tokens / 1000) * 0.015 + (output_tokens / 1000) * 0.075
                                    elif 'claude-3-sonnet' in model_name.lower():
                                        cost_estimate = (input_tokens / 1000) * 0.003 + (output_tokens / 1000) * 0.015
                                    else:  # claude-3-haiku or other
                                        cost_estimate = (input_tokens / 1000) * 0.00025 + (output_tokens / 1000) * 0.00125
                                    
                                    # Create successful response
                                    LLMResponse.objects.create(
                                        comparison=comparison,
                                        provider=provider,
                                        model_name=model_name,
                                        response_text=text,
                                        response_time_ms=response_time_ms,
                                        token_count=token_count,
                                        cost_estimate=cost_estimate
                                    )
                                    
                                    successful_responses += 1
                                    print(f"✅ Successfully created response for {provider.name}")
                                    
                                    # Update usage count
                                    api_config.usage_count_today += 1
                                    api_config.save()
                                else:
                                    error_msg = "Invalid response format from Claude API"
                                    LLMResponse.objects.create(
                                        comparison=comparison,
                                        provider=provider,
                                        model_name=model_name,
                                        response_text="",
                                        response_time_ms=response_time_ms,
                                        error_message=f"Claude API error: {error_msg}"
                                    )
                                    errors.append(f"{provider.name}: {error_msg}")
                                    
                            else:
                                print(f"❌ Claude API error - Status: {response.status_code}")
                                print(f"❌ Response content: {response.content}")
                                
                                try:
                                    error_data = response.json() if response.content else {}
                                    error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                                except:
                                    error_msg = f"HTTP {response.status_code} - {response.text[:200]}"
                                
                                LLMResponse.objects.create(
                                    comparison=comparison,
                                    provider=provider,
                                    model_name=model_name,
                                    response_text="",
                                    response_time_ms=response_time_ms,
                                    error_message=f"Claude API error: {error_msg}"
                                )
                                
                                errors.append(f"{provider.name}: {error_msg}")
                        
                        else:
                            # For other providers, create placeholder for now
                            LLMResponse.objects.create(
                                comparison=comparison,
                                provider=provider,
                                model_name=model_name,
                                response_text="",
                                response_time_ms=0,
                                error_message=f"{provider.provider_type} integration not yet implemented"
                            )
                            errors.append(f"{provider.name} ({model_name}): Integration not yet implemented")
                            
                    except Exception as provider_error:
                        print(f"❌ Provider {provider.name} error: {provider_error}")
                        LLMResponse.objects.create(
                            comparison=comparison,
                            provider=provider,
                            model_name=model_name,
                            response_text="",
                            response_time_ms=0,
                            error_message=str(provider_error)
                        )
                        errors.append(f"{provider.name} ({model_name}): {str(provider_error)}")
                
                # Get the updated comparison with responses
                comparison = LLMComparison.objects.prefetch_related('responses__provider').get(id=comparison.id)
                response_serializer = LLMComparisonSerializer(comparison)
                
                return Response({
                    'success': True,
                    'comparison': response_serializer.data,
                    'summary': {
                        'total_providers': len(provider_configs),
                        'successful_responses': successful_responses,
                        'errors': errors
                    }
                }, status=status.HTTP_201_CREATED)
                
            except Exception as api_error:
                print(f"❌ LLM API Error: {api_error}")
                # Fall back to mock responses if real API fails
                comparison = LLMComparison.objects.create(
                    user=request.user,
                    prompt=serializer.validated_data['prompt'],
                    title=serializer.validated_data.get('title', '')
                )
                
                # Create fallback responses with error info
                for config in provider_configs:
                    provider_id = config['provider_id']
                    model_name = config['model_name']
                    provider = LLMProvider.objects.get(id=provider_id)
                    LLMResponse.objects.create(
                        comparison=comparison,
                        provider=provider,
                        model_name=model_name,
                        response_text='',
                        response_time_ms=0,
                        token_count=0,
                        cost_estimate=0,
                        error_message=f"API call failed: {str(api_error)}"
                    )
                
                # Refresh the comparison to include the responses
                comparison.refresh_from_db()
                comparison = LLMComparison.objects.prefetch_related('responses__provider').get(id=comparison.id)
                
                response_serializer = LLMComparisonSerializer(comparison)
                
                return Response({
                    'success': True,
                    'comparison': response_serializer.data,
                    'summary': {
                        'total_providers': len(provider_configs),
                        'successful_responses': 0,
                        'errors': [f"API integration error: {str(api_error)}"]
                    }
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            import traceback
            return Response({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def responses(self, request, pk=None):
        """Get detailed responses for a specific comparison"""
        comparison = self.get_object()
        responses = comparison.responses.all()
        serializer = LLMResponseSerializer(responses, many=True)
        return Response(serializer.data)
