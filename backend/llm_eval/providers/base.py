from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncGenerator
import asyncio
import aiohttp
import time
from dataclasses import dataclass

@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    response_time_ms: int
    token_count: Optional[int] = None
    cost_estimate: Optional[float] = None
    error: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None

class LLMProvider(ABC):
    """Abstract base class for all LLM providers"""
    
    def __init__(self, api_key: str, model: str, max_tokens: int = 1000, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.provider_name = self.__class__.__name__.replace('Provider', '').lower()
    
    @abstractmethod
    async def generate_response(
        self, 
        prompt: Optional[str] = None, 
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response from the LLM provider.
        
        Args:
            prompt: Optional prompt string (for backward compatibility)
            messages: Optional structured messages array [{"role": "...", "content": "..."}]
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse object
            
        Note: Either prompt or messages should be provided, not both.
        If messages is provided, it takes precedence over prompt.
        """
        pass
    
    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests"""
        pass
    
    @abstractmethod
    def format_request_body(
        self, 
        prompt: Optional[str] = None, 
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Format the request body for the provider's API.
        
        Args:
            prompt: Optional prompt string (for backward compatibility)
            messages: Optional structured messages array
            **kwargs: Additional parameters
            
        Returns:
            Formatted request body dict
            
        Note: Either prompt or messages should be provided.
        If messages is provided, it takes precedence over prompt.
        """
        pass
    
    @abstractmethod
    def parse_response(self, response_data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        """Parse the API response and return (text, token_count)"""
        pass
    
    def estimate_cost(self, token_count: Optional[int]) -> Optional[float]:
        """Estimate cost based on token count - override in subclasses"""
        return None
    
    async def generate_response_stream(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response from the LLM provider.
        
        Args:
            prompt: Optional prompt string (for backward compatibility)
            messages: Optional structured messages array
            **kwargs: Additional provider-specific parameters
            
        Yields:
            Text chunks as they are generated
            
        Note: Default implementation falls back to non-streaming.
        Override in subclasses for native streaming support.
        """
        # Default implementation: fall back to non-streaming
        response = await self.generate_response(prompt=prompt, messages=messages, **kwargs)
        if response.error:
            yield f"Error: {response.error}"
        else:
            # Yield the full response as a single chunk
            yield response.text