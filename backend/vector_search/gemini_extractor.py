#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upgraded Gemini API PDF Text Extractor
Now uses Modern Gemini 2.5 Flash API with fallback to 1.5 Flash
"""

# Import the modern implementation
from .modern_gemini_extractor import (
    ModernGeminiPDFExtractor,
    initialize_gemini_extractor,
    get_gemini_extractor
)

# Backward compatibility alias
GeminiPDFExtractor = ModernGeminiPDFExtractor

# Re-export functions for backward compatibility
__all__ = [
    'GeminiPDFExtractor',
    'ModernGeminiPDFExtractor', 
    'initialize_gemini_extractor',
    'get_gemini_extractor'
]
