# backend/vector_search/startup.py
"""
Startup initialization for vector search components
Ensures singleton embedder and Gemini extractor are created once during application startup
"""

import logging
import os
from django.conf import settings
from .embeddings import get_embedder_instance
from .modern_gemini_extractor import initialize_gemini_extractor

logger = logging.getLogger(__name__)

def initialize_vector_search():
    """Initialize vector search components at startup"""
    try:
        logger.info("🚀 Initializing AICC IntelliDoc Vector Search components...")
        
        # Create singleton embedder instance
        embedder = get_embedder_instance()
        
        # Initialize Gemini PDF extractor if API key is available
        try:
            gemini_api_key = os.getenv('GOOGLE_API_KEY')
            if gemini_api_key:
                gemini_extractor = initialize_gemini_extractor(gemini_api_key)
                if gemini_extractor and gemini_extractor.gemini_available:
                    logger.info("🤖 Gemini API initialized successfully for PDF extraction")
                else:
                    logger.warning("⚠️ Google API key provided but initialization failed")
            else:
                logger.warning("⚠️ No GOOGLE_API_KEY found in environment - PDF extraction will use PyPDF2 only")
        except Exception as e:
            logger.error(f"❌ Gemini API initialization failed: {e}")
            logger.warning("🔄 PDF extraction will fall back to PyPDF2")
        
        logger.info(f"✅ Vector Search initialization complete!")
        logger.info(f"📊 Embedder dimension: {embedder.vector_dim}")
        
        if embedder.model is None:
            logger.warning("⚠️  Using fallback random embeddings - Consider downloading the model")
            logger.info("💡 Run: python backend/download_model.py to download the embedding model")
        else:
            logger.info("🎯 Ready for high-quality document processing!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Vector Search initialization failed: {e}")
        logger.warning("🔄 Will use fallback mode during processing")
        return False

def check_system_health():
    """Check system health for vector search components"""
    try:
        embedder = get_embedder_instance()
        
        health_status = {
            "embedder_available": embedder is not None,
            "model_loaded": embedder.model is not None if embedder else False,
            "vector_dimension": embedder.vector_dim if embedder else 0,
            "status": "healthy" if (embedder and embedder.model) else "degraded"
        }
        
        return health_status
        
    except Exception as e:
        return {
            "embedder_available": False,
            "model_loaded": False,
            "vector_dimension": 0,
            "status": "error",
            "error": str(e)
        }
