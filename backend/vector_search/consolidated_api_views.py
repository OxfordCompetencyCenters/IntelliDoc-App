# Consolidated Vector Search API - Phase 2 Consolidation
# backend/vector_search/consolidated_api_views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from users.models import IntelliDocProject
from .services_enhanced import EnhancedVectorSearchManager, PROCESSING_CONTROL, PROCESSING_THREADS
from .unified_services_fixed import UnifiedVectorSearchManager, fix_existing_documents
from .detailed_logger import DocumentProcessingTracker, doc_logger
import logging
import threading
import time

logger = logging.getLogger(__name__)

def run_processing_in_background(project_id: str, processing_mode: str = 'enhanced', llm_config=None):
    """Run enhanced document processing in background thread (project-isolated)."""
    try:
        cfg = llm_config or {}
        doc_logger.info(f"🚀 CONSOLIDATED PROCESSING STARTED | Project: {project_id} | Mode: {processing_mode}")
        logger.info(f"Starting consolidated processing for project {project_id} (background)")
        
        # Update PROCESSING_CONTROL so status endpoint shows is_processing=True
        PROCESSING_CONTROL[project_id] = {
            'status': 'PROCESSING',
            'stop_requested': False,
            'current_document_id': None,
        }
        
        result = UnifiedVectorSearchManager.process_project_documents(
            project_id,
            processing_mode=processing_mode,
            llm_provider=cfg.get('llm_provider'),
            llm_model=cfg.get('llm_model'),
            enable_summary=cfg.get('enable_summary', True),
        )
        
        # Update PROCESSING_CONTROL on completion
        PROCESSING_CONTROL[project_id] = {
            'status': 'COMPLETED' if result.get('status') in ('completed', 'all_already_processed') else 'FAILED',
            'stop_requested': False,
            'current_document_id': None,
        }
        
        doc_logger.info(f"✅ CONSOLIDATED PROCESSING COMPLETED | Project: {project_id} | Result: {result.get('status', 'unknown')}")
        logger.info(f"📦 PROJECT ISOLATION: Completed processing thread for project {project_id} (Total active: {len(PROCESSING_THREADS) - 1})")
        
        if project_id in PROCESSING_THREADS:
            del PROCESSING_THREADS[project_id]
    except Exception as e:
        doc_logger.error(f"❌ CONSOLIDATED PROCESSING FAILED | Project: {project_id} | Error: {str(e)}")
        logger.error(f"Consolidated processing failed for project {project_id}: {e}")
        # Update PROCESSING_CONTROL on failure
        PROCESSING_CONTROL[project_id] = {
            'status': 'FAILED',
            'stop_requested': False,
            'current_document_id': None,
        }
        if project_id in PROCESSING_THREADS:
            del PROCESSING_THREADS[project_id]

