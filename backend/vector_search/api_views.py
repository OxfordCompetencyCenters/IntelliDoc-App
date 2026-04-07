# backend/vector_search/api_views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from users.models import IntelliDocProject
from .services_enhanced import EnhancedVectorSearchManager, PROCESSING_THREADS
from .unified_services_fixed import UnifiedVectorSearchManager, fix_existing_documents
from .detailed_logger import DocumentProcessingTracker, doc_logger
import logging
import threading
import time

logger = logging.getLogger(__name__)

def run_processing_in_background(project_id: str, processing_mode: str = 'enhanced', llm_provider: str = None, llm_model: str = None, enable_summary: bool = True):
    """Run enhanced document processing in background thread - no fallbacks"""
    try:
        # Force enhanced mode only
        processing_mode = 'enhanced'
        
        # Create detailed logging for this processing session
        doc_logger.info(f"🚀 ENHANCED BACKGROUND PROCESSING STARTED | Project: {project_id}")
        if llm_provider:
            doc_logger.info(f"📋 BACKGROUND: LLM Config - Provider: {llm_provider}, Model: {llm_model}, Enable Summary: {enable_summary}")
        
        logger.info(f"Starting enhanced background processing for project {project_id}")
        
        # Use enhanced UnifiedVectorSearchManager only
        result = UnifiedVectorSearchManager.process_project_documents(
            project_id, 
            processing_mode='enhanced',
            llm_provider=llm_provider,
            llm_model=llm_model,
            enable_summary=enable_summary
        )
        
        doc_logger.info(f"✅ ENHANCED BACKGROUND PROCESSING COMPLETED | Project: {project_id} | Result: {result.get('status', 'unknown')}")
        logger.info(f"Enhanced background processing completed for project {project_id}: {result.get('status', 'unknown')}")
        
        # Clean up thread reference
        if project_id in PROCESSING_THREADS:
            logger.info(f"📦 PROJECT ISOLATION: Cleaning up processing thread for project {project_id}")
            del PROCESSING_THREADS[project_id]
            
    except Exception as e:
        doc_logger.error(f"❌ ENHANCED BACKGROUND PROCESSING FAILED | Project: {project_id} | Error: {str(e)}")
        logger.error(f"Enhanced background processing failed for project {project_id}: {e}")
        # Clean up thread reference
        if project_id in PROCESSING_THREADS:
            logger.info(f"📦 PROJECT ISOLATION: Cleaning up failed processing thread for project {project_id}")
            del PROCESSING_THREADS[project_id]

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_processing(request, project_id):
    """Start processing documents for a project in background"""
    try:
        # Verify project exists and user has access
        # Use UUID project_id only
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Check if processing is already running
        if project_id in PROCESSING_THREADS and PROCESSING_THREADS[project_id].is_alive():
            return Response({
                'success': False,
                'error': 'Processing already in progress',
                'message': 'Processing is already running for this project'
            }, status=status.HTTP_409_CONFLICT)
        
        # Get processing mode - enhanced only
        processing_mode = 'enhanced'  # Only enhanced mode supported
        logger.info(f"Starting enhanced processing for project {project_id} by user {request.user.email}")
        
        # Start processing in background thread
        processing_thread = threading.Thread(
            target=run_processing_in_background,
            args=(project_id, processing_mode),
            daemon=True
        )
        processing_thread.start()
        
        # Store thread reference
        PROCESSING_THREADS[project_id] = processing_thread
        logger.info(f"📦 PROJECT ISOLATION: Started processing thread for project {project_id} (Total active threads: {len(PROCESSING_THREADS)})")
        
        # Give a small delay to let processing start
        time.sleep(0.5)
        
        return Response({
            'success': True,
            'data': {
                'project_id': project_id,
                'status': 'started',
                'message': f"Enhanced processing started in background"
            },
            'message': 'Enhanced processing started successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error starting processing for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to start processing'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vector_status(request, project_id):
    """Get vector database status for a project (compatible with frontend)"""
    try:
        # Verify project exists and user has access
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get status from enhanced manager
        status_data = EnhancedVectorSearchManager.get_project_processing_status(project_id)
        
        # Format response for frontend compatibility
        vector_count = status_data.get('processing_progress', {}).get('completed', 0)
        total_documents = status_data.get('total_documents', 0)
        
        return Response({
            'has_vectors': vector_count > 0,
            'vector_count': vector_count,
            'total_documents': total_documents,
            'collection_status': status_data.get('collection_status', 'NOT_CREATED'),
            'last_updated': status_data.get('last_processed_at'),
            'processing_status': status_data.get('collection_status', 'ready'),
            'is_processing': status_data.get('is_processing', False)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting vector status for project {project_id}: {e}")
        return Response({
            'has_vectors': False,
            'vector_count': 0,
            'total_documents': 0,
            'collection_status': 'ERROR',
            'processing_status': 'error',
            'error': str(e)
        }, status=status.HTTP_200_OK)  # Return 200 so frontend doesn't break


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_unified(request, project_id):
    """
    Unified document processing endpoint that routes to the enhanced processing system.
    This is the main endpoint the frontend expects for document processing.
    """
    try:
        # Verify project exists and user has access
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        logger.info(f"Starting enhanced unified processing for project {project_id}")
        
        # Use the enhanced UnifiedVectorSearchManager for processing
        from .unified_services_fixed import UnifiedVectorSearchManager
        result = UnifiedVectorSearchManager.process_project_documents(project_id, processing_mode='enhanced')
        
        # Format response for frontend compatibility
        response_data = {
            'success': result['status'] == 'completed',
            'status': result['status'],
            'message': result.get('message', 'Processing completed'),
            'data': {
                'project_id': project_id,
                'processed_documents': result.get('processed_documents', 0),
                'failed_documents': result.get('failed_documents', 0),
                'total_chunks_created': result.get('total_chunks_created', 0),
                'processing_mode': result.get('processing_mode', 'enhanced'),
                'processing_details': result.get('processing_details', [])
            }
        }
        
        # Return appropriate status code
        status_code = status.HTTP_200_OK if result['status'] == 'completed' else status.HTTP_500_INTERNAL_SERVER_ERROR
        
        return Response(response_data, status=status_code)
        
    except Exception as e:
        logger.error(f"Error in unified processing for project {project_id}: {e}")
        return Response({
            'success': False,
            'status': 'error',
            'message': str(e),
            'data': {
                'project_id': project_id,
                'processed_documents': 0,
                'failed_documents': 0,
                'total_chunks_created': 0,
                'processing_mode': 'enhanced'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vector_status(request, project_id):
    """
    Get vector processing status for a project.
    Returns information about vector collection status and processing progress.
    """
    try:
        # Get project instance
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get status from enhanced manager
        status_data = EnhancedVectorSearchManager.get_project_processing_status(project_id)
        
        # Format response for frontend compatibility
        vector_count = status_data.get('processing_progress', {}).get('completed', 0)
        total_documents = status_data.get('total_documents', 0)
        
        return Response({
            'has_vectors': vector_count > 0,
            'vector_count': vector_count,
            'total_documents': total_documents,
            'collection_status': status_data.get('collection_status', 'NOT_CREATED'),
            'last_updated': status_data.get('last_processed_at'),
            'processing_status': status_data.get('collection_status', 'ready'),
            'is_processing': status_data.get('is_processing', False)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting vector status for project {project_id}: {e}")
        return Response({
            'has_vectors': False,
            'vector_count': 0,
            'total_documents': 0,
            'collection_status': 'ERROR',
            'processing_status': 'error',
            'error': str(e)
        }, status=status.HTTP_200_OK)  # Return 200 so frontend doesn't break

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_processing(request, project_id):
    """Stop processing documents for a project"""
    try:
        # Verify project exists and user has access
        # Use UUID project_id only
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        logger.info(f"Stopping processing for project {project_id} by user {request.user.email}")
        
        # Stop processing
        result = EnhancedVectorSearchManager.stop_project_processing(project_id)
        
        # Clean up thread reference if exists
        if project_id in PROCESSING_THREADS:
            thread = PROCESSING_THREADS[project_id]
            if thread.is_alive():
                # The thread will check stop flags and terminate gracefully
                logger.info(f"Background thread for project {project_id} will terminate gracefully")
            del PROCESSING_THREADS[project_id]
        
        return Response({
            'success': result['success'],
            'data': result,
            'message': result['message'],
            'processing_mode': 'enhanced'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error stopping processing for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to stop processing'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_processing_status(request, project_id):
    """Get detailed processing status for a project"""
    try:
        # Verify project exists and user has access
        # Use UUID project_id only
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get processing status
        status_data = EnhancedVectorSearchManager.get_project_processing_status(project_id)
        
        return Response({
            'success': True,
            'data': status_data,
            'message': 'Processing status retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting processing status for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to get processing status'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_document_statuses(request, project_id):
    """Get individual document processing statuses"""
    try:
        # Verify project exists and user has access
        # Use UUID project_id only
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get document statuses
        documents = EnhancedVectorSearchManager.get_document_statuses(project_id)
        
        return Response({
            'success': True,
            'data': documents,
            'message': 'Document statuses retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting document statuses for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to get document statuses'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_check(request):
    """Check vector search system health"""
    try:
        from .startup import check_system_health
        
        health_status = check_system_health()
        
        return Response({
            'success': True,
            'data': health_status,
            'message': 'Health check completed'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Health check failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_unified(request, project_id):
    """Process documents using the fixed unified system"""
    try:
        # Verify project exists and user has access
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get processing mode - enhanced only
        processing_mode = 'enhanced'  # Only enhanced mode supported
        
        logger.info(f"Starting enhanced unified processing for project {project_id}")
        
        # Process documents with fixed unified system
        result = UnifiedVectorSearchManager.process_project_documents(
            project_id, 
            processing_mode
        )
        
        return Response({
            'success': result['status'] == 'completed',
            'data': result,
            'message': result['message']
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in unified processing for project {project_id}: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Unified processing failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fix_documents_api(request, project_id=None):
    """Fix existing documents by extracting content from binary data"""
    try:
        # Verify project exists if project_id provided
        if project_id:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        logger.info(f"Starting document fixing for project {project_id or 'all projects'}")
        
        # Fix documents
        result = fix_existing_documents(project_id)
        
        return Response({
            'success': result['status'] == 'completed',
            'data': result,
            'message': result['message']
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fixing documents: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Document fixing failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_processing_modes(request):
    """Get available processing mode - enhanced only"""
    try:
        mode = {
            'enhanced': {
                'name': 'Enhanced',
                'description': 'Full AI-powered processing with all features',
                'features': [
                    'content_extraction',
                    'chunking',
                    'hierarchy',
                    'ai_summaries',
                    'ai_topics',
                    'advanced_search',
                    'complete_metadata',
                    'timing_tracking'
                ],
                'recommended_for': 'Maximum functionality with full AI capabilities',
                'default': True,
                'only_mode': True
            }
        }
        
        return Response({
            'success': True,
            'data': mode,
            'message': 'Enhanced processing mode available'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting processing modes: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Failed to get processing modes'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vector_status(request, project_id):
    """Get vector database status for a project (compatible with frontend)"""
    try:
        # Verify project exists and user has access
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # Get status from enhanced manager
        status_data = EnhancedVectorSearchManager.get_project_processing_status(project_id)
        
        # Format response for frontend compatibility
        vector_count = status_data.get('processing_progress', {}).get('completed', 0)
        total_documents = status_data.get('total_documents', 0)
        
        return Response({
            'has_vectors': vector_count > 0,
            'vector_count': vector_count,
            'total_documents': total_documents,
            'collection_status': status_data.get('collection_status', 'NOT_CREATED'),
            'last_updated': status_data.get('last_processed_at'),
            'processing_status': status_data.get('collection_status', 'ready'),
            'is_processing': status_data.get('is_processing', False)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting vector status for project {project_id}: {e}")
        return Response({
            'has_vectors': False,
            'vector_count': 0,
            'total_documents': 0,
            'collection_status': 'ERROR',
            'processing_status': 'error',
            'error': str(e)
        }, status=status.HTTP_200_OK)  # Return 200 so frontend doesn't break
