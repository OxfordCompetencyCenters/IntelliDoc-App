import requests
import os
from typing import List, Dict, Any
from .encryption import decrypt_api_key

class ModelService:
    """Service to fetch available models from different LLM providers"""
    
    @staticmethod
    def get_openai_models(api_key: str) -> List[Dict[str, Any]]:
        """
        Fetch available OpenAI models.

        Behaviour notes:
        - We call the OpenAI `/v1/models` endpoint directly and **do not** silently
          fall back to a hard‑coded subset of models.
        - This ensures the frontend can see the **full list of GPT models** that
          your account is allowed to use (e.g. `gpt-4.1`, `gpt-4o-mini`, future GPT‑5
          variants), instead of always being limited to a small default set.
        - If the API call fails (network issue, invalid key, permissions), we now
          return an empty list so upstream callers can surface a clear error and
          treat the key as invalid rather than pretending a partial list is “ok”.
        """
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            response = requests.get('https://api.openai.com/v1/models', headers=headers, timeout=10)
            response.raise_for_status()
            models = response.json()['data']
            
            # Filter to GPT chat/completion models - INCLUSIVE filter for all GPT models
            # Includes: gpt-3.5-*, gpt-4-*, gpt-4o-*, gpt-5-*, and any future GPT models
            chat_models = []
            for model in models:
                model_id = model['id'].lower()
                
                # Include all GPT models (gpt-3, gpt-3.5, gpt-4, gpt-4o, gpt-5, etc.)
                # Exclude: embeddings, audio, image, fine-tune base models, and deprecated models
                is_gpt_model = model_id.startswith('gpt-')
                
                # Exclude non-chat models (embeddings, audio, image generation, etc.)
                excluded_patterns = [
                    'embedding', 'audio', 'whisper', 'tts', 'dall-e', 'davinci', 
                    'curie', 'babbage', 'ada', 'instruct', 'deprecated'
                ]
                is_excluded = any(excluded in model_id for excluded in excluded_patterns)
                
                # Include all GPT models except excluded ones
                if is_gpt_model and not is_excluded:
                    chat_models.append({
                        'id': model['id'],
                        'name': model['id'],
                        'displayName': model['id'].replace('-', ' ').title(),
                        'object': model.get('object', 'model')
                    })
            
            return sorted(chat_models, key=lambda x: x['id'])
        except Exception as e:
            # IMPORTANT: do not hide failures behind a tiny hard‑coded list.
            # Returning [] allows DynamicModelsService.test_api_key(...) to
            # accurately detect that something is wrong with this API key or
            # network environment, so the UI can show a clear warning instead
            # of only exposing four fallback models.
            print(f"Error fetching OpenAI models: {e}")
            return []
    
    @staticmethod
    def get_claude_models(api_key: str) -> List[Dict[str, Any]]:
        """
        Fetch available Claude models from Anthropic API.
        
        Uses: GET https://api.anthropic.com/v1/models
        Headers: anthropic-version: 2023-06-01, X-Api-Key: {api_key}
        
        Returns empty list on error (no hardcoded fallback).
        This ensures the frontend can see the full list of Claude models
        that the account is allowed to use, instead of being limited to a
        hardcoded subset.
        """
        try:
            headers = {
                'anthropic-version': '2023-06-01',
                'X-Api-Key': api_key,
                'Content-Type': 'application/json'
            }
            response = requests.get(
                'https://api.anthropic.com/v1/models',
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Format models consistently
            models = []
            for model in data.get('data', []):
                model_id = model.get('id', '')
                if model_id:
                    models.append({
                        'id': model_id,
                        'name': model_id,
                        'displayName': model_id.replace('-', ' ').title()
                    })
            
            return sorted(models, key=lambda x: x['id'])
        except Exception as e:
            # IMPORTANT: do not hide failures behind a hardcoded list.
            # Returning [] allows DynamicModelsService.test_api_key(...) to
            # accurately detect that something is wrong with this API key or
            # network environment, so the UI can show a clear warning instead
            # of only exposing a partial list.
            print(f"Error fetching Claude models: {e}")
            return []
    
    @staticmethod
    def get_gemini_models(api_key: str) -> List[Dict[str, Any]]:
        """Fetch available Google Gemini models."""
        try:
            print(f"🔍 Fetching Gemini models with API key: {api_key[:10]}...")
            url = f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}'
            
            response = requests.get(url, timeout=10)
            print(f"📡 Gemini API response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Gemini API error response: {response.text}")
                response.raise_for_status()
            
            data = response.json()
            models = data.get('models', [])
            print(f"📋 Raw models count: {len(models)}")
            
            # Filter to generation models only and format consistently
            generation_models = []
            for model in models:
                if 'generateContent' in model.get('supportedGenerationMethods', []):
                    model_name = model['name'].replace('models/', '')  # Remove 'models/' prefix
                    generation_models.append({
                        'id': model_name,
                        'name': model_name,
                        'displayName': model.get('displayName', model_name),
                    })
                    print(f"✅ Added model: {model_name}")
            
            print(f"🎉 Found {len(generation_models)} generation models")
            return generation_models
            
        except Exception as e:
            # IMPORTANT: do not hide failures behind a hardcoded list.
            # Returning [] allows DynamicModelsService.test_api_key(...) to
            # accurately detect that something is wrong with this API key or
            # network environment, so the UI can show a clear warning instead
            # of only exposing a partial list.
            print(f"Error fetching Gemini models: {e}")
            return []
    
    @staticmethod
    def get_models_for_provider(provider_type: str, api_key: str = None) -> List[Dict[str, Any]]:
        """Get available models for a specific provider"""
        if provider_type == 'openai' and api_key:
            return ModelService.get_openai_models(api_key)
        elif provider_type == 'claude' and api_key:
            return ModelService.get_claude_models(api_key)
        elif provider_type == 'gemini' and api_key:
            return ModelService.get_gemini_models(api_key)
        else:
            return []
