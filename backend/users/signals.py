# users/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import DocumentVectorStatus, ProjectVectorCollection, VectorProcessingStatus
import logging
from django.utils import timezone
from django.db.models import Count

logger = logging.getLogger(__name__)

@receiver(post_save, sender=DocumentVectorStatus)
def update_collection_status_on_document_change(sender, instance, created, **kwargs):
    """
    Signal handler to automatically update collection status when document statuses change
    This ensures the overall collection status always reflects the actual state of documents
    """
    try:
        # Get the collection from the document status
        collection = instance.collection
        
        # Log that the signal was triggered
        logger.info(f"Signal triggered: Document status changed for {instance.document.original_filename} to {instance.status}")
        
        # Count document statuses
        doc_statuses = DocumentVectorStatus.objects.filter(collection=collection)
        total_docs = doc_statuses.count()
        completed_docs = doc_statuses.filter(status=VectorProcessingStatus.COMPLETED).count()
        failed_docs = doc_statuses.filter(status=VectorProcessingStatus.FAILED).count()
        processing_docs = doc_statuses.filter(status=VectorProcessingStatus.PROCESSING).count()
        pending_docs = doc_statuses.filter(status=VectorProcessingStatus.PENDING).count()
        
        # Log counts for debugging
        logger.info(f"Status counts: total={total_docs}, completed={completed_docs}, failed={failed_docs}, processing={processing_docs}, pending={pending_docs}")
        
        # Verify against project document count
        actual_doc_count = collection.project.documents.count()
        logger.info(f"Project document count: {actual_doc_count}")
        
        # Determine the correct status based on document statuses
        if total_docs == 0 or actual_doc_count == 0:
            # No documents to process
            collection_status = VectorProcessingStatus.PENDING
            logger.info(f"Setting collection status to PENDING (no documents)")
        elif completed_docs == actual_doc_count and completed_docs > 0:
            # All documents completed successfully
            collection_status = VectorProcessingStatus.COMPLETED
            logger.info(f"Setting collection status to COMPLETED (all documents processed)")
        elif failed_docs > 0 and (completed_docs + failed_docs) == actual_doc_count:
            # All documents processed, but some failed
            collection_status = VectorProcessingStatus.FAILED
            logger.info(f"Setting collection status to FAILED (some documents failed)")
        else:
            # Some documents still processing
            collection_status = VectorProcessingStatus.PROCESSING
            logger.info(f"Setting collection status to PROCESSING (processing in progress)")
        
        # Update the collection status if it's different
        if collection.status != collection_status:
            logger.info(f"Updating collection status from {collection.status} to {collection_status}")
            collection.status = collection_status
            collection.processed_documents = completed_docs
            collection.failed_documents = failed_docs
            collection.total_documents = actual_doc_count
            collection.last_processed_at = timezone.now()
            collection.save()
            
            # Verify the update was saved
            collection.refresh_from_db()
            logger.info(f"Collection status updated to {collection.status}")
        else:
            logger.info(f"Collection status already {collection_status}, no update needed")
    
    except Exception as e:
        logger.error(f"Error in signal handler: {e}")
        logger.exception(e)
