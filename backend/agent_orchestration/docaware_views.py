"""
DocAware API Views
=================

API endpoints for DocAware agent configuration and search methods.
"""

import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from users.models import IntelliDocProject
from .docaware import DocAwareSearchMethods, SearchMethod, EnhancedDocAwareAgentService

logger = logging.getLogger(__name__)

class DocAwareConfigViewSet(viewsets.ViewSet):
    """
    ViewSet for DocAware agent configuration
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def search_methods(self, request):
        """
        Get available search methods and their configurations
        """
        try:
            logger.info("📚 DOCAWARE API: search_methods endpoint called")
            print("🔍 DEBUG: DocAware search_methods endpoint hit!")  # Console debug
            print(f"🔍 DEBUG: Request method: {request.method}")
            print(f"🔍 DEBUG: Request path: {request.path}")
            print(f"🔍 DEBUG: Request user: {request.user}")
            
            print("🔍 DEBUG: Importing DocAwareSearchMethods...")
            methods = DocAwareSearchMethods.get_all_methods()
            print(f"🔍 DEBUG: Raw methods from backend: {list(methods.keys())}")
            
            # Format for frontend consumption
            formatted_methods = []
            for method, config in methods.items():
                print(f"🔍 DEBUG: Processing method {method} -> {config.name}")
                formatted_methods.append({
                    'id': method.value,
                    'name': config.name,
                    'description': config.description,
                    'parameters': config.parameters,
                    'default_values': config.default_values,
                    'requires_embedding': config.requires_embedding
                })
            
            logger.info(f"📚 DOCAWARE API: Returning {len(formatted_methods)} search methods")
            print(f"🔍 DEBUG: Returning {len(formatted_methods)} methods: {[m['name'] for m in formatted_methods]}")
            print(f"🔍 DEBUG: First method details: {formatted_methods[0] if formatted_methods else 'None'}")
            
            response_data = {
                'methods': formatted_methods,
                'count': len(formatted_methods)
            }
            print(f"🔍 DEBUG: Final response data: {response_data}")
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Failed to get search methods: {e}")
            print(f"🔍 DEBUG ERROR: {e}")
            return Response(
                {'error': 'Failed to retrieve search methods'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_parameters(self, request):
        """
        Validate search method parameters
        """
        try:
            method_id = request.data.get('method')
            parameters = request.data.get('parameters', {})
            
            if not method_id:
                return Response(
                    {'error': 'Search method is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate method exists
            try:
                search_method = SearchMethod(method_id)
            except ValueError:
                return Response(
                    {'error': f'Invalid search method: {method_id}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate parameters
            validated_params = DocAwareSearchMethods.validate_parameters(
                search_method, parameters
            )
            
            return Response({
                'valid': True,
                'validated_parameters': validated_params,
                'method': method_id
            })
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Parameter validation failed: {e}")
            return Response(
                {'error': f'Parameter validation failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def test_search(self, request):
        """
        Test search functionality with given parameters
        """
        try:
            logger.info("📚 DOCAWARE API: test_search endpoint called")
            print("🔍 DEBUG: DocAware test_search endpoint hit!")  # Console debug
            print(f"🔍 DEBUG: Request method: {request.method}")
            print(f"🔍 DEBUG: Request path: {request.path}")
            print(f"🔍 DEBUG: Request user: {request.user}")
            print(f"🔍 DEBUG: Request data: {request.data}")
            
            project_id = request.data.get('project_id')
            method_id = request.data.get('method')
            parameters = request.data.get('parameters', {})
            query = request.data.get('query')  # REMOVED HARDCODED FALLBACK
            content_filters = request.data.get('content_filters', [])  # Extract content filters array

            # Validate array
            if content_filters and not isinstance(content_filters, list):
                return Response(
                    {'error': 'content_filters must be an array'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            print(f"🔍 DEBUG: Extracted - project_id: {project_id}, method: {method_id}")
            print(f"🔍 DEBUG: Extracted - query: {query}, parameters: {parameters}")
            print(f"🔍 DEBUG: Extracted - content_filters: {content_filters}")
            
            # CRITICAL: Require actual query input
            if not query or query.strip() == "":
                print("🔍 DEBUG ERROR: Empty query provided")
                return Response(
                    {'error': 'Query is required and cannot be empty. This endpoint no longer accepts hardcoded test queries.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Reject generic test queries to force real input
            rejected_queries = [
                'test query', 
                'test query for document search',
                'sample query',
                'example query',
                'test'
            ]
            
            if query.lower().strip() in rejected_queries:
                print(f"🔍 DEBUG ERROR: Rejected generic test query: {query}")
                return Response(
                    {
                        'error': f'Generic test query "{query}" not allowed. Please provide a meaningful query from agent execution.',
                        'suggestion': 'Use queries like: "quarterly sales analysis", "project risk assessment", "customer feedback insights"'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"🔍 DOCAWARE: Processing real query: '{query[:100]}...'")
            print(f"🔍 DEBUG: Validated real query: {query[:50]}...")
            
            if not project_id:
                print("🔍 DEBUG ERROR: Missing project_id")
                return Response(
                    {'error': 'Project ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not method_id:
                print("🔍 DEBUG ERROR: Missing method_id")
                return Response(
                    {'error': 'Search method is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            print(f"🔍 DEBUG: Looking up project {project_id}...")
            # Verify project access
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            print(f"🔍 DEBUG: Found project: {project.name} (owner: {project.created_by})")
            
            if not project.has_user_access(request.user):
                print(f"🔍 DEBUG ERROR: Access denied - project owner: {project.created_by}, request user: {request.user}")
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            print(f"🔍 DEBUG: Validating search method {method_id}...")
            # Validate method
            try:
                search_method = SearchMethod(method_id)
                print(f"🔍 DEBUG: Valid search method: {search_method}")
            except ValueError as ve:
                print(f"🔍 DEBUG ERROR: Invalid search method {method_id}: {ve}")
                return Response(
                    {'error': f'Invalid search method: {method_id}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            print(f"🔍 DEBUG: Initializing DocAware service for project {project_id}...")
            # Initialize DocAware service
            try:
                docaware_service = EnhancedDocAwareAgentService(project_id)
                print(f"🔍 DEBUG: DocAware service initialized successfully")
            except Exception as init_error:
                print(f"🔍 DEBUG ERROR: Failed to initialize DocAware service: {init_error}")
                raise init_error
            
            print(f"🔍 DEBUG: Performing search with method {search_method}, query: '{query}'")
            print(f"🔍 DEBUG: Search parameters: {parameters}")
            
            # Perform test search
            try:
                search_results = docaware_service.search_documents(
                    query=query,
                    search_method=search_method,
                    method_parameters=parameters,
                    content_filters=content_filters
                )
                print(f"🔍 DEBUG: Search completed! Found {len(search_results)} results")
            except Exception as search_error:
                print(f"🔍 DEBUG ERROR: Search failed: {search_error}")
                import traceback
                print(f"🔍 DEBUG ERROR: Search traceback: {traceback.format_exc()}")
                raise search_error
            
            # Get search_limit from parameters (default to 10 if not provided)
            search_limit = parameters.get('search_limit', 10)
            print(f"🔍 DEBUG: Using search_limit: {search_limit}")
            
            # Format results for response - use search_limit instead of hardcoded 3
            formatted_results = []
            for i, result in enumerate(search_results[:search_limit]):
                print(f"🔍 DEBUG: Processing result {i+1}: {type(result)}")
                try:
                    content = result['content']
                    formatted_results.append({
                        'content': content,  # Full content for display
                        'content_preview': content[:200] + "..." if len(content) > 200 else content,  # Preview for header
                        'score': result['metadata'].get('score', 0),
                        'source': result['metadata'].get('source', 'Unknown'),
                        'page': result['metadata'].get('page'),
                        'search_method': result['metadata'].get('search_method', method_id)
                    })
                except Exception as format_error:
                    print(f"🔍 DEBUG ERROR: Failed to format result {i+1}: {format_error}")
                    print(f"🔍 DEBUG: Raw result data: {result}")
            
            response_data = {
                'success': True,
                'query': query,
                'method': method_id,
                'results_count': len(search_results),
                'search_limit_used': search_limit,
                'results_returned': len(formatted_results),
                'sample_results': formatted_results,
                'parameters_used': parameters,
                'content_filters_used': content_filters,
                'note': f'Showing {len(formatted_results)} results (search_limit: {search_limit})'
            }
            
            print(f"🔍 DEBUG: Final response: success={response_data['success']}, count={response_data['results_count']}")
            logger.info(f"📚 DOCAWARE API: Test search completed successfully - {len(search_results)} results")
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Test search failed: {e}")
            return Response(
                {'error': f'Search test failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def collections(self, request):
        """
        Get available collections for a project
        """
        try:
            project_id = request.query_params.get('project_id')
            
            if not project_id:
                return Response(
                    {'error': 'Project ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify project access
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Initialize DocAware service
            docaware_service = EnhancedDocAwareAgentService(project_id)
            
            # Get available collections
            collections = docaware_service.get_available_collections()
            
            return Response({
                'project_id': project_id,
                'collections': collections,
                'count': len(collections)
            })
            
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Failed to get collections: {e}")
            return Response(
                {'error': 'Failed to retrieve collections'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def hierarchical_paths(self, request):
        """
        Get hierarchical paths for content filtering
        Returns folder tree structure with files and folders
        """
        try:
            project_id = request.query_params.get('project_id')
            include_files = request.query_params.get('include_files', 'true').lower() == 'true'

            print(f"🔍 DEBUG HIERARCHICAL PATHS: Called with project_id={project_id}, include_files={include_files}")
            print(f"🔍 DEBUG HIERARCHICAL PATHS: Request method: {request.method}")
            print(f"🔍 DEBUG HIERARCHICAL PATHS: Query params: {dict(request.query_params)}")

            if not project_id:
                print("❌ DEBUG HIERARCHICAL PATHS: No project_id provided")
                return Response(
                    {'error': 'Project ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"📚 DOCAWARE API: Getting hierarchical paths for project {project_id} (include_files={include_files})")

            # Verify project access
            try:
                project = get_object_or_404(IntelliDocProject, project_id=project_id)
                print(f"✅ DEBUG HIERARCHICAL PATHS: Found project: {project.name} (owner: {project.created_by})")
            except Exception as proj_error:
                print(f"❌ DEBUG HIERARCHICAL PATHS: Project lookup failed: {proj_error}")
                raise proj_error

            # Use proper project access check that handles admins and shared projects
            if not project.has_user_access(request.user):
                print(f"❌ DEBUG HIERARCHICAL PATHS: Access denied - project owner: {project.created_by}, request user: {request.user}")
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Initialize DocAware service to get collection data
            try:
                print(f"🔧 DEBUG HIERARCHICAL PATHS: Initializing DocAware service for project {project_id}")
                docaware_service = EnhancedDocAwareAgentService(project_id)
                print(f"✅ DEBUG HIERARCHICAL PATHS: DocAware service initialized")
            except Exception as init_error:
                print(f"❌ DEBUG HIERARCHICAL PATHS: DocAware service initialization failed: {init_error}")
                raise init_error

            # Get hierarchical paths from the vector database
            try:
                print(f"📊 DEBUG HIERARCHICAL PATHS: Calling get_hierarchical_paths(include_files={include_files})")
                hierarchical_data = docaware_service.get_hierarchical_paths(include_files=include_files)
                print(f"📊 DEBUG HIERARCHICAL PATHS: Raw data from service: {len(hierarchical_data)} items")
                print(f"📊 DEBUG HIERARCHICAL PATHS: First few items: {hierarchical_data[:2] if hierarchical_data else 'None'}")
            except Exception as data_error:
                print(f"❌ DEBUG HIERARCHICAL PATHS: get_hierarchical_paths() failed: {data_error}")
                import traceback
                print(f"❌ DEBUG HIERARCHICAL PATHS: Traceback: {traceback.format_exc()}")
                raise data_error

            # Count folders and files
            folders_count = len([p for p in hierarchical_data if p.get('isFolder')])
            files_count = len([p for p in hierarchical_data if not p.get('isFolder')])

            logger.info(f"📚 DOCAWARE API: Found {folders_count} folders and {files_count} files")

            # Check document and processing status for better user feedback
            documents_count = project.documents.count()
            ready_documents_count = project.documents.filter(upload_status='ready').count()
            
            # Check vector collection status
            processing_status = None
            collection_status = None
            try:
                from users.models import ProjectVectorCollection, VectorProcessingStatus
                if hasattr(project, 'vector_collection'):
                    collection = project.vector_collection
                    collection_status = collection.status
                    processing_status = {
                        'status': collection.status,
                        'total_documents': collection.total_documents,
                        'processed_documents': collection.processed_documents,
                        'progress': collection.processing_progress if hasattr(collection, 'processing_progress') else 0
                    }
            except Exception as status_error:
                logger.debug(f"Could not get processing status: {status_error}")

            # Build per-document LLM upload status map (keyed by original_filename)
            # This is advisory metadata to help the UI show which documents are ready
            # for each provider and which are likely to fail.
            document_llm_status = {}
            try:
                from agent_orchestration.llm_file_service import LLMFileUploadService
                from project_api_keys.services import get_project_api_key_service

                llm_service = LLMFileUploadService(project)
                api_key_service = get_project_api_key_service()

                # Cache API key availability per provider (avoid repeated decrypts)
                provider_key_available = {}
                for provider_type in ['openai', 'anthropic', 'google']:
                    try:
                        key = api_key_service.get_project_api_key(project, provider_type)
                        provider_key_available[provider_type] = bool(key)
                    except Exception as key_err:
                        logger.debug(f"Could not check API key for {provider_type}: {key_err}")
                        provider_key_available[provider_type] = False

                for doc in project.documents.filter(upload_status='ready'):
                    status_entry = {}

                    for provider, field_name in [
                        ('openai', 'llm_file_id_openai'),
                        ('anthropic', 'llm_file_id_anthropic'),
                        ('google', 'llm_file_id_google'),
                    ]:
                        file_id = getattr(doc, field_name, None)
                        if file_id:
                            status_entry[provider] = {'status': 'ready'}
                            continue

                        # No file_id yet – infer potential issues without actually uploading
                        supported, support_reason = llm_service.check_provider_support(doc, provider)
                        if not supported:
                            reason_code = 'unsupported'
                            reason_text = support_reason or 'Not supported'
                            lower_reason = reason_text.lower()
                            if 'exceeds' in lower_reason and 'limit' in lower_reason:
                                reason_code = 'file_too_large'
                            elif 'not supported' in lower_reason:
                                reason_code = 'unsupported_type'

                            status_entry[provider] = {
                                'status': reason_code,
                                'reason': reason_text,
                            }
                            continue

                        # Supported by size/type – check API key presence for this provider
                        provider_key = 'google' if provider == 'google' else provider
                        if not provider_key_available.get(provider_key, False):
                            status_entry[provider] = {
                                'status': 'missing_api_key',
                                'reason': f'No API key configured for {provider}',
                            }
                        else:
                            # No obvious issues detected; will be uploaded lazily when used
                            status_entry[provider] = {'status': 'not_uploaded'}

                    document_llm_status[doc.original_filename] = status_entry

            except Exception as llm_status_error:
                logger.debug(f"Could not build LLM upload status: {llm_status_error}")

            response_data = {
                'project_id': project_id,
                'hierarchical_paths': hierarchical_data,
                'folders_count': folders_count,
                'files_count': files_count,
                'total_count': len(hierarchical_data),
                'documents_info': {
                    'total_documents': documents_count,
                    'ready_documents': ready_documents_count,
                    'collection_status': collection_status,
                    'processing_status': processing_status
                },
                'document_llm_status': document_llm_status
            }

            print(f"✅ DEBUG HIERARCHICAL PATHS: Returning response with {len(hierarchical_data)} items")
            print(f"✅ DEBUG HIERARCHICAL PATHS: Response keys: {list(response_data.keys())}")

            return Response(response_data)

        except Exception as e:
            print(f"❌ DEBUG HIERARCHICAL PATHS: Outer exception: {e}")
            import traceback
            print(f"❌ DEBUG HIERARCHICAL PATHS: Full traceback: {traceback.format_exc()}")
            logger.error(f"❌ DOCAWARE API: Failed to get hierarchical paths: {e}")
            return Response(
                {'error': f'Failed to retrieve hierarchical paths: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='uploaded_hierarchical_paths')
    def uploaded_hierarchical_paths(self, request):
        """
        Get hierarchical paths for *uploaded* (ready) project documents so the
        node-level "File Attachments" picker works immediately, even before
        Start Processing / Milvus vectorization completes.
        """
        try:
            project_id = request.query_params.get('project_id')
            include_files = request.query_params.get('include_files', 'true').lower() == 'true'
            include_llm_status = request.query_params.get('include_llm_status', 'true').lower() == 'true'

            if not project_id:
                return Response(
                    {'error': 'Project ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verify project access
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            if not project.has_user_access(request.user):
                return Response(
                    {'error': 'You do not have access to this project'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Only consider documents whose file content is ready for upload-to-provider
            docs = project.documents.filter(upload_status='ready')

            # Always use LLM-based folder organization (no rule-based fallback)
            folder_org_map = {}
            try:
                from users.models import ProjectDocumentFolderOrganization
                qs = (
                    ProjectDocumentFolderOrganization.objects
                    .filter(document__in=docs)
                    .values_list('document__document_id', 'folder_path')
                )
                folder_org_map = {str(doc_id): folder_path for doc_id, folder_path in qs}
            except Exception as e:
                logger.debug(f"Could not load LLM folder organization mapping: {e}")

            # Build folder paths + file entries from original_filename (preserves upload hierarchy)
            folder_paths = set()
            file_entries = []

            for doc in docs:
                # Normalize path separators and strip leading/trailing slashes
                original_filename = (doc.original_filename or '').replace('\\', '/').strip('/')
                if not original_filename:
                    continue

                parts = [p for p in original_filename.split('/') if p]
                if not parts:
                    continue

                file_name = parts[-1]
                # Always use LLM folder mapping; fall back to "Unclassified" if not yet processed
                folder_path = folder_org_map.get(str(doc.document_id), '')

                # Track folder itself and all parents for recursive folder checkbox UX
                if folder_path:
                    folder_paths.add(folder_path)
                    path_parts = folder_path.split('/')
                    for i in range(1, len(path_parts)):
                        folder_paths.add('/'.join(path_parts[:i]))

                file_entries.append({
                    'id': f"file_uploaded_{doc.document_id}",
                    'name': doc.original_filename,   # IMPORTANT: stored value for UI selection
                    'path': folder_path,             # folder path ('' for root)
                    'type': 'file',
                    'displayName': original_filename,
                    'isFolder': False,
                    'document_id': str(doc.document_id),
                })

            # Build folder entries (skips root "")
            folder_entries = []
            for folder_path in sorted(folder_paths):
                folder_entries.append({
                    'id': f"folder_uploaded_{folder_path}",
                    'name': folder_path.split('/')[-1],
                    'path': folder_path,
                    'type': 'folder',
                    'displayName': folder_path,
                    'isFolder': True,
                })

            hierarchical_data = folder_entries
            if include_files:
                hierarchical_data = folder_entries + file_entries

            folders_count = len(folder_entries)
            files_count = len(file_entries) if include_files else 0

            # Build per-document LLM upload status map (keyed by original_filename)
            # This matches the shape expected by NodePropertiesPanel.
            document_llm_status = {}
            if include_llm_status:
                try:
                    from agent_orchestration.llm_file_service import LLMFileUploadService
                    from project_api_keys.services import get_project_api_key_service

                    llm_service = LLMFileUploadService(project)
                    api_key_service = get_project_api_key_service()

                    provider_key_available = {}
                    for provider_type in ['openai', 'anthropic', 'google']:
                        try:
                            key = api_key_service.get_project_api_key(project, provider_type)
                            provider_key_available[provider_type] = bool(key)
                        except Exception as key_err:
                            logger.debug(f"Could not check API key for {provider_type}: {key_err}")
                            provider_key_available[provider_type] = False

                    for doc in docs:
                        status_entry = {}
                        for provider, field_name in [
                            ('openai', 'llm_file_id_openai'),
                            ('anthropic', 'llm_file_id_anthropic'),
                            ('google', 'llm_file_id_google'),
                        ]:
                            file_id = getattr(doc, field_name, None)
                            if file_id:
                                status_entry[provider] = {'status': 'ready'}
                                continue

                            supported, support_reason = llm_service.check_provider_support(doc, provider)
                            if not supported:
                                reason_code = 'unsupported'
                                reason_text = support_reason or 'Not supported'
                                lower_reason = reason_text.lower()
                                if 'exceeds' in lower_reason and 'limit' in lower_reason:
                                    reason_code = 'file_too_large'
                                elif 'not supported' in lower_reason:
                                    reason_code = 'unsupported_type'

                                status_entry[provider] = {
                                    'status': reason_code,
                                    'reason': reason_text,
                                }
                                continue

                            provider_key = 'google' if provider == 'google' else provider
                            if not provider_key_available.get(provider_key, False):
                                status_entry[provider] = {
                                    'status': 'missing_api_key',
                                    'reason': f'No API key configured for {provider}',
                                }
                            else:
                                status_entry[provider] = {'status': 'not_uploaded'}

                        document_llm_status[doc.original_filename] = status_entry
                except Exception as llm_status_error:
                    logger.debug(f"Could not build LLM upload status: {llm_status_error}")

            return Response({
                'project_id': project_id,
                'hierarchical_paths': hierarchical_data,
                'folders_count': folders_count,
                'files_count': files_count,
                'total_count': len(hierarchical_data),
                'documents_info': {
                    'total_documents': project.documents.count(),
                    'ready_documents': docs.count(),
                },
                'document_llm_status': document_llm_status
            })
        except Exception as e:
            logger.error(f"❌ DOCAWARE API: Failed to get uploaded hierarchical paths: {e}", exc_info=True)
            return Response(
                {'error': f'Failed to retrieve uploaded hierarchical paths: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