def process_unified_consolidated(request, project_id, llm_config=None, processing_mode_override=None):
    """
    CONSOLIDATED PROCESSING ENDPOINT - Phase 2
    
    Combines all processing capabilities into a single, intelligent endpoint
    that automatically selects the best processing mode based on project configuration
    
    Args:
        request: Django HttpRequest (for authentication/permission checks)
        project_id: Project ID to process
        llm_config: Optional dict with llm_provider, llm_model, enable_summary
        processing_mode_override: Optional processing mode override
    """
    try:
        # Verify project exists
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        # Enforce project access (legacy path is not behind ViewSet get_object())
        if not project.has_user_access(request.user):
            return Response(
                {'error': 'You do not have permission to access this project'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Duplicate-run guard: do not start if this project is already processing (multi-project isolation)
        if project_id in PROCESSING_THREADS and PROCESSING_THREADS[project_id].is_alive():
            logger.warning(f"⚠️ CONSOLIDATED: Processing already in progress for project {project_id}, rejecting duplicate request")
            return Response({
                'success': False,
                'status': 'already_running',
                'error': 'Processing already in progress',
                'message': 'Processing is already running for this project. Wait for it to finish or check status.',
                'project_id': str(project_id),
            }, status=status.HTTP_409_CONFLICT)
        
        logger.info(f"🚀 CONSOLIDATED: Processing request for project {project.name} (ID: {project_id})")
        
        # Get project's processing capabilities from cloned template configuration
        processing_capabilities = project.processing_capabilities or {}
        
        # Automatically determine optimal processing mode based on project configuration
        processing_mode = 'enhanced'  # Default to enhanced mode
        
        # Check project template type and capabilities
        if project.template_type == 'aicc-intellidoc' and processing_capabilities.get('supports_hierarchical_processing'):
            processing_mode = 'enhanced_hierarchical'
        elif processing_capabilities.get('supports_enhanced_processing'):
            processing_mode = 'enhanced'
        else:
            processing_mode = 'basic'
        
        # Allow override from parameter
        if processing_mode_override:
            processing_mode = processing_mode_override
        
        logger.info(f"🎯 CONSOLIDATED: Selected processing mode: {processing_mode}")
        logger.info(f"📊 CONSOLIDATED: Project capabilities: {list(processing_capabilities.keys())}")
        
        # Check document readiness
        ready_documents = project.documents.filter(upload_status='ready')
        if ready_documents.count() == 0:
            logger.warning(f"⚠️ CONSOLIDATED: No documents ready for processing in project {project_id}")
            return Response({
                'status': 'no_documents',
                'message': 'No documents ready for processing',
                'debug_info': {
                    'total_documents': project.documents.count(),
                    'ready_documents': ready_documents.count(),
                    'project_id': str(project.project_id),
                    'project_name': project.name
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Synchronous pre-flight: if all ready docs are already COMPLETED, skip thread
        # UNLESS summaries are requested and some documents are missing summaries.
        from users.models import DocumentVectorStatus, VectorProcessingStatus as VPS, ProjectDocumentSummary
        completed_doc_ids = DocumentVectorStatus.objects.filter(
            document__in=ready_documents,
            status=VPS.COMPLETED,
        ).values_list('document_id', flat=True)
        new_docs_count = ready_documents.exclude(id__in=completed_doc_ids).count()

        enable_summary = (llm_config or {}).get('enable_summary', False)
        needs_summaries = False
        if new_docs_count == 0 and enable_summary:
            # Check if any ready documents are missing summaries
            docs_with_summaries = ProjectDocumentSummary.objects.filter(
                document__in=ready_documents,
            ).exclude(long_summary='').exclude(short_summary='').count()
            needs_summaries = docs_with_summaries < ready_documents.count()
            if needs_summaries:
                logger.info(
                    f"📝 CONSOLIDATED: All docs vectorized but {ready_documents.count() - docs_with_summaries} "
                    f"missing summaries — proceeding to generate them."
                )

        if new_docs_count == 0 and not needs_summaries:
            logger.info(
                f"✅ CONSOLIDATED: All {ready_documents.count()} documents already processed "
                f"for project {project_id}. Nothing to do."
            )
            return Response({
                'success': True,
                'status': 'all_already_processed',
                'message': 'All documents are already processed. Upload new files to process them.',
                'project_id': str(project_id),
                'ready_documents': ready_documents.count(),
                'new_documents': 0,
                'skipped_documents': ready_documents.count(),
            }, status=status.HTTP_200_OK)

        # Use provided LLM config or defaults
        if not llm_config:
            llm_config = {
                'llm_provider': 'openai',
                'llm_model': 'gpt-5.3-chat-latest',
                'enable_summary': True
            }
            logger.info(f"📋 CONSOLIDATED: Using default LLM config")
        
        logger.info(f"📋 CONSOLIDATED: LLM Config - Provider: {llm_config.get('llm_provider')}, Model: {llm_config.get('llm_model')}, Enable Summary: {llm_config.get('enable_summary')}")
        
        # Run processing in background thread so request returns immediately and multiple projects can run in parallel
        processing_thread = threading.Thread(
            target=run_processing_in_background,
            args=(str(project.project_id), processing_mode),
            kwargs={'llm_config': llm_config},
            daemon=True,
        )
        processing_thread.start()
        PROCESSING_THREADS[project_id] = processing_thread
        logger.info(f"📦 PROJECT ISOLATION: Started background processing for project {project_id} (Total active threads: {len(PROCESSING_THREADS)})")
        
        time.sleep(0.3)  # Brief delay so thread is registered before client may poll status
        
        # Return immediately so frontend can poll vector-status for progress
        enhanced_result = {
            'success': True,
            'status': 'started',
            'message': 'Document processing started in background. Poll vector-status for progress.',
            'project_id': str(project_id),
            'project_name': project.name,
            'template_type': project.template_type,
            'template_name': project.template_name,
            'processing_mode': processing_mode,
            'processing_capabilities': processing_capabilities,
            'consolidated_features': {
                'intelligent_mode_selection': True,
                'template_aware_processing': True,
                'enhanced_hierarchical_support': processing_mode == 'enhanced_hierarchical',
                'content_preservation': True,
                'category_filtering': processing_capabilities.get('category_filtered_search', False),
                'advanced_search': processing_capabilities.get('multi_filter_search', False),
                'background_processing': True,
            },
            'user_email': request.user.email if hasattr(request, 'user') and request.user else 'unknown',
            'ready_documents': ready_documents.count(),
            'total_documents': project.documents.count(),
        }
        return Response(enhanced_result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Processing failed for project {project_id}: {e}")
        return Response({
            'status': 'error',
            'message': str(e),
            'project_id': project_id,
            'processing_mode': 'consolidated',
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_unified_consolidated(request, project_id):
    """
    CONSOLIDATED SEARCH ENDPOINT - Phase 2
    
    Combines all search capabilities into a single, intelligent endpoint
    """
    try:
        # Verify project exists and user has access
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get search parameters
        query = request.data.get('query', '').strip()
        limit = request.data.get('limit', 5)
        filters = request.data.get('filters', {})
        search_type = request.data.get('search_type', 'basic')
        
        logger.info(f"🔍 CONSOLIDATED: Search request for project {project.name}: '{query}'")
        
        # Get project's search capabilities
        processing_capabilities = project.processing_capabilities or {}
        
        # Automatically determine optimal search mode
        if processing_capabilities.get('hierarchical_search'):
            search_mode = 'hierarchical'
        elif processing_capabilities.get('category_filtered_search'):
            search_mode = 'category_filtered'
        else:
            search_mode = 'basic'
        
        # Allow override from request
        if search_type != 'basic':
            search_mode = search_type
        
        logger.info(f"🎯 CONSOLIDATED: Selected search mode: {search_mode}")
        
        # Use the enhanced search manager
        try:
            # Try enhanced hierarchical search first
            from .enhanced_hierarchical_services import EnhancedHierarchicalSearchAPI
            search_api = EnhancedHierarchicalSearchAPI()
            
            results = search_api.search_documents(
                project_id=str(project.project_id),
                query=query,
                limit=limit,
                filters=filters,
                search_level='chunk',
                group_by_document=True
            )
            
            search_results = {
                'results': results,
                'search_mode': search_mode,
                'query': query,
                'total_results': len(results),
                'project_id': project_id,
                'project_name': project.name,
                'capabilities': processing_capabilities,
                'search_features': {
                    'hierarchical_search': search_mode == 'hierarchical',
                    'category_filtering': processing_capabilities.get('category_filtered_search', False),
                    'content_reconstruction': processing_capabilities.get('full_document_rebuild', False),
                    'advanced_filtering': len(filters) > 0
                }
            }
            
        except Exception as search_error:
            logger.warning(f"⚠️ CONSOLIDATED: Enhanced search failed, falling back to basic: {search_error}")
            
            # Fallback to basic search
            search_results = {
                'results': [],
                'search_mode': 'basic_fallback',
                'query': query,
                'total_results': 0,
                'project_id': project_id,
                'project_name': project.name,
                'error': str(search_error),
                'message': 'Enhanced search failed, basic search not yet implemented'
            }
        
        return Response(search_results, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Search failed for project {project_id}: {e}")
        return Response({
            'error': str(e),
            'query': query,
            'project_id': project_id,
            'search_mode': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_project_capabilities_consolidated(request, project_id):
    """
    CONSOLIDATED CAPABILITIES ENDPOINT - Phase 2
    
    Returns comprehensive project capabilities for frontend decision making
    """
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get processing capabilities from cloned template configuration
        processing_capabilities = project.processing_capabilities or {}
        
        # Build comprehensive capabilities response
        capabilities = {
            'project_id': project_id,
            'project_name': project.name,
            'template_type': project.template_type,
            'template_name': project.template_name,
            'processing': {
                'supports_hierarchical_processing': processing_capabilities.get('supports_hierarchical_processing', False),
                'supports_enhanced_processing': processing_capabilities.get('supports_enhanced_processing', True),
                'supports_chunking': processing_capabilities.get('supports_chunking', True),
                'processing_mode': 'enhanced_hierarchical' if processing_capabilities.get('supports_hierarchical_processing') else 'enhanced',
                'max_chunk_size': processing_capabilities.get('max_chunk_size', 35000),
                'content_preservation': 'complete'
            },
            'search': {
                'hierarchical_search': processing_capabilities.get('hierarchical_search', False),
                'category_filtered_search': processing_capabilities.get('category_filtered_search', False),
                'multi_filter_search': processing_capabilities.get('multi_filter_search', False),
                'full_document_rebuild': processing_capabilities.get('full_document_rebuild', False),
                'advanced_search': processing_capabilities.get('multi_filter_search', False)
            },
            'ui': {
                'has_navigation': project.has_navigation,
                'total_pages': project.total_pages,
                'navigation_pages': project.navigation_pages or [],
                'supports_multi_page': project.has_navigation and project.total_pages > 1
            },
            'metadata': {
                'created_at': project.created_at.isoformat(),
                'created_by': project.created_by.email,
                'last_updated': project.updated_at.isoformat() if hasattr(project, 'updated_at') else None,
                'document_count': project.documents.count(),
                'ready_documents': project.documents.filter(upload_status='ready').count()
            }
        }
        
        return Response(capabilities, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Failed to get capabilities for project {project_id}: {e}")
        return Response({
            'error': str(e),
            'project_id': project_id,
            'capabilities': {
                'processing': {'supports_enhanced_processing': True},
                'search': {'hierarchical_search': False}
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vector_status_consolidated(request, project_id):
    """
    CONSOLIDATED STATUS ENDPOINT - Phase 2
    
    Returns comprehensive project status information
    """
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        # Enforce project access (legacy path is not behind ViewSet get_object())
        if not project.has_user_access(request.user):
            return Response(
                {'error': 'You do not have permission to access this project'},
                status=status.HTTP_403_FORBIDDEN
            )
        logger.debug(f"📊 CONSOLIDATED: Getting status for project {project_id} ({project.name})")
        
        # Use lightweight ORM-only status (no processor / Milvus init on every poll)
        status_data = EnhancedVectorSearchManager.get_processing_status_lightweight(project_id)
        
        # Format comprehensive status response
        vector_count = status_data.get('processing_progress', {}).get('completed', 0)
        total_documents = status_data.get('total_documents', 0)
        ready_documents = project.documents.filter(upload_status='ready').count()
        
        # Normalize status to lowercase for frontend compatibility
        raw_status = status_data.get('collection_status', 'NOT_CREATED')
        if isinstance(raw_status, str):
            normalized_status = raw_status.lower()
        else:
            normalized_status = str(raw_status).lower() if raw_status else 'not_created'
        
        # Map common status values
        status_mapping = {
            'completed': 'completed',
            'processing': 'processing',
            'pending': 'pending',
            'failed': 'failed',
            'not_created': 'not_created',
            'error': 'error',
            'unknown': 'unknown'
        }
        normalized_status = status_mapping.get(normalized_status, normalized_status)

        # Defensive guardrail: avoid contradictory "completed" when progress is incomplete.
        if normalized_status == 'completed' and total_documents > 0 and vector_count < total_documents:
            normalized_status = 'processing' if bool(status_data.get('is_processing', False)) else 'pending'
        
        logger.debug(f"📊 CONSOLIDATED: Normalized status '{raw_status}' -> '{normalized_status}' for project {project_id}")
        
        terminal_statuses = {'completed', 'failed', 'error'}
        raw_is_processing = bool(status_data.get('is_processing', False))
        is_terminal_status = normalized_status in terminal_statuses
        is_count_complete = total_documents > 0 and vector_count >= total_documents
        effective_is_processing = raw_is_processing and not is_terminal_status and not is_count_complete

        # Check PROCESSING_CONTROL for real-time thread status
        control_status = PROCESSING_CONTROL.get(str(project_id), {}).get('status', '')
        if control_status == 'COMPLETED' and normalized_status == 'processing':
            # Background thread completed but DB status is stale — fix it
            normalized_status = 'completed'
            effective_is_processing = False
        elif control_status == 'PROCESSING':
            effective_is_processing = True
            normalized_status = 'processing'

        # Add summary progress info
        from users.models import ProjectDocumentSummary
        summaries_count = ProjectDocumentSummary.objects.filter(
            document__project=project
        ).exclude(long_summary='').exclude(short_summary='').count()

        consolidated_status = {
            'project_id': project_id,
            'project_name': project.name,
            'vector_status': {
                'has_vectors': vector_count > 0,
                'vector_count': vector_count,
                'total_documents': total_documents,
                'ready_documents': ready_documents,
                'collection_status': normalized_status,
                'processing_status': normalized_status,
                'is_processing': effective_is_processing,
                'summaries_generated': summaries_count,
            },
            'processing_capabilities': project.processing_capabilities or {},
            'template_info': {
                'template_type': project.template_type,
                'template_name': project.template_name,
                'supports_hierarchical': project.processing_capabilities.get('supports_hierarchical_processing', False)
            },
            'last_updated': status_data.get('last_processed_at'),
            'status_timestamp': timezone.now().isoformat()
        }
        
        return Response(consolidated_status, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Failed to get status for project {project_id}: {e}")
        logger.exception(e)  # Log full exception traceback
        return Response({
            'project_id': project_id,
            'vector_status': {
                'has_vectors': False,
                'vector_count': 0,
                'total_documents': 0,
                'ready_documents': 0,
                'collection_status': 'error',  # Normalize to lowercase
                'processing_status': 'error',  # Normalize to lowercase
                'is_processing': False
            },
            'error': str(e)
        }, status=status.HTTP_200_OK)  # Return 200 so frontend doesn't break

# Additional consolidated endpoints...
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_processing_consolidated(request, project_id):
    """Start processing with consolidated background processing"""
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Check if processing is already running
        if project_id in PROCESSING_THREADS and PROCESSING_THREADS[project_id].is_alive():
            return Response({
                'success': False,
                'error': 'Processing already in progress',
                'message': 'Processing is already running for this project'
            }, status=status.HTTP_409_CONFLICT)
        
        # Determine processing mode based on project capabilities
        processing_capabilities = project.processing_capabilities or {}
        processing_mode = 'enhanced_hierarchical' if processing_capabilities.get('supports_hierarchical_processing') else 'enhanced'
        
        # Extract LLM config from request (same pattern as process_unified_consolidated)
        llm_config = {
            'llm_provider': request.data.get('llm_provider', 'openai'),
            'llm_model': request.data.get('llm_model', 'gpt-5.3-chat-latest'),
            'enable_summary': request.data.get('enable_summary', True),
        }
        
        logger.info(f"🚀 CONSOLIDATED: Starting background processing for project {project_id} with mode {processing_mode}")
        logger.info(f"📋 CONSOLIDATED: LLM Config - Provider: {llm_config['llm_provider']}, Model: {llm_config['llm_model']}")
        
        # Start processing in background thread
        processing_thread = threading.Thread(
            target=run_processing_in_background,
            args=(project_id, processing_mode),
            kwargs={'llm_config': llm_config},
            daemon=True
        )
        processing_thread.start()
        
        # Store thread reference
        PROCESSING_THREADS[project_id] = processing_thread
        
        # Give a small delay to let processing start
        time.sleep(0.5)
        
        return Response({
            'success': True,
            'data': {
                'project_id': project_id,
                'project_name': project.name,
                'status': 'started',
                'processing_mode': processing_mode,
                'llm_model': llm_config['llm_model'],
                'message': f"Consolidated processing started in background with {processing_mode} mode"
            },
            'message': 'Consolidated processing started successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Error starting processing for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to start consolidated processing'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_processing_consolidated(request, project_id):
    """Stop processing with consolidated cleanup"""
    try:
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        logger.info(f"🛑 CONSOLIDATED: Stopping processing for project {project_id}")
        
        # Stop processing
        result = EnhancedVectorSearchManager.stop_project_processing(project_id)
        
        # Clean up thread reference if exists
        if project_id in PROCESSING_THREADS:
            thread = PROCESSING_THREADS[project_id]
            if thread.is_alive():
                logger.info(f"🔄 CONSOLIDATED: Background thread for project {project_id} will terminate gracefully")
            del PROCESSING_THREADS[project_id]
        
        return Response({
            'success': result.get('success', True),
            'data': {
                **result,
                'project_id': project_id,
                'project_name': project.name,
                'stopped_at': timezone.now().isoformat()
            },
            'message': result.get('message', 'Consolidated processing stopped'),
            'processing_mode': 'consolidated'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ CONSOLIDATED: Error stopping processing for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to stop consolidated processing'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
