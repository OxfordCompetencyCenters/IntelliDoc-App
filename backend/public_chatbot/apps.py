from django.apps import AppConfig


class PublicChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'public_chatbot'
    verbose_name = 'Public Chatbot API'
    
    def ready(self):
        """Initialize ChromaDB service and signals on app startup"""
        try:
            # Import signals to register them
            from . import signals
            
            # Initialize singleton service
            from .services import PublicKnowledgeService
            PublicKnowledgeService.get_instance()
        except Exception as e:
            import logging
            logger = logging.getLogger('public_chatbot')
            logger.warning(f"ChromaDB service initialization deferred: {e}")