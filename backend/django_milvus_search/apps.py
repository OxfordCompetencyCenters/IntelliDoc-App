"""
Django app configuration for Milvus Search
"""
from django.apps import AppConfig


class MilvusSearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_milvus_search'
    verbose_name = 'Milvus Search'
    
    def ready(self):
        """Initialize the app when Django starts"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Milvus Search app initialized")
