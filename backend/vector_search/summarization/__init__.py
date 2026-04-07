# Enhanced Summarization Service with Fallback Support
# backend/vector_search/summarization/__init__.py

import logging
from typing import Optional
from .openai_summarizer import OpenAISummarizer

logger = logging.getLogger(__name__)

# Global summarizer instance
_summarizer_instance = None

def get_summarizer() -> OpenAISummarizer:
    """Get or create the global summarizer instance"""
    global _summarizer_instance
    
    if _summarizer_instance is None:
        _summarizer_instance = OpenAISummarizer()
        logger.info("Initialized OpenAI summarizer instance")
    
    return _summarizer_instance

def initialize_summarizer() -> bool:
    """Initialize the summarizer and return success status"""
    try:
        summarizer = get_summarizer()
        return summarizer.is_available()
    except Exception as e:
        logger.error(f"Failed to initialize summarizer: {e}")
        return False

# Export for easy importing
__all__ = ['get_summarizer', 'initialize_summarizer', 'OpenAISummarizer']
