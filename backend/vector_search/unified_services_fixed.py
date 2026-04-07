# Enhanced-Only Vector Search Service - Full AI Processing
# backend/vector_search/unified_services_fixed.py

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db import transaction
from asgiref.sync import async_to_sync

from users.models import (
    IntelliDocProject, ProjectDocument, ProjectVectorCollection,
    VectorProcessingStatus, DocumentVectorStatus,
)
from .embeddings import get_embedder_instance

logger = logging.getLogger(__name__)

def fix_existing_documents(project_id: str = None) -> Dict[str, Any]:
    """Fix existing documents by re-processing them with batch insertion"""
    try:
        logger.info(f"🔧 Starting document fixing for project {project_id or 'all projects'}")
        
        if project_id:
            projects = [IntelliDocProject.objects.get(project_id=project_id)]
        else:
            projects = IntelliDocProject.objects.all()
        
        total_fixed = 0
        total_failed = 0
        
        for project in projects:
            result = UnifiedVectorSearchManager.process_project_documents(str(project.project_id), 'enhanced')
            if result['status'] == 'completed':
                total_fixed += result['processed_documents']
                total_failed += result['failed_documents']
        
        return {
            'status': 'completed',
            'message': f'Fixed {total_fixed} documents across {len(projects)} projects',
            'fixed_documents': total_fixed,
            'failed_documents': total_failed
        }
        
    except Exception as e:
        logger.error(f"❌ Document fixing failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'fixed_documents': 0,
            'failed_documents': 0
        }

