"""
DocAware Handler
===============

Handles DocAware integration and context management for conversation orchestration.
"""

import logging
import time
import json
from typing import Dict, List, Any, Optional, Union
from asgiref.sync import sync_to_async

# Import DocAware services
from .docaware import EnhancedDocAwareAgentService, SearchMethod

# Import models for doc-aware context and full document mode
from users.models import ProjectDocument, IntelliDocProject, ProjectDocumentSummary

logger = logging.getLogger('conversation_orchestrator')


class FileAttachmentPreparationError(Exception):
    """
    Raised when File Attachments cannot be prepared for execution
    (e.g. uploads fail for required documents for the selected provider).
    """

    def __init__(
        self,
        message: str,
        provider: str,
        missing_documents: Optional[List[str]] = None,
        reason: Optional[str] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.missing_documents = missing_documents or []
        self.reason = reason


class DocAwareHandler:
    """
    Handles DocAware integration and document context retrieval
    """
    
    def __init__(self, llm_provider_manager=None):
        """
        Initialize DocAwareHandler
        
        Args:
            llm_provider_manager: Optional LLMProviderManager instance for query refinement
        """
        self.llm_provider_manager = llm_provider_manager
    
    def is_docaware_enabled(self, agent_node: Dict[str, Any]) -> bool:
        """
        Check if DocAware (chunk-based RAG) is enabled for this agent.
        DocAware is considered enabled if:
        - doc_aware is True AND search_method is set
        """
        agent_data = agent_node.get('data', {})
        doc_aware = agent_data.get('doc_aware', False)
        search_method = agent_data.get('search_method')
        
        return doc_aware and bool(search_method)
    
    @staticmethod
    def is_file_attachments_enabled(agent_node: Dict[str, Any]) -> bool:
        """
        Check if file attachments are enabled for this agent (independent of DocAware).
        """
        agent_data = agent_node.get('data', {})
        return agent_data.get('file_attachments_enabled', False)
    
    async def get_file_attachment_references(
        self, 
        agent_node: Dict[str, Any], 
        project_id: str
    ) -> Dict[str, Any]:
        """
        Get file references for the File Attachments feature.
        
        Retrieves file_ids from ProjectDocument records that have been uploaded
        to the relevant LLM provider's File API. This is independent of DocAware.
        
        Args:
            agent_node: Agent configuration containing selected documents
            project_id: Project ID to get documents from
            
        Returns:
            Dict with:
            - mode: 'file_attachments'
            - file_references: List of {file_id, filename, provider} dicts
            - error: Optional error message
        """
        agent_data = agent_node.get('data', {})
        selected_docs = agent_data.get('file_attachment_documents', [])
        llm_provider = agent_data.get('llm_provider', 'openai')
        
        # Map provider names to field names
        provider_field_map = {
            'openai': 'llm_file_id_openai',
            'anthropic': 'llm_file_id_anthropic',
            'google': 'llm_file_id_google',
            'gemini': 'llm_file_id_google',  # alias
        }
        
        file_id_field = provider_field_map.get(llm_provider, 'llm_file_id_openai')
        
        logger.info(f"📎 FILE ATTACHMENTS: Getting file references for provider {llm_provider}")
        logger.info(f"📎 FILE ATTACHMENTS: Selected documents: {selected_docs}")
        
        try:
            # Get project
            project = await sync_to_async(
                IntelliDocProject.objects.get
            )(project_id=project_id)
            
            file_references = []
            missing_uploads = []
            
            if not selected_docs:
                # If no specific documents selected, get all processed documents
                documents = await sync_to_async(list)(
                    ProjectDocument.objects.filter(
                        project=project,
                        upload_status='ready'
                    )
                )
            else:
                # Get specific selected documents by original filename.
                # NOTE: If multiple documents share the same original filename,
                # all of them will be included and attached. This is logged for visibility.
                documents = await sync_to_async(list)(
                    ProjectDocument.objects.filter(
                        project=project,
                        original_filename__in=selected_docs
                    )
                )

                # Warn if there are duplicates by filename within the selection
                name_counts: Dict[str, int] = {}
                for d in documents:
                    name_counts[d.original_filename] = name_counts.get(d.original_filename, 0) + 1
                duplicate_names = [name for name, count in name_counts.items() if count > 1]
                if duplicate_names:
                    logger.warning(
                        "⚠️ FILE ATTACHMENTS: Multiple documents share the same original "
                        f"filename in project {project_id}: {', '.join(duplicate_names)}. "
                        "All matching documents will be attached."
                    )
            
            for doc in documents:
                file_id = getattr(doc, file_id_field, None)
                
                if not file_id:
                    # Lazy upload: attempt to upload the document to the provider now
                    logger.info(f"📎 FILE ATTACHMENTS: Lazy uploading {doc.original_filename} to {llm_provider}...")
                    try:
                        from .llm_file_service import LLMFileUploadService
                        service = LLMFileUploadService(project)
                        upload_result = await service._upload_to_provider(doc, llm_provider)
                        if upload_result.get('file_id'):
                            file_id = upload_result['file_id']
                            # Refresh from DB to get the updated field
                            await sync_to_async(doc.refresh_from_db)()
                            logger.info(f"📎 FILE ATTACHMENTS: Lazy upload succeeded for {doc.original_filename}: {file_id[:20]}...")
                        else:
                            error_msg = upload_result.get('error', 'Unknown error')
                            missing_uploads.append(doc.original_filename)
                            logger.warning(f"⚠️ FILE ATTACHMENTS: Lazy upload failed for {doc.original_filename}: {error_msg}")
                            continue
                    except Exception as upload_err:
                        missing_uploads.append(doc.original_filename)
                        logger.warning(f"⚠️ FILE ATTACHMENTS: Lazy upload exception for {doc.original_filename}: {upload_err}")
                        continue
                
                if file_id:
                    file_references.append({
                        'file_id': file_id,
                        'filename': doc.original_filename,
                        'document_id': str(doc.document_id),
                        'provider': llm_provider,
                        'file_type': doc.file_type,
                        'file_size': doc.file_size
                    })
                    logger.info(f"📎 FILE ATTACHMENTS: Found file_id for {doc.original_filename}: {file_id[:20]}...")
                else:
                    missing_uploads.append(doc.original_filename)
                    logger.warning(f"⚠️ FILE ATTACHMENTS: Document {doc.original_filename} not uploaded to {llm_provider}")
            
            result = {
                'mode': 'file_attachments',
                'provider': llm_provider,
                'file_references': file_references,
                'documents_found': len(documents),
                'documents_with_file_id': len(file_references)
            }
            
            if missing_uploads:
                # Treat missing uploads as a hard failure so the node fails clearly
                message = (
                    f"{len(missing_uploads)} document(s) could not be prepared for "
                    f"file attachments for provider {llm_provider}: {', '.join(missing_uploads)}"
                )
                logger.error(f"❌ FILE ATTACHMENTS: {message}")
                raise FileAttachmentPreparationError(
                    message=message,
                    provider=llm_provider,
                    missing_documents=missing_uploads,
                )
            
            logger.info(f"📎 FILE ATTACHMENTS: Returning {len(file_references)} file references")
            return result
            
        except IntelliDocProject.DoesNotExist:
            logger.error(f"❌ FILE ATTACHMENTS: Project {project_id} not found")
            return {
                'mode': 'file_attachments',
                'error': f'Project {project_id} not found',
                'file_references': []
            }
        except Exception as e:
            logger.error(f"❌ FILE ATTACHMENTS: Error getting file references: {e}")
            return {
                'mode': 'file_attachments',
                'error': str(e),
                'file_references': []
            }
    
    async def validate_and_reupload_inline_attachments(
        self,
        inline_attachments: List[Dict[str, Any]],
        provider: str,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Validate inline file attachment file_ids against the current API key.
        If a file_id is stale (uploaded with a previous key), re-upload the file
        and return the updated attachment with the new file_id.

        Args:
            inline_attachments: List of inline attachment dicts with file_id, filename, etc.
            provider: LLM provider name ('openai', 'anthropic', 'google')
            project_id: Project ID for API key access

        Returns:
            List of validated attachment dicts (stale ones re-uploaded or skipped)
        """
        if not inline_attachments:
            return []

        import aiohttp

        try:
            project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            logger.error(f"❌ INLINE VALIDATE: Project {project_id} not found")
            return inline_attachments  # Return as-is, let downstream handle errors

        from project_api_keys.services import get_project_api_key_service
        svc = get_project_api_key_service()
        api_key = await svc.get_project_api_key_async(project, provider)
        if not api_key:
            logger.warning(f"⚠️ INLINE VALIDATE: No API key for {provider}, skipping validation")
            return inline_attachments

        validated = []
        for att in inline_attachments:
            file_id = att.get('file_id')
            filename = att.get('filename', 'attachment')
            if not file_id:
                continue

            # Validate file_id is accessible with the current API key
            is_valid = False
            if provider == 'openai':
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                        async with session.get(
                            f"https://api.openai.com/v1/files/{file_id}",
                            headers={"Authorization": f"Bearer {api_key}"},
                        ) as resp:
                            is_valid = resp.status == 200
                            if not is_valid:
                                logger.warning(
                                    f"⚠️ INLINE VALIDATE: OpenAI file_id {file_id[:20]}... for '{filename}' "
                                    f"returned status {resp.status} — stale file_id from a different API key"
                                )
                except Exception as e:
                    logger.warning(f"⚠️ INLINE VALIDATE: Error checking file_id {file_id[:20]}...: {e}")
            else:
                # For other providers, assume valid (add validation later if needed)
                is_valid = True

            if is_valid:
                validated.append(att)
            else:
                # Attempt re-upload from project documents matching the filename
                logger.info(f"🔄 INLINE VALIDATE: Attempting re-upload of '{filename}' to {provider}")
                try:
                    docs = await sync_to_async(list)(
                        ProjectDocument.objects.filter(
                            project=project,
                            original_filename=filename,
                        )
                    )
                    if docs:
                        doc = docs[0]
                        # Clear the stale file_id so the upload service doesn't skip it
                        field_name = f'llm_file_id_{provider}'
                        if getattr(doc, field_name, None) == file_id:
                            setattr(doc, field_name, None)
                            await sync_to_async(doc.save)(update_fields=[field_name])

                        from .llm_file_service import LLMFileUploadService
                        service = LLMFileUploadService(project)
                        upload_result = await service._upload_to_provider(doc, provider)
                        new_file_id = upload_result.get('file_id')
                        if new_file_id:
                            logger.info(f"✅ INLINE VALIDATE: Re-uploaded '{filename}' — new file_id: {new_file_id[:20]}...")
                            att_copy = dict(att)
                            att_copy['file_id'] = new_file_id
                            validated.append(att_copy)
                        else:
                            logger.warning(f"⚠️ INLINE VALIDATE: Re-upload failed for '{filename}': {upload_result.get('error')}")
                    else:
                        logger.warning(
                            f"⚠️ INLINE VALIDATE: Cannot re-upload '{filename}' — "
                            f"document not found in project. The file was likely uploaded "
                            f"directly to a previous OpenAI account and is no longer accessible."
                        )
                except Exception as re_err:
                    logger.warning(f"⚠️ INLINE VALIDATE: Re-upload exception for '{filename}': {re_err}")

        return validated

    async def get_docaware_context_from_conversation_query(
        self, 
        agent_node: Dict[str, Any], 
        search_query: str, 
        project_id: str, 
        conversation_history: str
    ) -> str:
        """
        Retrieve document context using conversation-based search query for single agents.
        
        This is purely chunk-based DocAware. File attachments are handled
        separately by get_file_attachment_references().
        
        Args:
            agent_node: Agent configuration
            search_query: Search query extracted from conversation
            project_id: Project ID for document search
            conversation_history: Full conversation history for context
            
        Returns:
            Formatted document context string (chunk-based)
        """
        agent_data = agent_node.get('data', {})
        
        # Standard chunk-based DocAware
        search_method = agent_data.get('search_method', 'hybrid_search')
        search_parameters = agent_data.get('search_parameters', {})
        
        logger.info(f"📚 DOCAWARE: Single agent searching with method {search_method}")
        logger.info(f"📚 DOCAWARE: Query: {search_query[:100]}...")
        
        try:
            # Initialize DocAware service for this project using sync_to_async
            def create_docaware_service():
                return EnhancedDocAwareAgentService(project_id)
            
            docaware_service = await sync_to_async(create_docaware_service)()
            
            # Extract conversation context for contextual search methods
            conversation_context = self.extract_conversation_context(conversation_history)

            # Extract content_filters from agent config
            content_filters = agent_data.get('content_filters', [])

            # Perform document search with the conversation-based query using sync_to_async
            def perform_search():
                return docaware_service.search_documents(
                    query=search_query,
                    search_method=SearchMethod(search_method),
                    method_parameters=search_parameters,
                    conversation_context=conversation_context,
                    content_filters=content_filters
                )

            search_start = time.time()
            search_results = await sync_to_async(perform_search)()
            search_duration_ms = (time.time() - search_start) * 1000.0
            
            if not search_results:
                logger.info(f"📚 DOCAWARE: No relevant documents found for single agent query")
                return ""
            
            # Get search_limit from search_parameters (configured in frontend)
            search_limit = search_parameters.get('search_limit', 10)
            
            # Filter out documents with failed extraction status
            valid_results = []
            failed_results = []
            
            for result in search_results:
                content = result.get('content', '')
                # Check if content indicates failed extraction
                if content and ('Extraction Status: FAILED' in content or 
                               'This document could not be processed' in content):
                    failed_results.append(result)
                    logger.warning(f"⚠️ DOCAWARE: Filtering out document with failed extraction: {result.get('metadata', {}).get('source', 'Unknown')}")
                else:
                    valid_results.append(result)
            
            if failed_results:
                logger.warning(f"⚠️ DOCAWARE: Filtered out {len(failed_results)} document(s) with failed extraction status")
            
            if not valid_results:
                logger.error(f"❌ DOCAWARE: All {len(search_results)} search results have failed extraction status!")
                logger.error(f"❌ DOCAWARE: Search found {len(search_results)} document(s), but all contain 'Extraction Status: FAILED'")
                logger.error(f"❌ DOCAWARE: These documents were processed but content extraction failed during processing")
                logger.error(f"❌ DOCAWARE: ACTION REQUIRED: Delete these documents from the project and re-upload them")
                logger.error(f"❌ DOCAWARE: After re-uploading, wait for 'Start Processing' to complete successfully before using DocAware")
                return ""  # Return empty context if all documents failed
            
            # Format results for prompt inclusion
            context_parts = []
            context_parts.append(f"Found {len(valid_results)} relevant documents based on conversation context:\n")
            
            # Use configured search_limit, but don't exceed available results
            limit = min(len(valid_results), search_limit)

            # Fetch document-level short summaries (project-isolated) for context injection.
            doc_summary_cache: Dict[str, str] = {}
            included_doc_ids = set()
            try:
                limit_results = valid_results[:limit]
                doc_ids = []
                for r in limit_results:
                    meta = r.get('metadata') or {}
                    doc_id = meta.get('document_id')
                    if doc_id:
                        doc_ids.append(str(doc_id))

                doc_ids = list(dict.fromkeys(doc_ids))  # de-dupe while preserving order
                if doc_ids:
                    def fetch_summaries():
                        qs = ProjectDocumentSummary.objects.filter(
                            document__document_id__in=doc_ids,
                            document__project__project_id=project_id,
                        ).values_list('document__document_id', 'short_summary')
                        return [(str(doc_id), short_summary) for (doc_id, short_summary) in qs]

                    summaries = await sync_to_async(fetch_summaries)()
                    doc_summary_cache = {doc_id: short for (doc_id, short) in summaries if short and short.strip()}
            except Exception as summary_err:
                logger.warning(f"⚠️ DOCAWARE: Failed fetching doc-level summaries: {summary_err}")

            for i, result in enumerate(valid_results[:limit], 1):
                content = result['content']  # Use full content without truncation
                metadata = result['metadata']
                
                # Debug logging for content verification
                content_length = len(content) if content else 0
                content_preview = content[:200] if content and len(content) > 200 else content
                is_empty = not content or len(content.strip()) == 0
                
                logger.info(f"📚 DOCAWARE CONTENT DEBUG: Document {i} - Content length: {content_length} chars, Empty: {is_empty}")
                if content:
                    logger.info(f"📚 DOCAWARE CONTENT DEBUG: Document {i} preview (first 200 chars): {content_preview}...")
                else:
                    logger.warning(f"⚠️ DOCAWARE CONTENT DEBUG: Document {i} has EMPTY content! Available result keys: {list(result.keys())}")
                    logger.warning(f"⚠️ DOCAWARE CONTENT DEBUG: Document {i} metadata keys: {list(metadata.keys()) if metadata else 'None'}")
                
                context_parts.append(f"📄 Document {i} (Relevance: {metadata.get('score', 0):.3f}):")
                context_parts.append(f"   Source: {metadata.get('source', 'Unknown')}")
                
                if metadata.get('page'):
                    context_parts.append(f"   Page: {metadata['page']}")

                # Inject document-level summary only once per document_id.
                doc_id_str = str(metadata.get('document_id') or '').strip()
                if doc_id_str and doc_id_str not in included_doc_ids:
                    short_summary = doc_summary_cache.get(doc_id_str)
                    if short_summary:
                        context_parts.append("   === Document Short Summary ===")
                        context_parts.append(short_summary)
                    included_doc_ids.add(doc_id_str)
                    
                context_parts.append(f"   Content: {content}")
                context_parts.append("")  # Empty line separator
            
            # Add search metadata
            context_parts.append(f"Search performed using: {search_method}")
            context_parts.append(f"Query derived from conversation history")
            
            result_text = "\n".join(context_parts)
            logger.info(f"📚 DOCAWARE: Generated context from {len(valid_results)} valid results (filtered {len(failed_results)} failed, total {len(search_results)} results) ({len(result_text)} chars)")

            # Structured experiment log for DocAware impact / retrieval overhead
            try:
                agent_name = agent_data.get('name') or agent_node.get('data', {}).get('name', 'UnknownAgent')
                domain_counts: Dict[str, int] = {}
                for r in valid_results:
                    meta = r.get('metadata', {}) or {}
                    # Try common domain/category fields
                    domain = meta.get('category') or meta.get('domain') or meta.get('document_type') or 'unknown'
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1

                # Extract configuration
                configuration = {
                    "agent_name": agent_name,
                    "search_method": search_method,
                    "has_content_filters": bool(content_filters),
                }

                exp_payload = {
                    "experiment": "docaware_single_agent",
                    "project_id": project_id,
                    "agent_name": agent_name,
                    "search_method": search_method,
                    "query_length": len(search_query or ""),
                    "results_count": len(valid_results),
                    "failed_results_count": len(failed_results),
                    "total_results_count": len(search_results),
                    "search_duration_ms": search_duration_ms,
                    "content_filters": content_filters,
                    "domain_counts": domain_counts,
                }
                logger.info(f"EXP_METRIC_DOCAWARE_SINGLE | {json.dumps(exp_payload, default=str)}")
                
                # Store in database
                logger.info(f"📊 METRIC SAVE CHECK (DOCAWARE): project_id={project_id}, will_save={bool(project_id)}")
                if project_id:
                    try:
                        from users.models import IntelliDocProject, ExperimentMetric
                        # Note: sync_to_async is already imported at module level
                        
                        def save_metric():
                            try:
                                project_obj = IntelliDocProject.objects.get(project_id=project_id)
                                logger.info(f"📊 METRIC SAVE: Project found, creating ExperimentMetric for docaware_single...")
                                metric = ExperimentMetric.objects.create(
                                    project=project_obj,
                                    experiment_type='docaware_single',
                                    metric_data=exp_payload,
                                    configuration=configuration,
                                )
                                logger.info(f"✅ Stored DocAware experiment metric: id={metric.id}, project={project_id}")
                                return metric.id
                            except IntelliDocProject.DoesNotExist:
                                logger.warning(f"⚠️ Could not save experiment metric: Project {project_id} not found")
                                return None
                            except Exception as e:
                                logger.error(f"❌ Failed to save experiment metric to database: {e}", exc_info=True)
                                return None
                        
                        # Use sync_to_async for database write (imported at module level)
                        metric_id = await sync_to_async(save_metric)()
                        if metric_id:
                            logger.info(f"✅ METRIC SAVE SUCCESS: DocAware metric saved with ID {metric_id}")
                        else:
                            logger.warning(f"⚠️ METRIC SAVE FAILED: DocAware metric was not saved (check logs above)")
                    except Exception as db_error:
                        logger.warning(f"⚠️ Failed to store experiment metric in database: {db_error}", exc_info=True)
                else:
                    logger.warning(f"⚠️ METRIC SAVE SKIPPED (DOCAWARE): project_id is None or empty - metric will not be saved")
            except Exception as metric_error:
                logger.error(f"❌ EXP_METRIC_DOCAWARE_SINGLE: Failed to log metrics: {metric_error}")
            
            return result_text
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE: Error retrieving document context from conversation query: {e}")
            import traceback
            logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
            return f"⚠️ Document search failed: {str(e)}"
    
    def get_docaware_context(
        self, 
        agent_node: Dict[str, Any], 
        conversation_history: str, 
        project_id: str
    ) -> str:
        """
        Retrieve document context using DocAware service (chunk-based only).
        
        File attachments are handled separately via get_file_attachment_references().
        
        Returns:
            Formatted document context string
        """
        agent_data = agent_node.get('data', {})
        
        search_method = agent_data.get('search_method', 'hybrid_search')
        search_parameters = agent_data.get('search_parameters', {})
        
        logger.info(f"📚 DOCAWARE: Getting context for agent with method {search_method}")
        
        try:
            # Initialize DocAware service for this project
            docaware_service = EnhancedDocAwareAgentService(project_id)
            
            # Extract query from recent conversation history
            query = self.extract_query_from_conversation(conversation_history)
            
            if not query:
                logger.warning(f"📚 DOCAWARE: No query could be extracted from conversation history")
                return ""
            
            # Get conversation context for contextual search
            conversation_context = self.extract_conversation_context(conversation_history)

            # Extract content_filters from agent config
            content_filters = agent_data.get('content_filters', [])

            # Perform document search
            search_start = time.time()
            search_results = docaware_service.search_documents(
                query=query,
                search_method=SearchMethod(search_method),
                method_parameters=search_parameters,
                conversation_context=conversation_context,
                content_filters=content_filters
            )
            search_duration_ms = (time.time() - search_start) * 1000.0
            
            if not search_results:
                logger.info(f"📚 DOCAWARE: No relevant documents found for query: {query[:50]}...")
                return ""
            
            # Get search_limit from search_parameters (configured in frontend)
            search_limit = search_parameters.get('search_limit', 10)
            
            # Filter out documents with failed extraction status
            valid_results = []
            failed_results = []
            
            for result in search_results:
                content = result.get('content', '')
                # Check if content indicates failed extraction
                if content and ('Extraction Status: FAILED' in content or 
                               'This document could not be processed' in content):
                    failed_results.append(result)
                    logger.warning(f"⚠️ DOCAWARE: Filtering out document with failed extraction: {result.get('metadata', {}).get('source', 'Unknown')}")
                else:
                    valid_results.append(result)
            
            if failed_results:
                logger.warning(f"⚠️ DOCAWARE: Filtered out {len(failed_results)} document(s) with failed extraction status")
            
            if not valid_results:
                logger.error(f"❌ DOCAWARE: All {len(search_results)} search results have failed extraction status!")
                logger.error(f"❌ DOCAWARE: Search found {len(search_results)} document(s), but all contain 'Extraction Status: FAILED'")
                logger.error(f"❌ DOCAWARE: These documents were processed but content extraction failed during processing")
                logger.error(f"❌ DOCAWARE: ACTION REQUIRED: Delete these documents from the project and re-upload them")
                logger.error(f"❌ DOCAWARE: After re-uploading, wait for 'Start Processing' to complete successfully before using DocAware")
                return ""  # Return empty context if all documents failed
            
            # Format results for prompt
            context_parts = []
            context_parts.append(f"Found {len(valid_results)} relevant documents for your query:\n")
            
            # Use configured search_limit, but don't exceed available results
            limit = min(len(valid_results), search_limit)

            # Fetch document-level short summaries (project-isolated) for context injection.
            doc_summary_cache: Dict[str, str] = {}
            included_doc_ids = set()
            try:
                limit_results = valid_results[:limit]
                doc_ids = []
                for r in limit_results:
                    meta = r.get('metadata') or {}
                    doc_id = meta.get('document_id')
                    if doc_id:
                        doc_ids.append(str(doc_id))

                doc_ids = list(dict.fromkeys(doc_ids))
                if doc_ids:
                    qs = ProjectDocumentSummary.objects.filter(
                        document__document_id__in=doc_ids,
                        document__project__project_id=project_id,
                    ).values_list('document__document_id', 'short_summary')
                    doc_summary_cache = {str(doc_id): short_summary for (doc_id, short_summary) in qs if short_summary and short_summary.strip()}
            except Exception as summary_err:
                logger.warning(f"⚠️ DOCAWARE: Failed fetching doc-level summaries: {summary_err}")

            for i, result in enumerate(valid_results[:limit], 1):
                content = result['content']  # Use full content without truncation
                metadata = result['metadata']
                
                # Debug logging for content verification
                content_length = len(content) if content else 0
                content_preview = content[:200] if content and len(content) > 200 else content
                is_empty = not content or len(content.strip()) == 0
                
                logger.info(f"📚 DOCAWARE CONTENT DEBUG: Document {i} - Content length: {content_length} chars, Empty: {is_empty}")
                if content:
                    logger.info(f"📚 DOCAWARE CONTENT DEBUG: Document {i} preview (first 200 chars): {content_preview}...")
                else:
                    logger.warning(f"⚠️ DOCAWARE CONTENT DEBUG: Document {i} has EMPTY content! Available result keys: {list(result.keys())}")
                    logger.warning(f"⚠️ DOCAWARE CONTENT DEBUG: Document {i} metadata keys: {list(metadata.keys()) if metadata else 'None'}")
                
                context_parts.append(f"Document {i} (Score: {metadata.get('score', 0):.3f}):")
                context_parts.append(f"Source: {metadata.get('source', 'Unknown')}")
                if metadata.get('page'):
                    context_parts.append(f"Page: {metadata['page']}")

                # Inject document-level summary only once per document_id.
                doc_id_str = str(metadata.get('document_id') or '').strip()
                if doc_id_str and doc_id_str not in included_doc_ids:
                    short_summary = doc_summary_cache.get(doc_id_str)
                    if short_summary:
                        context_parts.append("   === Document Short Summary ===")
                        context_parts.append(short_summary)
                    included_doc_ids.add(doc_id_str)

                context_parts.append(f"Content: {content}")
                context_parts.append("")  # Empty line separator
            
            result_text = "\n".join(context_parts)
            logger.info(f"📚 DOCAWARE: Generated context with {len(valid_results)} valid results (filtered {len(failed_results)} failed, total {len(search_results)} results) ({len(result_text)} chars)")

            # Structured experiment log for DocAware impact (generic path)
            try:
                agent_name = agent_data.get('name') or agent_node.get('data', {}).get('name', 'UnknownAgent')
                domain_counts: Dict[str, int] = {}
                for r in valid_results:
                    meta = r.get('metadata', {}) or {}
                    domain = meta.get('category') or meta.get('domain') or meta.get('document_type') or 'unknown'
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1

                # Extract configuration
                configuration = {
                    "agent_name": agent_name,
                    "search_method": search_method,
                    "has_content_filters": bool(content_filters),
                }
                
                exp_payload = {
                    "experiment": "docaware_contextual",
                    "project_id": project_id,
                    "agent_name": agent_name,
                    "search_method": search_method,
                    "query_length": len(query or ""),
                    "results_count": len(valid_results),
                    "failed_results_count": len(failed_results),
                    "total_results_count": len(search_results),
                    "search_duration_ms": search_duration_ms,
                    "content_filters": content_filters,
                    "domain_counts": domain_counts,
                }
                logger.info(f"EXP_METRIC_DOCAWARE_CONTEXT | {json.dumps(exp_payload, default=str)}")
                
                # Store in database (sync method, so use direct DB call - no await needed)
                logger.info(f"📊 METRIC SAVE CHECK (DOCAWARE_CONTEXT): project_id={project_id}, will_save={bool(project_id)}")
                if project_id:
                    try:
                        from users.models import IntelliDocProject, ExperimentMetric
                        
                        try:
                            project_obj = IntelliDocProject.objects.get(project_id=project_id)
                            logger.info(f"📊 METRIC SAVE: Project found, creating ExperimentMetric for docaware_context...")
                            metric = ExperimentMetric.objects.create(
                                project=project_obj,
                                experiment_type='docaware_context',
                                metric_data=exp_payload,
                                configuration=configuration,
                            )
                            logger.info(f"✅ Stored DocAware context experiment metric: id={metric.id}, project={project_id}")
                        except IntelliDocProject.DoesNotExist:
                            logger.warning(f"⚠️ Could not save experiment metric: Project {project_id} not found")
                        except Exception as e:
                            logger.error(f"❌ Failed to save experiment metric to database: {e}", exc_info=True)
                            import traceback
                            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                    except Exception as db_error:
                        logger.error(f"❌ Failed to store experiment metric in database: {db_error}", exc_info=True)
                        import traceback
                        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                else:
                    logger.warning(f"⚠️ METRIC SAVE SKIPPED (DOCAWARE_CONTEXT): project_id is None or empty - metric will not be saved")
            except Exception as metric_error:
                logger.error(f"❌ EXP_METRIC_DOCAWARE_CONTEXT: Failed to log metrics: {metric_error}")
            
            return result_text
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE: Error retrieving document context: {e}")
            return ""
    
    def extract_query_from_conversation(self, conversation_history: str, max_length: Optional[int] = None) -> str:
        """
        Extract a search query from the conversation history
        
        Intelligently extracts the user's actual question, not the full conversation.
        Prioritizes the last user message, ignoring assistant responses and start node messages.
        
        Args:
            conversation_history: Full conversation history
            max_length: Optional maximum length (default: None - no limit)
                       Kept for backward compatibility but not enforced
        """
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Starting with conversation: '{conversation_history[:200]}...'")
        
        if not conversation_history.strip():
            logger.warning(f"📚 DOCAWARE QUERY EXTRACTION: Empty conversation history")
            return ""
        
        # Split conversation into lines
        lines = conversation_history.strip().split('\n')
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Split into {len(lines)} lines")
        
        # Look for the last user message (most relevant for search)
        # Format can be: "User: ..." or "User: ..." or node names like "Start Node: ..."
        user_query = None
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a user message
            # Patterns: "User:", "user:", or lines that don't start with assistant/agent names
            line_lower = line.lower()
            
            # SPECIAL CASE: "Start Node:" contains the user's initial query
            if line_lower.startswith('start node:'):
                user_query = line.split(':', 1)[1].strip() if ':' in line else line
                logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Found query from Start Node: '{user_query[:100]}...'")
                break

            # Skip assistant/agent responses (but NOT Start Node which we handled above)
            if any(skip in line_lower for skip in ['assistant:', 'ai assistant', 'end node:']):
                continue
            
            # Check for explicit "User:" prefix
            if line_lower.startswith('user:'):
                user_query = line.split(':', 1)[1].strip() if ':' in line else line
                logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Found user message with 'User:' prefix: '{user_query[:100]}...'")
                break
            
            # If no explicit "User:" found, check if line doesn't look like an assistant response
            # and contains a question or query-like content
            if ':' in line:
                prefix = line.split(':', 1)[0].strip().lower()
                # If it's not an assistant/agent prefix, it might be a user message
                if 'assistant' not in prefix and 'ai' not in prefix and 'start' not in prefix and 'end' not in prefix:
                    # This might be a user message without explicit "User:" label
                    potential_query = line.split(':', 1)[1].strip() if ':' in line else line
                    # Only use if it looks like a question/query (has question words or is reasonably short)
                    if any(word in potential_query.lower() for word in ['what', 'how', 'tell', 'explain', 'find', 'search', 'about', '?']):
                        user_query = potential_query
                        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Found potential user query: '{user_query[:100]}...'")
                        break
        
        # If we found a user query, use it
        if user_query:
            query_text = user_query
        else:
            # Fallback: get the last few meaningful lines (excluding assistant responses)
            recent_lines = []
            for line in reversed(lines[-10:]):
                line = line.strip()
                if not line:
                    continue
                line_lower = line.lower()
                # Skip assistant/agent responses
                if any(skip in line_lower for skip in ['assistant:', 'ai assistant', 'start node:', 'end node:']):
                    continue
                recent_lines.insert(0, line)
                if len(recent_lines) >= 3:  # Limit to last 3 non-assistant lines
                    break
            
            if recent_lines:
                query_text = " ".join(recent_lines)
                logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Using fallback - combined {len(recent_lines)} lines")
            else:
                logger.warning(f"📚 DOCAWARE QUERY EXTRACTION: No user query found in conversation history")
                return ""
        
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Extracted query length: {len(query_text)} characters")
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Query: '{query_text[:200]}...'")
        
        # No truncation by default - use full query to preserve all context
        # The embedding model will handle longer queries internally
        # Only truncate if explicitly requested (for very long conversations)
        if max_length and len(query_text) > max_length:
            # Try to break at sentence boundary for very long conversations
            truncated = query_text[:max_length]
            last_sentence_end = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
            
            if last_sentence_end > max_length * 0.7:  # If we can get at least 70% with complete sentences
                query_text = truncated[:last_sentence_end + 1]
            else:
                # Break at word boundary
                query_text = truncated.rsplit(' ', 1)[0] + "..."
            logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Truncated to {len(query_text)} chars due to explicit max_length limit")
        else:
            logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Using full query ({len(query_text)} chars) - no truncation")
        
        # Check for forbidden patterns
        rejected_queries = ['test query', 'test query for document search', 'sample query', 'example query']
        if query_text.lower().strip() in rejected_queries:
            logger.error(f"📚 DOCAWARE QUERY EXTRACTION: DETECTED FORBIDDEN QUERY: '{query_text}' - This should not happen!")
            logger.error(f"📚 DOCAWARE QUERY EXTRACTION: Original conversation history was: '{conversation_history}'")
            # Return empty to prevent the forbidden query from being used
            return ""
        
        logger.info(f"📚 DOCAWARE QUERY EXTRACTION: Final extracted query: '{query_text[:100]}...'")
        return query_text
    
    def extract_conversation_context(self, conversation_history: str, max_turns: int = 3) -> List[str]:
        """
        Extract conversation context for contextual search
        """
        if not conversation_history.strip():
            return []
        
        # Split into turns and get recent ones
        lines = conversation_history.strip().split('\n')
        meaningful_lines = [line.strip() for line in lines if line.strip()]
        
        # Take last few turns
        recent_context = meaningful_lines[-max_turns:] if meaningful_lines else []
        
        logger.debug(f"📚 DOCAWARE: Extracted context with {len(recent_context)} turns")
        return recent_context
    
    def extract_search_query_from_aggregated_input(
        self, 
        aggregated_context: Dict[str, Any], 
        agent_node: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Extract search query from aggregated input context (all connected agent outputs)
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs
            agent_node: Optional agent node for query refinement settings
            
        Returns:
            Search query string extracted from aggregated inputs
        """
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Starting with {aggregated_context['input_count']} inputs")
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Primary input: '{str(aggregated_context.get('primary_input', ''))[:200]}...'")
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Secondary inputs count: {len(aggregated_context.get('secondary_inputs', []))}")
        
        # Combine all input content for search query
        query_parts = []
        
        # Add primary input (prefer plain text without upstream citation appendix for embedding)
        primary_plain = aggregated_context.get('primary_plain')
        if primary_plain:
            query_parts.append(str(primary_plain))
            logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Added primary_plain: '{str(primary_plain)[:100]}...'")
        elif aggregated_context['primary_input']:
            primary_input = str(aggregated_context['primary_input'])
            query_parts.append(primary_input)
            logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Added primary input: '{primary_input[:100]}...'")
        
        # Add secondary inputs
        for i, secondary in enumerate(aggregated_context['secondary_inputs']):
            sec_plain = secondary.get('content_plain')
            if sec_plain:
                query_parts.append(str(sec_plain))
                logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Added secondary plain {i+1}: '{str(sec_plain)[:100]}...'")
            elif secondary.get('content'):
                secondary_content = str(secondary['content'])
                query_parts.append(secondary_content)
                logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Added secondary input {i+1}: '{secondary_content[:100]}...'")
        
        # Combine and clean up
        combined_query = " ".join(query_parts).strip()
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Combined query length: {len(combined_query)} characters")
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Combined query preview: '{combined_query[:200]}...'")
        
        if not combined_query:
            logger.warning(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Empty combined query")
            return ""
        
        # No truncation - use full query to preserve all context
        # The embedding model will handle longer queries internally
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Using full query ({len(combined_query)} chars) - no truncation")
        
        # Check for forbidden patterns
        rejected_queries = ['test query', 'test query for document search', 'sample query', 'example query']
        if combined_query.lower().strip() in rejected_queries:
            logger.error(f"📚 AGGREGATED INPUT QUERY EXTRACTION: DETECTED FORBIDDEN QUERY: '{combined_query}' - This should not happen!")
            logger.error(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Original aggregated context was: {aggregated_context}")
            # Return empty to prevent the forbidden query from being used
            return ""
        
        logger.info(f"📚 AGGREGATED INPUT QUERY EXTRACTION: Final extracted query: '{combined_query[:100]}...'")
        
        # Note: LLM refinement will be applied in get_docaware_context_from_query if enabled
        # This keeps the extraction method synchronous and allows async refinement later
        
        return combined_query
    
    async def refine_query_with_llm(
        self, 
        query: str, 
        project_id: str, 
        agent_node: Dict[str, Any]
    ) -> str:
        """
        Refine search query using LLM to preserve all key concepts while optimizing for search
        
        Args:
            query: Original search query (can be very long)
            project_id: Project ID for LLM API key retrieval
            agent_node: Agent configuration (may contain LLM provider settings)
            
        Returns:
            Refined query optimized for search, or original query if LLM refinement fails
        """
        if not self.llm_provider_manager:
            logger.warning(f"📚 QUERY REFINEMENT: LLM provider manager not available, using original query")
            return query
        
        if not query or len(query.strip()) < 50:
            # Don't refine very short queries
            logger.debug(f"📚 QUERY REFINEMENT: Query too short ({len(query)} chars), skipping refinement")
            return query
        
        try:
            # Get project for API key retrieval
            from users.models import IntelliDocProject
            # Note: sync_to_async is already imported at module level
            
            project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
            
            # Get agent config for LLM provider settings
            agent_data = agent_node.get('data', {})
            
            # Use agent's LLM provider if specified, otherwise default to OpenAI
            llm_provider_type = agent_data.get('llm_provider', 'openai')
            llm_model = agent_data.get('llm_model', 'gpt-3.5-turbo')
            
            # Create LLM provider configuration
            agent_config = {
                'llm_provider': llm_provider_type,
                'llm_model': llm_model,
                'max_tokens': 200,  # Short response for query refinement
                'temperature': 0.3  # Lower temperature for more focused queries
            }
            
            logger.info(f"📚 QUERY REFINEMENT: Refining query ({len(query)} chars) using {llm_provider_type} {llm_model}")
            
            # Get LLM provider
            llm_provider = await self.llm_provider_manager.get_llm_provider(agent_config, project)
            
            if not llm_provider:
                logger.warning(f"📚 QUERY REFINEMENT: Could not create LLM provider, using original query")
                return query
            
            # Get agent's system message for context-aware refinement
            agent_system_message = agent_data.get('system_message', '')
            
            # Create refinement prompt
            refinement_prompt = f"""You are a search query optimizer. Your task is to create an optimal search query that preserves all key concepts from the input while being concise and effective for document retrieval.

Original query (from multiple agent outputs):
{query}

Create an optimized search query that:
1. Preserves ALL key concepts, topics, and important information
2. Combines related concepts intelligently
3. Removes redundancy and filler words
4. Maintains the semantic meaning and intent
5. Is optimized for vector similarity search"""
            
            # Add agent-specific context if system message exists
            if agent_system_message and agent_system_message.strip():
                refinement_prompt += f"""

Refine the query to extract helpful insights to achieve the below:
{agent_system_message}"""
            
            refinement_prompt += """

Return ONLY the refined search query, nothing else. Do not add explanations or commentary.

Refined search query:"""
            
            # Generate refined query
            llm_response = await llm_provider.generate_response(
                prompt=refinement_prompt,
                temperature=0.3
            )
            
            if llm_response.error:
                logger.warning(f"📚 QUERY REFINEMENT: LLM generation failed: {llm_response.error}, using original query")
                return query
            
            refined_query = llm_response.text.strip()
            
            # Clean up the response (remove quotes if present, trim whitespace)
            refined_query = refined_query.strip('"\'')
            
            if not refined_query or len(refined_query) < 10:
                logger.warning(f"📚 QUERY REFINEMENT: Refined query too short or empty, using original query")
                return query
            
            logger.info(f"📚 QUERY REFINEMENT: Successfully refined query from {len(query)} to {len(refined_query)} chars")
            logger.debug(f"📚 QUERY REFINEMENT: Original: '{query[:200]}...'")
            logger.debug(f"📚 QUERY REFINEMENT: Refined: '{refined_query[:200]}...'")
            
            return refined_query
            
        except Exception as e:
            logger.error(f"❌ QUERY REFINEMENT: Error during query refinement: {e}")
            import traceback
            logger.error(f"❌ QUERY REFINEMENT: Traceback: {traceback.format_exc()}")
            # Fallback to original query on any error
            return query
    
    async def get_docaware_context_from_query(self, agent_node: Dict[str, Any], search_query: str, project_id: str, aggregated_context: Dict[str, Any]) -> str:
        """
        Retrieve document context using a specific search query (from aggregated input)
        
        Args:
            agent_node: Agent configuration
            search_query: Search query extracted from aggregated inputs
            project_id: Project ID for document search
            aggregated_context: Full aggregated context for metadata
            
        Returns:
            Formatted document context string
        """
        agent_data = agent_node.get('data', {})
        search_method = agent_data.get('search_method', 'hybrid_search')
        search_parameters = agent_data.get('search_parameters', {})
        
        # Check if query refinement is enabled
        query_refinement_enabled = agent_data.get('query_refinement_enabled', False)
        
        # Apply LLM refinement if enabled
        if query_refinement_enabled and self.llm_provider_manager:
            logger.info(f"📚 DOCAWARE: Query refinement enabled, refining query before search")
            search_query = await self.refine_query_with_llm(search_query, project_id, agent_node)
        
        logger.info(f"📚 DOCAWARE: Searching documents with method {search_method}")
        logger.info(f"📚 DOCAWARE: Query length: {len(search_query)} chars, preview: '{search_query[:100]}...'")
        
        try:
            # Initialize DocAware service for this project using sync_to_async
            def create_docaware_service():
                return EnhancedDocAwareAgentService(project_id)
            
            docaware_service = await sync_to_async(create_docaware_service)()
            
            # Extract conversation context from aggregated input for contextual search methods
            conversation_context = self.extract_conversation_context_from_aggregated_input(aggregated_context)

            # Extract content_filters from agent config
            content_filters = agent_data.get('content_filters', [])

            # Perform document search with the aggregated input query using sync_to_async
            def perform_search():
                return docaware_service.search_documents(
                    query=search_query,
                    search_method=SearchMethod(search_method),
                    method_parameters=search_parameters,
                    conversation_context=conversation_context,
                    content_filters=content_filters
                )

            search_results = await sync_to_async(perform_search)()
            
            if not search_results:
                logger.info(f"📚 DOCAWARE: No relevant documents found for aggregated input query")
                return ""
            
            # Get search_limit from search_parameters (configured in frontend)
            search_limit = search_parameters.get('search_limit', 10)
            
            # Filter out documents with failed extraction status
            valid_results = []
            failed_results = []
            
            for result in search_results:
                content = result.get('content', '')
                # Check if content indicates failed extraction
                if content and ('Extraction Status: FAILED' in content or 
                               'This document could not be processed' in content):
                    failed_results.append(result)
                    logger.warning(f"⚠️ DOCAWARE: Filtering out document with failed extraction: {result.get('metadata', {}).get('source', 'Unknown')}")
                else:
                    valid_results.append(result)
            
            if failed_results:
                logger.warning(f"⚠️ DOCAWARE: Filtered out {len(failed_results)} document(s) with failed extraction status")
            
            if not valid_results:
                logger.error(f"❌ DOCAWARE: All {len(search_results)} search results have failed extraction status!")
                logger.error(f"❌ DOCAWARE: Search found {len(search_results)} document(s), but all contain 'Extraction Status: FAILED'")
                logger.error(f"❌ DOCAWARE: These documents were processed but content extraction failed during processing")
                logger.error(f"❌ DOCAWARE: ACTION REQUIRED: Delete these documents from the project and re-upload them")
                logger.error(f"❌ DOCAWARE: After re-uploading, wait for 'Start Processing' to complete successfully before using DocAware")
                return ""  # Return empty context if all documents failed
            
            # Format results for prompt inclusion
            context_parts = []
            context_parts.append(f"Found {len(valid_results)} relevant documents based on connected agent inputs:\n")
            
            # Use configured search_limit, but don't exceed available results
            limit = min(len(valid_results), search_limit)

            # Fetch document-level short summaries (project-isolated) for context injection.
            doc_summary_cache: Dict[str, str] = {}
            included_doc_ids = set()
            try:
                limit_results = valid_results[:limit]
                doc_ids = []
                for r in limit_results:
                    meta = r.get('metadata') or {}
                    doc_id = meta.get('document_id')
                    if doc_id:
                        doc_ids.append(str(doc_id))
                doc_ids = list(dict.fromkeys(doc_ids))
                if doc_ids:
                    def fetch_summaries():
                        qs = ProjectDocumentSummary.objects.filter(
                            document__document_id__in=doc_ids,
                            document__project__project_id=project_id,
                        ).values_list('document__document_id', 'short_summary')
                        return [(str(doc_id), short_summary) for (doc_id, short_summary) in qs]

                    summaries = await sync_to_async(fetch_summaries)()
                    doc_summary_cache = {
                        doc_id: short for (doc_id, short) in summaries if short and short.strip()
                    }
            except Exception as summary_err:
                logger.warning(f"⚠️ DOCAWARE: Failed fetching doc-level summaries: {summary_err}")

            for i, result in enumerate(valid_results[:limit], 1):
                content = result['content']  # Use full content without truncation
                metadata = result['metadata']
                
                # Debug logging for content verification
                content_length = len(content) if content else 0
                content_preview = content[:200] if content and len(content) > 200 else content
                is_empty = not content or len(content.strip()) == 0
                
                logger.info(f"📚 DOCAWARE CONTENT DEBUG: Document {i} - Content length: {content_length} chars, Empty: {is_empty}")
                if content:
                    logger.info(f"📚 DOCAWARE CONTENT DEBUG: Document {i} preview (first 200 chars): {content_preview}...")
                else:
                    logger.warning(f"⚠️ DOCAWARE CONTENT DEBUG: Document {i} has EMPTY content! Available result keys: {list(result.keys())}")
                    logger.warning(f"⚠️ DOCAWARE CONTENT DEBUG: Document {i} metadata keys: {list(metadata.keys()) if metadata else 'None'}")
                
                context_parts.append(f"📄 Document {i} (Relevance: {metadata.get('score', 0):.3f}):")
                context_parts.append(f"   Source: {metadata.get('source', 'Unknown')}")
                
                if metadata.get('page'):
                    context_parts.append(f"   Page: {metadata['page']}")

                # Inject document-level summary only once per document_id.
                doc_id_str = str(metadata.get('document_id') or '').strip()
                if doc_id_str and doc_id_str not in included_doc_ids:
                    short_summary = doc_summary_cache.get(doc_id_str)
                    if short_summary:
                        context_parts.append("   === Document Short Summary ===")
                        context_parts.append(short_summary)
                    included_doc_ids.add(doc_id_str)
                    
                context_parts.append(f"   Content: {content}")
                context_parts.append("")  # Empty line separator
            
            # Add search metadata
            context_parts.append(f"Search performed using: {search_method}")
            context_parts.append(f"Query derived from {aggregated_context['input_count']} connected agent outputs")
            
            result_text = "\n".join(context_parts)
            logger.info(f"📚 DOCAWARE: Generated context from {len(valid_results)} valid results (filtered {len(failed_results)} failed, total {len(search_results)} results) ({len(result_text)} chars)")
            
            return result_text
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE: Error retrieving document context from aggregated input: {e}")
            import traceback
            logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
            return f"⚠️ Document search failed: {str(e)}"
    
    def extract_conversation_context_from_aggregated_input(self, aggregated_context: Dict[str, Any]) -> List[str]:
        """
        Extract conversation context from aggregated input for contextual search methods
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs
            
        Returns:
            List of conversation context strings
        """
        context_list = []
        
        # Add primary input as context
        if aggregated_context['primary_input']:
            context_list.append(str(aggregated_context['primary_input']))
        
        # Add secondary inputs as context
        for secondary in aggregated_context['secondary_inputs']:
            if secondary.get('content'):
                context_list.append(f"{secondary['name']}: {secondary['content']}")
        
        logger.debug(f"📚 DOCAWARE: Extracted {len(context_list)} context items from aggregated input")
        return context_list

    # =========================================================================
    # Tool-based DocAware (LLM-callable document search)
    # =========================================================================

    DOCAWARE_TOOL_NAME = "document_search"

    def build_docaware_tool(self, agent_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Build an OpenAI-format tool schema for document vector search.

        Returns None if DocAware is not enabled for this agent.
        """
        if not self.is_docaware_enabled(agent_node):
            return None

        return {
            "type": "function",
            "function": {
                "name": self.DOCAWARE_TOOL_NAME,
                "description": (
                    "Search project documents for relevant passages using "
                    "vector similarity search. Use this to find specific "
                    "information, facts, or excerpts from the project's "
                    "document collection."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant document passages",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 5)",
                            "minimum": 1,
                            "maximum": 20,
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    async def execute_docaware_tool(
        self,
        agent_node: Dict[str, Any],
        query: str,
        project_id: str,
        limit: int = 5,
    ) -> str:
        """
        Execute a DocAware search tool call and return formatted results.

        Uses hybrid search by default with no query refinement --
        the LLM formulates the query directly.
        """
        agent_data = agent_node.get('data', {})
        limit = max(1, min(limit, 20))

        logger.info(
            f"📚 DOCAWARE TOOL: query='{(query or '')[:60]}', limit={limit}"
        )
        start_time = time.time()

        try:
            def create_service():
                return EnhancedDocAwareAgentService(project_id)

            docaware_service = await sync_to_async(create_service)()

            content_filters = agent_data.get('content_filters', [])
            search_params = {"search_limit": limit}

            def perform_search():
                return docaware_service.search_documents(
                    query=query,
                    search_method=SearchMethod.HYBRID_SEARCH,
                    method_parameters=search_params,
                    conversation_context=None,
                    content_filters=content_filters if content_filters else None,
                )

            search_results = await sync_to_async(perform_search)()

            duration_ms = (time.time() - start_time) * 1000

            if not search_results:
                logger.info(
                    f"📚 DOCAWARE TOOL: no results in {duration_ms:.0f}ms"
                )
                return "No relevant passages found for the query."

            valid_results = [
                r for r in search_results
                if r.get('content') and r['content'].strip()
            ]
            if not valid_results:
                return "No relevant passages found for the query."

            parts: List[str] = []
            parts.append(f"Found {len(valid_results)} relevant passages:\n")

            for i, result in enumerate(valid_results[:limit], 1):
                content = result['content']
                meta = result.get('metadata', {})
                source = meta.get('source', 'Unknown')
                page = meta.get('page')
                score = meta.get('score', 0)

                header = f"[{i}] Source: {source}"
                if page:
                    header += f", Page: {page}"
                header += f", Relevance: {score:.3f}"

                parts.append(header)
                parts.append(f"Content: {content}")
                parts.append("")

            context = "\n".join(parts)

            logger.info(
                f"📚 DOCAWARE TOOL: {len(valid_results)} results in "
                f"{duration_ms:.0f}ms, {len(context)} chars"
            )
            return context

        except Exception as e:
            logger.error(f"❌ DOCAWARE TOOL: Error: {e}")
            return f"Document search failed: {str(e)}"