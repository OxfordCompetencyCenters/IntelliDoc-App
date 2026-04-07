"""
Django signals for automatic ChromaDB cleanup
Ensures ChromaDB stays in sync when documents are deleted from Django admin
"""
import logging
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from .models import PublicKnowledgeDocument
from .services import PublicKnowledgeService

logger = logging.getLogger('public_chatbot')


@receiver(pre_delete, sender=PublicKnowledgeDocument)
def delete_from_chromadb_before_django_delete(sender, instance, **kwargs):
    """
    Delete document from ChromaDB before deleting from Django
    Using pre_delete to ensure we still have access to document_id
    """
    try:
        # Only attempt deletion if document was actually synced to ChromaDB
        if instance.synced_to_chromadb and instance.chromadb_id:
            logger.info(f"🗑️ SIGNAL: Auto-deleting document {instance.document_id} from ChromaDB")
            
            # Get ChromaDB service instance
            knowledge_service = PublicKnowledgeService.get_instance()
            
            if knowledge_service.is_ready:
                # Delete from ChromaDB using document_id
                success = knowledge_service.delete_knowledge(instance.document_id)
                
                if success:
                    logger.info(f"✅ SIGNAL: Successfully deleted document {instance.document_id} from ChromaDB")
                else:
                    logger.error(f"❌ SIGNAL: Failed to delete document {instance.document_id} from ChromaDB")
            else:
                logger.warning(f"⚠️ SIGNAL: ChromaDB service not ready, skipping deletion for {instance.document_id}")
        else:
            logger.info(f"ℹ️ SIGNAL: Document {instance.document_id} was not synced to ChromaDB, no deletion needed")
            
    except Exception as e:
        logger.error(f"❌ SIGNAL: Error during ChromaDB deletion for {instance.document_id}: {e}")
        # Don't re-raise the exception to avoid blocking Django deletion


@receiver(post_delete, sender=PublicKnowledgeDocument)
def log_successful_deletion(sender, instance, **kwargs):
    """
    Log successful completion of document deletion
    """
    logger.info(f"🎯 SIGNAL: Document {instance.document_id} successfully deleted from Django database")