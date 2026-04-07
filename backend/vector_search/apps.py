# backend/vector_search/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class VectorSearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vector_search'
    verbose_name = 'Vector Search'

    def ready(self):
        """Vector search components load lazily on first use (faster startup)."""
        if hasattr(VectorSearchConfig, '_initialized'):
            return
        VectorSearchConfig._initialized = True
        logger.info("🎆 AICC IntelliDoc Vector Search App Ready (lazy loading enabled)")
