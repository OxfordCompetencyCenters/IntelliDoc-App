# backend/vector_search/services_enhanced.py
from typing import Dict, Any, List, Optional
import logging
from django.conf import settings
from .embeddings import DocumentEmbedder
from .enhanced_hierarchical_processor import EnhancedHierarchicalProcessor
from .enhanced_hierarchical_database import EnhancedHierarchicalVectorDatabase
import threading
import time

logger = logging.getLogger(__name__)

# Global processing control
PROCESSING_CONTROL = {}
PROCESSING_THREADS = {}

class EnhancedProjectVectorSearchService:
    """Enhanced service for managing vector search operations with stop capability"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        # Load project object (required for processor initialization)
        from users.models import IntelliDocProject
        try:
            self.project = IntelliDocProject.objects.get(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            logger.error(f"❌ Project {project_id} not found")
            raise ValueError(f"Project {project_id} not found")
        
        # Use singleton embedder instead of creating new instances
        from .embeddings import get_embedder_instance
        self.embedder = get_embedder_instance()
        
        # Pass project as first argument, embedder as keyword argument
        self.processor = EnhancedHierarchicalProcessor(self.project, embedder=self.embedder)
        self.vector_db = EnhancedHierarchicalVectorDatabase(project_id)
        self.stop_processing = False
        self.processing_thread = None
        self.current_document_id = None
        
        # Initialize processing control for this project
        if project_id not in PROCESSING_CONTROL:
            PROCESSING_CONTROL[project_id] = {
                'stop_requested': False,
                'current_document_id': None,
                'status': 'IDLE'
            }
    
    def process_and_vectorize_documents(self) -> Dict[str, Any]:
        """Process only new/unprocessed documents in a project with stop capability"""
        from users.models import DocumentVectorStatus, ProjectVectorCollection, VectorProcessingStatus, ProjectDocument
        from django.utils import timezone
        
        try:
            # Reset stop flag
            self.stop_processing = False
            self.current_document_id = None
            
            # Store processing state globally
            PROCESSING_CONTROL[self.project_id] = {
                'stop_requested': False,
                'current_document_id': None,
                'status': 'PROCESSING'
            }
            
            logger.info(f"Starting document processing and vectorization for project {self.project_id}")
            
            # Get or create project vector collection
            from users.models import IntelliDocProject
            project = IntelliDocProject.objects.get(project_id=self.project_id)
            
            collection, created = ProjectVectorCollection.objects.get_or_create(
                project=project,
                defaults={
                    'collection_name': project.generate_collection_name(),
                    'status': VectorProcessingStatus.PROCESSING
                }
            )
            
            # Update collection status to processing
            collection.status = VectorProcessingStatus.PROCESSING
            collection.save()
            
            processed_count = 0
            failed_count = 0
            skipped_count = 0
            stopped_count = 0
            results = []
            
            # Process each document in the project using enhanced hierarchical processor
            documents = project.documents.filter(upload_status='ready')
            if getattr(project, 'preserve_original_folder_structure', False):
                try:
                    from users.models import ProjectDocumentFolderOrganization

                    folder_org_map = {
                        str(doc_id): folder_path
                        for doc_id, folder_path in ProjectDocumentFolderOrganization.objects.filter(
                            document__in=documents
                        ).values_list('document__document_id', 'folder_path')
                    }
                    self.processor.folder_organization_map = folder_org_map
                except Exception as e:
                    logger.debug(f"Could not load LLM folder organization mapping: {e}")

            for doc_info in self.processor.process_project_documents_enhanced(list(documents)):
                # Check if stop was requested
                if self._should_stop_processing():
                    logger.info(f"Processing stopped for project {self.project_id}")
                    stopped_count += 1
                    break
                
                document_id = doc_info.document_metadata['document_id']
                file_name = doc_info.document_metadata['file_name']
                
                # Update current document being processed
                self.current_document_id = document_id
                PROCESSING_CONTROL[self.project_id]['current_document_id'] = document_id
                
                try:
                    # SECURITY FIX: Get the document with project filter to ensure project isolation
                    document = ProjectDocument.objects.get(document_id=document_id, project=self.project)
                    
                    # Get or create document vector status
                    doc_vector_status, created = DocumentVectorStatus.objects.get_or_create(
                    document=document,
                    collection=collection,
                    defaults={
                    'status': VectorProcessingStatus.PROCESSING,
                    'content_length': doc_info.document_metadata['original_content_length']
                    }
                    )
                    
                    # Update status to processing
                    doc_vector_status.status = VectorProcessingStatus.PROCESSING
                    doc_vector_status.content_length = doc_info.document_metadata['original_content_length']
                    doc_vector_status.save()
                    
                    # Check again before processing
                    if self._should_stop_processing():
                        logger.info(f"Processing stopped during document {file_name}")
                        # Clean up this document's partial processing
                        self._cleanup_partial_document(document_id)
                        doc_vector_status.status = VectorProcessingStatus.PENDING
                        doc_vector_status.save()
                        stopped_count += 1
                        break
                    
                    # Record processing start time
                    start_time = timezone.now()
                    
                    # Insert into enhanced hierarchical vector database
                    success = self.vector_db.insert_hierarchical_document(doc_info)
                    
                    # Check if stopped during insertion
                    if self._should_stop_processing():
                        logger.info(f"Processing stopped during insertion for document {file_name}")
                        # Clean up this document's partial processing
                        self._cleanup_partial_document(document_id)
                        doc_vector_status.status = VectorProcessingStatus.PENDING
                        doc_vector_status.save()
                        stopped_count += 1
                        break
                    
                    # Calculate processing time
                    processing_time = (timezone.now() - start_time).total_seconds() * 1000  # in milliseconds
                    
                    if success:
                        # Update document status to completed
                        doc_vector_status.status = VectorProcessingStatus.COMPLETED
                        doc_vector_status.processed_at = timezone.now()
                        doc_vector_status.processing_time_ms = int(processing_time)
                        doc_vector_status.error_message = ''
                        doc_vector_status.save()
                        
                        processed_count += 1
                        results.append({
                        "document_id": document_id,
                        "file_name": file_name,
                        "content_length": doc_info.document_metadata['original_content_length'],
                        "processing_time_ms": int(processing_time),
                        "status": "success"
                        })
                        logger.info(f"Successfully processed: {file_name}")
                    else:
                        # Update document status to failed
                        doc_vector_status.status = VectorProcessingStatus.FAILED
                        doc_vector_status.error_message = 'Database insertion failed'
                        doc_vector_status.processing_time_ms = int(processing_time)
                        doc_vector_status.save()
                        
                        failed_count += 1
                        results.append({
                            "document_id": document_id,
                            "file_name": file_name,
                            "status": "failed",
                            "error": "Database insertion failed"
                        })
                        
                except Exception as e:
                    failed_count += 1
                    error_msg = str(e)
                    logger.error(f"Failed to process document {file_name}: {error_msg}")
                    
                    # Update document status to failed if we can
                    try:
                        # SECURITY FIX: Get the document with project filter to ensure project isolation
                        document = ProjectDocument.objects.get(document_id=document_id, project=self.project)
                        doc_vector_status, created = DocumentVectorStatus.objects.get_or_create(
                            document=document,
                            collection=collection,
                            defaults={'status': VectorProcessingStatus.FAILED}
                        )
                        doc_vector_status.status = VectorProcessingStatus.FAILED
                        doc_vector_status.error_message = error_msg
                        doc_vector_status.save()
                    except:
                        pass
                    
                    results.append({
                        "document_id": document_id,
                        "file_name": file_name,
                        "status": "failed",
                        "error": error_msg
                    })
                
                # Clear current document
                self.current_document_id = None
                PROCESSING_CONTROL[self.project_id]['current_document_id'] = None
            
            # Update collection statistics
            collection.total_documents = collection.document_statuses.count()
            collection.processed_documents = collection.document_statuses.filter(
                status=VectorProcessingStatus.COMPLETED
            ).count()
            collection.failed_documents = collection.document_statuses.filter(
                status=VectorProcessingStatus.FAILED
            ).count()
            collection.last_processed_at = timezone.now()
            
            # Update collection status based on results
            was_stopped = self._should_stop_processing()
            
            if was_stopped:
                collection.status = VectorProcessingStatus.PENDING
                collection.error_message = f"Processing stopped by user. {stopped_count} documents interrupted."
            elif collection.failed_documents > 0 and collection.processed_documents == 0:
                collection.status = VectorProcessingStatus.FAILED
                collection.error_message = f"All {collection.failed_documents} documents failed to process"
            elif collection.failed_documents > 0:
                collection.status = VectorProcessingStatus.COMPLETED
                collection.error_message = f"{collection.failed_documents} documents failed to process"
            else:
                collection.status = VectorProcessingStatus.COMPLETED
                collection.error_message = ''
            
            collection.save()
            
            # Get final stats
            collection_stats = self.vector_db.get_collection_stats()
            
            # Calculate skipped documents
            total_docs = ProjectDocument.objects.filter(project=project).count()
            skipped_count = total_docs - (processed_count + failed_count + stopped_count)
            
            # Clean up processing control
            PROCESSING_CONTROL[self.project_id]['status'] = 'COMPLETED' if not was_stopped else 'STOPPED'
            
            summary = {
                "project_id": self.project_id,
                "processed_documents": processed_count,
                "failed_documents": failed_count,
                "skipped_documents": skipped_count,
                "stopped_documents": stopped_count,
                "total_documents_in_project": total_docs,
                "total_in_collection": collection_stats.get("total_documents", 0),
                "was_stopped": was_stopped,
                "results": results,
                "status": "stopped" if was_stopped else "completed"
            }
            
            logger.info(f"Processing completed for project {self.project_id}: "
                       f"{processed_count} processed, {failed_count} failed, {skipped_count} skipped, "
                       f"{stopped_count} stopped")
            
            return summary
            
        except Exception as e:
            error_msg = f"Document processing failed for project {self.project_id}: {e}"
            logger.error(error_msg)
            
            # Update collection status to failed if possible
            try:
                from users.models import IntelliDocProject
                project = IntelliDocProject.objects.get(project_id=self.project_id)
                collection = ProjectVectorCollection.objects.get(project=project)
                collection.status = VectorProcessingStatus.FAILED
                collection.error_message = error_msg
                collection.save()
            except:
                pass
            
            # Clean up processing control
            if self.project_id in PROCESSING_CONTROL:
                PROCESSING_CONTROL[self.project_id]['status'] = 'FAILED'
            
            return {
                "project_id": self.project_id,
                "processed_documents": 0,
                "failed_documents": 0,
                "skipped_documents": 0,
                "stopped_documents": 0,
                "was_stopped": False,
                "status": "error",
                "error": error_msg
            }
    
    def _should_stop_processing(self) -> bool:
        """Check if processing should be stopped"""
        return (self.stop_processing or 
                PROCESSING_CONTROL.get(self.project_id, {}).get('stop_requested', False))
    
    def _cleanup_partial_document(self, document_id: str) -> None:
        """Clean up partial processing for a document"""
        try:
            # Delete from vector database
            success = self.vector_db.delete_document(document_id)
            if success:
                logger.info(f"Cleaned up partial processing for document {document_id}")
            else:
                logger.warning(f"Failed to clean up partial processing for document {document_id}")
        except Exception as e:
            logger.error(f"Error cleaning up partial processing for document {document_id}: {e}")
    
    def stop_processing(self) -> bool:
        """Stop the current processing operation"""
        try:
            logger.info(f"Stop requested for project {self.project_id}")
            
            # Set stop flags
            self.stop_processing = True
            if self.project_id in PROCESSING_CONTROL:
                PROCESSING_CONTROL[self.project_id]['stop_requested'] = True
            
            # Clean up current document if any
            if self.current_document_id:
                self._cleanup_partial_document(self.current_document_id)
            
            # Update all PROCESSING documents to PENDING
            from users.models import ProjectVectorCollection, DocumentVectorStatus, VectorProcessingStatus
            from users.models import IntelliDocProject
            
            project = IntelliDocProject.objects.get(project_id=self.project_id)
            try:
                collection = ProjectVectorCollection.objects.get(project=project)
                
                # Reset processing documents to pending
                processing_docs = DocumentVectorStatus.objects.filter(
                    collection=collection,
                    status=VectorProcessingStatus.PROCESSING
                )
                
                for doc_status in processing_docs:
                    # Clean up vector database entry
                    self._cleanup_partial_document(str(doc_status.document.document_id))
                    # Reset status
                    doc_status.status = VectorProcessingStatus.PENDING
                    doc_status.processed_at = None
                    doc_status.error_message = 'Processing stopped by user'
                    doc_status.save()
                
                # Update collection status
                collection.status = VectorProcessingStatus.PENDING
                collection.error_message = 'Processing stopped by user'
                collection.save()
                
                logger.info(f"Successfully stopped processing for project {self.project_id}")
                return True
                
            except ProjectVectorCollection.DoesNotExist:
                logger.warning(f"No collection found for project {self.project_id}")
                return True
            
        except Exception as e:
            logger.error(f"Error stopping processing for project {self.project_id}: {e}")
            return False
    
    def get_document_statuses(self) -> List[Dict[str, Any]]:
        """Get individual document processing statuses"""
        from users.models import ProjectDocument, DocumentVectorStatus, VectorProcessingStatus
        from users.models import IntelliDocProject, ProjectVectorCollection
        
        try:
            project = IntelliDocProject.objects.get(project_id=self.project_id)
            documents = ProjectDocument.objects.filter(project=project)
            
            document_statuses = []
            
            # Get collection if exists
            try:
                collection = ProjectVectorCollection.objects.get(project=project)
            except ProjectVectorCollection.DoesNotExist:
                collection = None
            
            for doc in documents:
                try:
                    if collection:
                        doc_status = DocumentVectorStatus.objects.get(
                            document=doc,
                            collection=collection
                        )
                        status = doc_status.status
                        processed_at = doc_status.processed_at.isoformat() if doc_status.processed_at else None
                        processing_time = doc_status.processing_time_ms
                        error_message = doc_status.error_message
                    else:
                        status = VectorProcessingStatus.PENDING
                        processed_at = None
                        processing_time = None
                        error_message = ''
                    
                    document_statuses.append({
                        "document_id": str(doc.document_id),
                        "file_name": doc.original_filename,
                        "file_size": doc.file_size,
                        "uploaded_at": doc.uploaded_at.isoformat(),
                        "status": status,
                        "processed_at": processed_at,
                        "processing_time_ms": processing_time,
                        "error_message": error_message
                    })
                    
                except DocumentVectorStatus.DoesNotExist:
                    document_statuses.append({
                        "document_id": str(doc.document_id),
                        "file_name": doc.original_filename,
                        "file_size": doc.file_size,
                        "uploaded_at": doc.uploaded_at.isoformat(),
                        "status": VectorProcessingStatus.PENDING,
                        "processed_at": None,
                        "processing_time_ms": None,
                        "error_message": ''
                    })
            
            return document_statuses
            
        except Exception as e:
            logger.error(f"Error getting document statuses for project {self.project_id}: {e}")
            return []
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get detailed processing status for the project"""
        from users.models import ProjectVectorCollection, DocumentVectorStatus, VectorProcessingStatus, ProjectDocument
        
        try:
            # Get project
            from users.models import IntelliDocProject
            project = IntelliDocProject.objects.get(project_id=self.project_id)
            logger.debug(f"📊 STATUS: Getting processing status for project {self.project_id} ({project.name})")
            
            # Get total documents in project
            total_documents = ProjectDocument.objects.filter(project=project).count()
            logger.debug(f"📊 STATUS: Total documents in project: {total_documents}")
            
            # Get current processing control status
            control_status = PROCESSING_CONTROL.get(self.project_id, {})
            logger.debug(f"📊 STATUS: Processing control status: {control_status}")
            
            try:
                # Get collection
                collection = ProjectVectorCollection.objects.get(project=project)
                logger.debug(f"📊 STATUS: Found collection {collection.collection_name} with status: {collection.status}")
                
                # Get document statuses
                document_statuses = DocumentVectorStatus.objects.filter(collection=collection)
                current_project_doc_ids = list(
                    ProjectDocument.objects.filter(project=project).values_list('id', flat=True)
                )
                current_doc_statuses = document_statuses.filter(document_id__in=current_project_doc_ids)
                
                # Count by status
                status_counts = {
                    'pending': current_doc_statuses.filter(status=VectorProcessingStatus.PENDING).count(),
                    'processing': current_doc_statuses.filter(status=VectorProcessingStatus.PROCESSING).count(),
                    'completed': current_doc_statuses.filter(status=VectorProcessingStatus.COMPLETED).count(),
                    'failed': current_doc_statuses.filter(status=VectorProcessingStatus.FAILED).count()
                }
                
                # Count unprocessed documents (not in DocumentVectorStatus)
                processed_doc_ids = current_doc_statuses.values_list('document_id', flat=True)
                unprocessed_count = ProjectDocument.objects.filter(
                    project=project
                ).exclude(id__in=processed_doc_ids).count()

                # Derive effective status from current corpus state, not stale collection status.
                has_all_status_rows = (unprocessed_count == 0 and total_documents > 0)
                all_terminal = has_all_status_rows and (status_counts['completed'] + status_counts['failed'] == total_documents)
                control_is_processing = control_status.get('status') == 'PROCESSING'

                # Thread-liveness cross-check: don't trust PROCESSING_CONTROL if thread is dead
                thread_alive = (
                    self.project_id in PROCESSING_THREADS
                    and PROCESSING_THREADS[self.project_id].is_alive()
                )
                if control_is_processing and not thread_alive:
                    logger.warning(
                        "Auto-healed stale PROCESSING_CONTROL for project %s",
                        self.project_id,
                    )
                    PROCESSING_CONTROL.setdefault(self.project_id, {})['status'] = 'STALE'
                    control_is_processing = False

                if (control_is_processing and thread_alive) or status_counts['processing'] > 0:
                    normalized_status = 'processing'
                elif total_documents == 0:
                    normalized_status = 'not_created'
                elif has_all_status_rows and status_counts['completed'] == total_documents:
                    normalized_status = 'completed'
                elif all_terminal and status_counts['failed'] > 0:
                    normalized_status = 'failed'
                else:
                    # New uploads/deletes or not-yet-processed corpus should not appear as completed.
                    normalized_status = 'pending'

                raw_status = collection.status
                logger.debug(
                    "📊 STATUS: Effective status '%s' (raw collection status='%s', totals=%s, completed=%s, failed=%s, unprocessed=%s)",
                    normalized_status,
                    raw_status,
                    total_documents,
                    status_counts['completed'],
                    status_counts['failed'],
                    unprocessed_count,
                )
                
                return {
                    'project_id': self.project_id,
                    'collection_status': normalized_status,  # Return normalized lowercase status
                    'collection_name': collection.collection_name,
                    'total_documents': total_documents,
                    'unprocessed_documents': unprocessed_count,
                    'document_statuses': status_counts,
                    'last_processed_at': collection.last_processed_at.isoformat() if collection.last_processed_at else None,
                    'error_message': collection.error_message,
                    'is_processing': normalized_status == 'processing',
                    'current_document_id': control_status.get('current_document_id'),
                    'stop_requested': control_status.get('stop_requested', False),
                    'processing_progress': {
                        'completed': status_counts['completed'],
                        'total': total_documents,
                        'percentage': (status_counts['completed'] / total_documents * 100) if total_documents > 0 else 0
                    }
                }
                
            except ProjectVectorCollection.DoesNotExist:
                logger.info(f"📊 STATUS: No collection found for project {self.project_id}, returning NOT_CREATED")
                return {
                    'project_id': self.project_id,
                    'collection_status': 'not_created',  # Normalize to lowercase
                    'collection_name': None,
                    'total_documents': total_documents,
                    'unprocessed_documents': total_documents,
                    'document_statuses': {
                        'pending': 0,
                        'processing': 0,
                        'completed': 0,
                        'failed': 0
                    },
                    'last_processed_at': None,
                    'error_message': '',
                    'is_processing': control_status.get('status') == 'PROCESSING',
                    'current_document_id': control_status.get('current_document_id'),
                    'stop_requested': control_status.get('stop_requested', False),
                    'processing_progress': {
                        'completed': 0,
                        'total': total_documents,
                        'percentage': 0
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ STATUS: Failed to get processing status for project {self.project_id}: {e}")
            logger.exception(e)  # Log full exception traceback
            return {
                'project_id': self.project_id,
                'collection_status': 'error',  # Return error status instead of missing field
                'error': str(e),
                'processing_progress': {'completed': 0, 'total': 0, 'percentage': 0},
                'is_processing': False
            }

class EnhancedVectorSearchManager:
    """Enhanced manager class for vector search operations with stop capability"""
    
    @staticmethod
    def get_project_service(project_id: str) -> EnhancedProjectVectorSearchService:
        """Get an enhanced vector search service for a specific project"""
        return EnhancedProjectVectorSearchService(project_id)
    
    @staticmethod
    def process_project_documents(project_id: str) -> Dict[str, Any]:
        """Process and vectorize only new/unprocessed documents for a project"""
        service = EnhancedVectorSearchManager.get_project_service(project_id)
        return service.process_and_vectorize_documents()
    
    @staticmethod
    def stop_project_processing(project_id: str) -> Dict[str, Any]:
        """Stop processing for a specific project"""
        service = EnhancedVectorSearchManager.get_project_service(project_id)
        success = service.stop_processing()
        return {
            'project_id': project_id,
            'success': success,
            'message': 'Processing stopped successfully' if success else 'Failed to stop processing'
        }
    
    @staticmethod
    def get_project_processing_status(project_id: str) -> Dict[str, Any]:
        """Get detailed processing status for a project (heavy -- creates processor + Milvus)"""
        service = EnhancedVectorSearchManager.get_project_service(project_id)
        return service.get_processing_status()

    @staticmethod
    def get_processing_status_lightweight(project_id: str) -> Dict[str, Any]:
        """ORM-only status query -- no processor, no Milvus, no embedder.

        Designed for the polling endpoint so every 3-second poll doesn't spin
        up a full EnhancedHierarchicalProcessor + Milvus connection.
        """
        from users.models import (
            IntelliDocProject, ProjectVectorCollection,
            DocumentVectorStatus, VectorProcessingStatus, ProjectDocument,
        )

        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            return {
                'project_id': project_id,
                'collection_status': 'error',
                'error': f'Project {project_id} not found',
                'processing_progress': {'completed': 0, 'total': 0, 'percentage': 0},
                'is_processing': False,
            }

        total_documents = ProjectDocument.objects.filter(project=project).count()
        control_status = PROCESSING_CONTROL.get(project_id, {})

        # --- Thread-liveness cross-check (auto-heal stale PROCESSING_CONTROL) ---
        control_is_processing = control_status.get('status') == 'PROCESSING'
        thread_alive = (
            project_id in PROCESSING_THREADS
            and PROCESSING_THREADS[project_id].is_alive()
        )
        if control_is_processing and not thread_alive:
            logger.warning(
                "Auto-healed stale PROCESSING_CONTROL for project %s "
                "(control said PROCESSING but no thread is alive)",
                project_id,
            )
            PROCESSING_CONTROL.setdefault(project_id, {})['status'] = 'STALE'
            control_is_processing = False

        try:
            collection = ProjectVectorCollection.objects.get(project=project)

            current_project_doc_ids = list(
                ProjectDocument.objects.filter(project=project).values_list('id', flat=True)
            )
            current_doc_statuses = DocumentVectorStatus.objects.filter(
                collection=collection, document_id__in=current_project_doc_ids,
            )

            status_counts = {
                'pending': current_doc_statuses.filter(status=VectorProcessingStatus.PENDING).count(),
                'processing': current_doc_statuses.filter(status=VectorProcessingStatus.PROCESSING).count(),
                'completed': current_doc_statuses.filter(status=VectorProcessingStatus.COMPLETED).count(),
                'failed': current_doc_statuses.filter(status=VectorProcessingStatus.FAILED).count(),
            }

            processed_doc_ids = current_doc_statuses.values_list('document_id', flat=True)
            unprocessed_count = ProjectDocument.objects.filter(
                project=project
            ).exclude(id__in=processed_doc_ids).count()

            has_all_status_rows = (unprocessed_count == 0 and total_documents > 0)
            all_terminal = has_all_status_rows and (
                status_counts['completed'] + status_counts['failed'] == total_documents
            )

            if (control_is_processing and thread_alive) or status_counts['processing'] > 0:
                normalized_status = 'processing'
            elif total_documents == 0:
                normalized_status = 'not_created'
            elif has_all_status_rows and status_counts['completed'] == total_documents:
                normalized_status = 'completed'
            elif all_terminal and status_counts['failed'] > 0:
                normalized_status = 'failed'
            else:
                normalized_status = 'pending'

            logger.debug(
                "LIGHTWEIGHT STATUS: project=%s effective='%s' (thread_alive=%s, completed=%s, "
                "failed=%s, unprocessed=%s, total=%s)",
                project_id, normalized_status, thread_alive,
                status_counts['completed'], status_counts['failed'],
                unprocessed_count, total_documents,
            )

            return {
                'project_id': project_id,
                'collection_status': normalized_status,
                'collection_name': collection.collection_name,
                'total_documents': total_documents,
                'unprocessed_documents': unprocessed_count,
                'document_statuses': status_counts,
                'last_processed_at': (
                    collection.last_processed_at.isoformat()
                    if collection.last_processed_at else None
                ),
                'error_message': collection.error_message,
                'is_processing': normalized_status == 'processing',
                'current_document_id': control_status.get('current_document_id'),
                'stop_requested': control_status.get('stop_requested', False),
                'processing_progress': {
                    'completed': status_counts['completed'],
                    'total': total_documents,
                    'percentage': (
                        (status_counts['completed'] / total_documents * 100)
                        if total_documents > 0 else 0
                    ),
                },
            }

        except ProjectVectorCollection.DoesNotExist:
            return {
                'project_id': project_id,
                'collection_status': 'processing' if thread_alive else 'not_created',
                'collection_name': None,
                'total_documents': total_documents,
                'unprocessed_documents': total_documents,
                'document_statuses': {
                    'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0,
                },
                'last_processed_at': None,
                'error_message': '',
                'is_processing': thread_alive,
                'current_document_id': control_status.get('current_document_id'),
                'stop_requested': control_status.get('stop_requested', False),
                'processing_progress': {
                    'completed': 0,
                    'total': total_documents,
                    'percentage': 0,
                },
            }

    @staticmethod
    def get_document_statuses(project_id: str) -> List[Dict[str, Any]]:
        """Get individual document processing statuses"""
        service = EnhancedVectorSearchManager.get_project_service(project_id)
        return service.get_document_statuses()
