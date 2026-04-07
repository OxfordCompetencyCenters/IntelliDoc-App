from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .claude_provider import ClaudeProvider
from .ollama_provider import OllamaProvider

PROVIDER_REGISTRY = {
    'openai': OpenAIProvider,
    'gemini': GeminiProvider,
    'claude': ClaudeProvider,
    'ollama': OllamaProvider,
}

def get_provider_class(provider_type: str):
    """Factory function to get provider class by type"""
    return PROVIDER_REGISTRY.get(provider_type.lower())