class UnifiedVectorSearchManager:
    """Enhanced-only vector search service with full AI processing capabilities"""
    
    def __init__(self):
        pass  # No longer need ContentExtractor since EnhancedHierarchicalProcessor handles everything
    
    @staticmethod
    def process_project_documents(
        project_id: str, 
        processing_mode: str = 'enhanced',
        llm_provider: str = None,
        llm_model: str = None,
        enable_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Enhanced document processing with full AI capabilities - NO fallbacks
        
        Args:
            project_id: Project identifier
            processing_mode: Only 'enhanced' mode supported
            llm_provider: LLM provider to use (e.g., 'openai', 'anthropic', 'google')
            llm_model: LLM model to use (e.g., 'gpt-3.5-turbo', 'claude-3-opus')
            enable_summary: Whether to generate summaries for chunks
        """
        try:
            # Get project using UUID only
            project = IntelliDocProject.objects.get(project_id=project_id)
            
            logger.info(f"🚀 Starting ENHANCED processing for project {project.name}")
            if llm_provider:
                logger.info(f"📋 LLM Config - Provider: {llm_provider}, Model: {llm_model}, Enable Summary: {enable_summary}")
            
            # Initialize components
            manager = UnifiedVectorSearchManager()
            embedder = get_embedder_instance()
            
            # Only enhanced processing - no fallbacks
            return manager._process_enhanced_with_full_ai(
                project, 
                embedder,
                llm_provider=llm_provider,
                llm_model=llm_model,
                enable_summary=enable_summary
            )
                
        except Exception as e:
            logger.error(f"❌ Enhanced processing failed for project {project_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'processed_documents': 0,
                'failed_documents': 0,
                'total_chunks_created': 0,
                'processing_mode': 'enhanced'
            }
    
    def _process_enhanced_with_full_ai(
        self, 
        project: IntelliDocProject, 
        embedder,
        llm_provider: str = None,
        llm_model: str = None,
        enable_summary: bool = True
    ) -> Dict[str, Any]:
        """Enhanced processing with full AI capabilities using project-specific API keys"""
        from .enhanced_hierarchical_processor import EnhancedHierarchicalProcessor
        from .enhanced_hierarchical_database import EnhancedHierarchicalVectorDatabase

        start_time = time.time()

        # Initialize processor with project and LLM configuration
        try:
            processor = EnhancedHierarchicalProcessor(
                project=project, 
                embedder=embedder,
                llm_provider=llm_provider,
                llm_model=llm_model,
                enable_summary=enable_summary
            )
        except ValueError as e:
            # Project doesn't have required API key configured
            logger.error(f"❌ Cannot process documents: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'processed_documents': 0,
                'failed_documents': 0,
                'total_chunks_created': 0,
                'processing_mode': 'enhanced',
                'error_type': 'missing_api_key'
            }

        database = EnhancedHierarchicalVectorDatabase(str(project.project_id))
        
        # Get documents - check all possible statuses and log what we find
        all_documents = project.documents.all()
        ready_documents = project.documents.filter(upload_status='ready')
        
        logger.info(f"📊 Document status check for project {project.name}:")
        logger.info(f"  • Total documents: {all_documents.count()}")
        logger.info(f"  • Ready documents: {ready_documents.count()}")
        
        # Log the upload status of each document
        for doc in all_documents:
            logger.info(f"  • {doc.original_filename}: status={doc.upload_status}")
        
        # No files uploaded at all
        if not ready_documents.exists():
            logger.warning(f"No ready documents found for project {project.name}")
            return {
                'status': 'completed',
                'message': 'No documents to process',
                'processed_documents': 0,
                'failed_documents': 0,
                'total_chunks_created': 0,
                'processing_mode': 'enhanced',
                'debug_info': {
                    'total_documents': all_documents.count(),
                    'ready_documents': ready_documents.count(),
                    'project_id': str(project.project_id),
                    'project_name': project.name
                }
            }

        # "Preserve Original Folder Structure" now means: use LLM-based folder organization
        # based on ProjectDocumentSummary.short_summary.
        folder_org_enabled = True  # Always use LLM-based folder classification
        llm_folder_org_enabled = bool(folder_org_enabled and llm_provider and llm_model)
        doc_summaries_will_generate = bool((enable_summary or folder_org_enabled) and llm_provider and llm_model)

        # Generate per-document summaries.
        # For local models (Ollama): process sequentially to avoid overwhelming the model.
        # For cloud providers: process in parallel (I/O-bound).
        # upsert_document_summary is idempotent — skips docs that already have summaries.
        summaries_generated = 0
        is_local_provider = llm_provider in ('ollama',)
        if doc_summaries_will_generate:
            try:
                from .document_summarization.file_based_document_summarizer import upsert_document_summary

                all_ready_list = list(ready_documents)
                mode = "sequentially (local model)" if is_local_provider else "in parallel"
                logger.info(f"📝 Generating summaries for {len(all_ready_list)} ready documents {mode}")

                if is_local_provider:
                    # Sequential: one at a time for local models
                    async def _generate_all_summaries():
                        results = []
                        for doc in all_ready_list:
                            try:
                                r = await upsert_document_summary(
                                    project=project, document=doc,
                                    llm_provider=llm_provider, llm_model=llm_model,
                                )
                                results.append(r)
                                logger.info(f"  ✅ Summary generated for {doc.original_filename}")
                            except Exception as e:
                                results.append(e)
                                logger.error(f"  ❌ Summary failed for {doc.original_filename}: {e}")
                        return results
                else:
                    # Parallel: cloud providers handle concurrent requests well
                    async def _generate_all_summaries():
                        tasks = [
                            upsert_document_summary(
                                project=project, document=doc,
                                llm_provider=llm_provider, llm_model=llm_model,
                            )
                            for doc in all_ready_list
                        ]
                        return await asyncio.gather(*tasks, return_exceptions=True)

                results = async_to_sync(_generate_all_summaries)()
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        doc_name = getattr(all_ready_list[i], "original_filename", "unknown")
                        logger.error("❌ Failed generating document summary for %s: %s", doc_name, result)
                    else:
                        summaries_generated += 1
                logger.info(f"✅ Summary generation complete: {summaries_generated}/{len(all_ready_list)} succeeded")
            except Exception as e:
                logger.error("❌ Failed generating document summaries batch: %s", e)

        # Incremental: skip docs already successfully embedded in Milvus
        already_completed_doc_ids = DocumentVectorStatus.objects.filter(
            document__in=ready_documents,
            status=VectorProcessingStatus.COMPLETED,
        ).values_list('document_id', flat=True)

        documents = ready_documents.exclude(id__in=already_completed_doc_ids)

        skipped_count = len(already_completed_doc_ids)
        logger.info(
            f"  • Skipping {skipped_count} already-COMPLETED documents; "
            f"{documents.count()} to process"
        )

        if not documents.exists():
            logger.info(f"All documents already processed for project {project.name}")
            return {
                'status': 'all_already_processed',
                'message': f'All documents are already processed. {summaries_generated} summaries checked/generated.',
                'processed_documents': 0,
                'failed_documents': 0,
                'skipped_documents': skipped_count,
                'summaries_generated': summaries_generated,
                'total_chunks_created': 0,
                'processing_mode': 'enhanced',
            }

        logger.info(f"🚀 Starting enhanced processing for {documents.count()} documents in project {project.name}")
        documents_list = list(documents)

        folder_organization_map: Dict[str, str] = {}
        if llm_folder_org_enabled:
            try:
                from .document_summarization.document_folder_organizer import (
                    generate_and_persist_document_folder_organization,
                )

                folder_organization_map = generate_and_persist_document_folder_organization(
                    project=project,
                    documents=documents_list,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
            except Exception as e:
                logger.error("❌ Failed generating LLM folder organization: %s", e)
        
        processed_count = 0
        failed_count = 0
        total_chunks_created = 0
        processing_details = []

        # Process documents using the enhanced hierarchical processor
        processor.folder_organization_map = folder_organization_map or {}
        doc_infos = processor.process_project_documents_enhanced(documents_list)
        
        for doc_info in doc_infos:
            try:
                # Find the original document object
                original_doc = None
                for doc in documents:
                    if str(doc.document_id) == doc_info.document_metadata['document_id']:
                        original_doc = doc
                        break

                if not original_doc:
                    logger.error(f"❌ Could not find original document for {doc_info.document_metadata.get('file_name')}")
                    failed_count += 1
                    continue

                # 📦 COLLECT-AND-BATCH-STORE PATTERN with Enhanced Database
                logger.info(f"📦 Collecting {len(doc_info.chunks)} enhanced chunks for batch insertion: {doc_info.document_metadata.get('file_name')}")
                
                # Mark document as processing
                self._update_document_status(
                    str(project.project_id),
                    str(original_doc.document_id),
                    'processing',
                    f'Enhanced batch inserting {len(doc_info.chunks)} chunks',
                    enable_summary=doc_summaries_will_generate,
                )
                
                # 🚀 ATOMIC BATCH INSERTION FOR ENTIRE DOCUMENT using Enhanced Database
                logger.info(f"🚀 Starting enhanced atomic batch insertion for {doc_info.document_metadata.get('file_name')} - {len(doc_info.chunks)} chunks")
                
                try:
                    # Use enhanced database insertion
                    success = database.insert_hierarchical_document(doc_info)
                    
                    if success:
                        # 🎯 ENHANCED ATOMICITY SUCCESS
                        self._update_document_status(
                            str(project.project_id),
                            str(original_doc.document_id), 
                            'completed', 
                            f'Enhanced processing: {len(doc_info.chunks)} chunks (chunk summaries removed); doc summaries generated={bool(doc_summaries_will_generate)}',
                            enable_summary=doc_summaries_will_generate,
                        )
                        
                        processed_count += 1
                        total_chunks_created += len(doc_info.chunks)
                        processing_details.append({
                            'file_name': doc_info.document_metadata.get('file_name'),
                            'chunks_created': len(doc_info.chunks),
                            'document_summaries_generated': bool(doc_summaries_will_generate),
                            'hierarchical_analysis': True,
                            'enhanced_processing': True,
                            'enhanced_database': True,
                            'batch_insertion': True,
                            'atomic_operation': True
                        })
                        
                        logger.info(f"✅ ENHANCED SUCCESS: {doc_info.document_metadata.get('file_name')} - {len(doc_info.chunks)} chunks with full AI integration")
                    else:
                        # 💥 ENHANCED ATOMICITY FAILURE
                        self._update_document_status(
                            str(project.project_id),
                            str(original_doc.document_id), 
                            'failed', 
                            f'Enhanced batch insertion failed for {len(doc_info.chunks)} chunks',
                            enable_summary=doc_summaries_will_generate,
                        )
                        failed_count += 1
                        logger.error(f"💥 ENHANCED FAILURE: {doc_info.document_metadata.get('file_name')} - Enhanced batch insertion failed")
                        
                except Exception as batch_error:
                    # 🚨 ENHANCED EXCEPTION DURING BATCH
                    self._update_document_status(
                        str(project.project_id),
                        str(original_doc.document_id), 
                        'failed', 
                        f'Enhanced batch insertion exception: {str(batch_error)[:200]}',
                        enable_summary=doc_summaries_will_generate,
                    )
                    failed_count += 1
                    logger.exception(f"🚨 ENHANCED BATCH EXCEPTION: {doc_info.document_metadata.get('file_name')}: {batch_error}")

            except Exception as e:
                logger.exception(f"❌ Failed to process document {doc_info.document_metadata.get('file_name', 'N/A')}: {e}")
                failed_count += 1
                # Mark document as failed due to processing error
                if 'original_doc' in locals() and original_doc:
                    self._update_document_status(
                        str(project.project_id),
                        str(original_doc.document_id),
                        'failed',
                        f'Enhanced processing error: {str(e)[:200]}',
                        enable_summary=doc_summaries_will_generate,
                    )

        # Update collection status
        collection = self._update_collection_status(project, processed_count, failed_count, 'enhanced')
        
        total_processing_time = int((time.time() - start_time) * 1000)

        return {
            'status': 'completed',
            'message': f'Enhanced processing completed with full AI: {processed_count} documents processed',
            'processed_documents': processed_count,
            'failed_documents': failed_count,
            'total_chunks_created': total_chunks_created,
            'processing_details': processing_details,
            'processing_mode': 'enhanced',
            'total_processing_time_ms': total_processing_time,
            'features_enabled': {
                'ai_summaries': bool(doc_summaries_will_generate),
                'ai_topics': False,
                'hierarchical_analysis': True,
                'enhanced_categorization': True,
                'complete_metadata': True,
                'timing_tracking': True
            },
            'collection_name': collection.collection_name if collection else 'default'
        }
    
    def _update_document_status(self, project_id: str, document_id: str, status: str, message: str, enable_summary: bool = True):
        """Update individual document processing status for frontend tracking using DocumentVectorStatus
        
        SECURITY: Requires project_id to ensure document belongs to the correct project.
        This prevents potential cross-project document access.
        """
        try:
            from users.models import ProjectDocument, DocumentVectorStatus, ProjectVectorCollection, VectorProcessingStatus
            
            # SECURITY FIX: Find document by UUID AND project_id to ensure project isolation
            document = ProjectDocument.objects.get(document_id=document_id, project__project_id=project_id)
            
            # Get or create vector collection for the project
            collection, created = ProjectVectorCollection.objects.get_or_create(
                project=document.project,
                defaults={
                    'collection_name': document.project.generate_collection_name(),
                    'status': VectorProcessingStatus.PROCESSING
                }
            )
            
            # Get or create document vector status
            doc_vector_status, created = DocumentVectorStatus.objects.get_or_create(
                document=document,
                collection=collection,
                defaults={
                    'status': VectorProcessingStatus.PENDING,
                    'content_length': len(document.extraction_text or ''),
                    'embedding_dimension': 384
                }
            )
            
            # Map status to VectorProcessingStatus
            vector_status_map = {
                'processing': VectorProcessingStatus.PROCESSING,
                'completed': VectorProcessingStatus.COMPLETED,
                'failed': VectorProcessingStatus.FAILED
            }
            
            # Update vector status
            if status in vector_status_map:
                doc_vector_status.status = vector_status_map[status]
                doc_vector_status.error_message = message if status == 'failed' else ''
                
                if status == 'completed':
                    doc_vector_status.processed_at = timezone.now()
                    # Document-level summaries (no per-chunk summaries/topics anymore)
                    doc_vector_status.summary_generated = bool(enable_summary)
                    doc_vector_status.summary_generated_at = timezone.now() if enable_summary else None
                    doc_vector_status.summary_chunks_count = 1 if enable_summary else 0
                    doc_vector_status.summarizer_used = 'file_api_llm' if enable_summary else 'none'

                    # Topics are fully removed.
                    doc_vector_status.topic_generated = False
                    doc_vector_status.topic_generated_at = None
                    doc_vector_status.topic_chunks_count = 0
                    doc_vector_status.topic_generator_used = 'none'
                
                doc_vector_status.updated_at = timezone.now()
                doc_vector_status.save()
                
                logger.info(f"📊 Document vector status updated: {document.original_filename} -> {status}")
            
        except Exception as e:
            logger.error(f"❌ Failed to update document status for {document_id}: {e}")
            logger.exception(e)
    
    def _update_collection_status(self, project: IntelliDocProject, processed: int, failed: int, mode: str) -> Optional[Any]:
        """Update collection status with consistency checks"""
        try:
            # Get or create the collection
            collection, created = ProjectVectorCollection.objects.get_or_create(
                project=project,
                defaults={
                    'collection_name': project.generate_collection_name(),
                    'status': VectorProcessingStatus.COMPLETED,
                    'total_documents': processed + failed,
                    'processed_documents': processed,
                    'failed_documents': failed,
                    'last_processed_at': timezone.now()
                }
            )
            
            # Log the status before update
            logger.info(f"Collection status before update: {collection.status}")
            
            # If it already exists, update it
            if not created:
                # Get the actual document statuses for verification
                from users.models import DocumentVectorStatus
                doc_statuses = DocumentVectorStatus.objects.filter(collection=collection)
                completed_docs = doc_statuses.filter(status=VectorProcessingStatus.COMPLETED).count()
                failed_docs = doc_statuses.filter(status=VectorProcessingStatus.FAILED).count()
                
                # Determine the actual status based on document statuses
                actual_doc_count = project.documents.count()
                logger.info(f"Status verification: completed={completed_docs}, failed={failed_docs}, total={actual_doc_count}")
                
                # Only set as COMPLETED if all documents are processed and non-zero
                if actual_doc_count == 0:
                    # No documents to process
                    status_to_set = VectorProcessingStatus.PENDING
                    logger.info(f"Setting status to PENDING (no documents in project)")
                elif completed_docs > 0 and completed_docs == actual_doc_count:
                    # All documents completed successfully
                    status_to_set = VectorProcessingStatus.COMPLETED
                    logger.info(f"✅ Setting status to COMPLETED: all {completed_docs}/{actual_doc_count} documents processed successfully")
                elif failed_docs > 0 and (completed_docs + failed_docs) == actual_doc_count:
                    # All documents processed, but some failed
                    status_to_set = VectorProcessingStatus.FAILED
                    logger.info(f"❌ Setting status to FAILED: {failed_docs} documents failed, {completed_docs} completed")
                elif completed_docs > 0 or failed_docs > 0:
                    # Some documents still processing or pending
                    status_to_set = VectorProcessingStatus.PROCESSING
                    logger.info(f"🔄 Setting status to PROCESSING: {completed_docs} completed, {failed_docs} failed, {actual_doc_count - completed_docs - failed_docs} pending")
                else:
                    # If no document statuses yet, use provided counts
                    if processed > 0 and failed == 0:
                        status_to_set = VectorProcessingStatus.COMPLETED
                        logger.info(f"✅ Setting status to COMPLETED based on provided counts: {processed} processed, {failed} failed")
                    else:
                        status_to_set = VectorProcessingStatus.PROCESSING
                        logger.info(f"🔄 Setting status to PROCESSING based on provided counts: {processed} processed, {failed} failed")
                
                # Update the collection with verified status
                collection.total_documents = actual_doc_count
                collection.processed_documents = completed_docs
                collection.failed_documents = failed_docs
                collection.last_processed_at = timezone.now()
                collection.status = status_to_set
                collection.save()
                
                # Verify the save was successful
                collection.refresh_from_db()
                logger.info(f"✅ Collection status updated and verified: {collection.status} (processed={completed_docs}, failed={failed_docs}, total={actual_doc_count})")
            
            # Verify the update was saved correctly
            collection.refresh_from_db()
            logger.info(f"Verified collection status after update: {collection.status}")
            
            return collection
            
        except Exception as e:
            logger.error(f"❌ Error updating collection status: {e}")
            logger.exception(e)
            return None
    
    @staticmethod
    def search_project_documents(project_id: str, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search documents in a project using enhanced hierarchical search"""
        try:
            from .enhanced_hierarchical_services import EnhancedHierarchicalSearchAPI
            search_api = EnhancedHierarchicalSearchAPI()
            
            results = search_api.search_documents(
                project_id=project_id,
                query=query,
                limit=limit,
                search_level='chunk',
                group_by_document=True
            )
            
            return {
                'status': 'success',
                'results': results,
                'total_results': len(results),
                'search_mode': 'enhanced_hierarchical'
            }
            
        except Exception as e:
            logger.error(f"❌ Enhanced search failed for project {project_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'results': [],
                'total_results': 0,
                'search_mode': 'fallback'
            }

# Management command integration - Enhanced only
def fix_existing_documents_cmd(project_id: str = None) -> Dict[str, Any]:
    """Fix existing documents using enhanced processing only"""
    try:
        from .enhanced_hierarchical_processor import EnhancedHierarchicalProcessor
        from .embeddings import get_embedder_instance
        
        # Get projects to fix
        if project_id:
            projects = IntelliDocProject.objects.filter(project_id=project_id)
        else:
            projects = IntelliDocProject.objects.all()
            
        if not projects.exists():
            return {
                'status': 'error',
                'message': f'No projects found with ID: {project_id}' if project_id else 'No projects found',
                'fixed_count': 0,
                'failed_count': 0
            }
        
        fixed_count = 0
        failed_count = 0
        
        for project in projects:
            try:
                result = UnifiedVectorSearchManager.process_project_documents(str(project.project_id), 'enhanced')
                if result['status'] == 'completed':
                    fixed_count += result['processed_documents']
                    failed_count += result['failed_documents']
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Failed to fix project {project.name}: {e}")
                failed_count += 1
        
        return {
            'status': 'completed',
            'message': f'Fixed documents across {projects.count()} projects',
            'fixed_count': fixed_count,
            'failed_count': failed_count,
            'projects_processed': projects.count()
        }
        
    except Exception as e:
        logger.error(f"❌ Document fixing command failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
            'fixed_count': 0,
            'failed_count': 0
        }
