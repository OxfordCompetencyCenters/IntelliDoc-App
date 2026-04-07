# backend/project_api_keys/validators.py

import asyncio
import aiohttp
import logging
from typing import Tuple
import time

logger = logging.getLogger(__name__)

class APIKeyValidator:
    """Validates API keys with their respective providers"""
    
    def __init__(self):
        self.timeout = 10  # seconds
        logger.info("🔍 API KEY VALIDATOR: Initialized")
    
    def validate_key(self, provider_type: str, api_key: str) -> Tuple[bool, str]:
        """Validate an API key synchronously"""
        try:
            # Run async validation in sync context
            return asyncio.run(self._validate_key_async(provider_type, api_key))
        except Exception as e:
            logger.error(f"❌ Validation error for {provider_type}: {e}")
            return False, f"Validation failed: {str(e)}"
    
    async def _validate_key_async(self, provider_type: str, api_key: str) -> Tuple[bool, str]:
        """Async validation implementation"""
        logger.info(f"🔍 Validating {provider_type} API key")
        
        try:
            if provider_type == 'openai':
                return await self._validate_openai_key(api_key)
            elif provider_type == 'google':
                return await self._validate_google_key(api_key)
            elif provider_type == 'anthropic':
                return await self._validate_anthropic_key(api_key)
            else:
                return False, f"Unsupported provider: {provider_type}"
                
        except Exception as e:
            logger.error(f"❌ Async validation error for {provider_type}: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def _validate_openai_key(self, api_key: str) -> Tuple[bool, str]:
        """Validate OpenAI API key"""
        try:
            # Basic format validation
            if not api_key.startswith(('sk-', 'sk-proj-')):
                return False, "Invalid OpenAI API key format (should start with 'sk-' or 'sk-proj-')"
            
            if len(api_key) < 40:
                return False, "OpenAI API key appears too short"
            
            # Test API call to OpenAI
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'gpt-3.5-turbo',
                'messages': [{'role': 'user', 'content': 'Test'}],
                'max_tokens': 1
            }
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status == 200:
                        logger.info("✅ OpenAI API key validation successful")
                        return True, "Valid OpenAI API key"
                    elif response.status == 401:
                        return False, "Invalid OpenAI API key or insufficient permissions"
                    elif response.status == 429:
                        # Rate limited, but key is probably valid
                        logger.warning("⚠️ OpenAI API rate limited during validation")
                        return True, "Valid OpenAI API key (rate limited during test)"
                    else:
                        error_text = await response.text()
                        logger.warning(f"⚠️ OpenAI API validation returned status {response.status}: {error_text}")
                        return False, f"API validation failed (status: {response.status})"
            
        except asyncio.TimeoutError:
            logger.warning("⚠️ OpenAI API validation timeout")
            return False, "Validation timeout - please check your internet connection"
        except Exception as e:
            logger.error(f"❌ OpenAI validation error: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def _validate_google_key(self, api_key: str) -> Tuple[bool, str]:
        """Validate Google/Gemini API key"""
        try:
            # Basic format validation
            if not api_key.startswith('AIza'):
                return False, "Invalid Google API key format (should start with 'AIza')"
            
            if len(api_key) < 35:
                return False, "Google API key appears too short"
            
            # Test API call to Gemini (using gemini-2.5-flash to match PDF extractor)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}',
                    headers={'Content-Type': 'application/json'},
                    json={
                        'contents': [{
                            'parts': [{'text': 'Test'}]
                        }],
                        'generationConfig': {
                            'maxOutputTokens': 1
                        }
                    }
                ) as response:
                    
                    if response.status == 200:
                        logger.info("✅ Google API key validation successful")
                        return True, "Valid Google API key"
                    elif response.status == 400:
                        error_data = await response.json()
                        if 'API_KEY_INVALID' in str(error_data):
                            return False, "Invalid Google API key"
                        else:
                            # Might be valid key with other issues
                            return True, "Valid Google API key (minor API issue during test)"
                    elif response.status == 403:
                        return False, "Google API key lacks required permissions for Gemini"
                    elif response.status == 429:
                        # Rate limited, but key is probably valid
                        logger.warning("⚠️ Google API rate limited during validation")
                        return True, "Valid Google API key (rate limited during test)"
                    else:
                        error_text = await response.text()
                        logger.warning(f"⚠️ Google API validation returned status {response.status}: {error_text}")
                        return False, f"API validation failed (status: {response.status})"
            
        except asyncio.TimeoutError:
            logger.warning("⚠️ Google API validation timeout")
            return False, "Validation timeout - please check your internet connection"
        except Exception as e:
            logger.error(f"❌ Google validation error: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def _validate_anthropic_key(self, api_key: str) -> Tuple[bool, str]:
        """Validate Anthropic/Claude API key"""
        try:
            # Basic format validation
            if not api_key.startswith('sk-ant-'):
                return False, "Invalid Anthropic API key format (should start with 'sk-ant-')"
            
            if len(api_key) < 40:
                return False, "Anthropic API key appears too short"
            
            # Test API call to Anthropic
            headers = {
                'x-api-key': api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            payload = {
                'model': 'claude-3-haiku-20240307',
                'max_tokens': 1,
                'messages': [{'role': 'user', 'content': 'Test'}]
            }
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status == 200:
                        logger.info("✅ Anthropic API key validation successful")
                        return True, "Valid Anthropic API key"
                    elif response.status == 401:
                        return False, "Invalid Anthropic API key or insufficient permissions"
                    elif response.status == 429:
                        # Rate limited, but key is probably valid
                        logger.warning("⚠️ Anthropic API rate limited during validation")
                        return True, "Valid Anthropic API key (rate limited during test)"
                    else:
                        error_text = await response.text()
                        logger.warning(f"⚠️ Anthropic API validation returned status {response.status}: {error_text}")
                        return False, f"API validation failed (status: {response.status})"
            
        except asyncio.TimeoutError:
            logger.warning("⚠️ Anthropic API validation timeout")
            return False, "Validation timeout - please check your internet connection"
        except Exception as e:
            logger.error(f"❌ Anthropic validation error: {e}")
            return False, f"Validation error: {str(e)}"
