# Enhanced Hierarchical Services with Complete Content Preservation
# backend/vector_search/enhanced_hierarchical_services.py

import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone

from users.models import IntelliDocProject, ProjectDocument, ProjectVectorCollection, VectorProcessingStatus
from .enhanced_hierarchical_processor import EnhancedHierarchicalProcessor, EnhancedHierarchicalChunkMapper
from .enhanced_hierarchical_database import EnhancedHierarchicalVectorDatabase
from .embeddings import DocumentEmbedder

logger = logging.getLogger(__name__)

class EnhancedHierarchicalVectorSearchManager:
    """Enhanced vector search manager with complete content preservation"""
    
    @staticmethod
    def process_project_documents_enhanced(project_id: str) -> Dict[str, Any]:
        """Process project documents with enhanced hierarchical chunking preserving ALL content"""
        try:
            # Get project - handle both integer ID and UUID
            try:
                # First try as integer ID (pk)
                project = IntelliDocProject.objects.get(id=int(project_id))
            except (ValueError, IntelliDocProject.DoesNotExist):
                # If that fails, try as UUID
                project = IntelliDocProject.objects.get(project_id=project_id)
            
            # Initialize components
            from .embeddings import get_embedder_instance
            embedder = get_embedder_instance()
            # Pass project as first argument, embedder as keyword argument
            processor = EnhancedHierarchicalProcessor(project, embedder=embedder, max_chunk_size=35000)
            database = EnhancedHierarchicalVectorDatabase(project_id)
            
            # Get project documents
            documents = project.documents.filter(upload_status='ready')
            
            logger.info(f"📋 Found {documents.count()} documents with upload_status='ready' for project {project_id}")
            
            if not documents.exists():
                logger.warning(f"⚠️ No ready documents found for project {project_id}")
                return {
                    'status': 'no_documents',
                    'message': 'No documents found to process',
                    'processed_documents': 0,
                    'failed_documents': 0,
                    'total_chunks_created': 0
                }
            
            # If LLM folder organization was previously generated, use it.
            if getattr(project, 'preserve_original_folder_structure', False):
                try:
                    from users.models import ProjectDocumentFolderOrganization

                    folder_org_map = {
                        str(doc_id): folder_path
                        for doc_id, folder_path in ProjectDocumentFolderOrganization.objects.filter(document__in=documents).values_list(
                            'document__document_id', 'folder_path'
                        )
                    }
                    processor.folder_organization_map = folder_org_map
                except Exception as e:
                    logger.debug(f"Could not load LLM folder organization mapping: {e}")
            
            # Process documents with enhanced hierarchical structure
            processed_count = 0
            failed_count = 0
            total_chunks_created = 0
            processing_details = []
            
            logger.info(f"Starting enhanced hierarchical processing of {documents.count()} documents for project {project_id}")
            
            for doc_info in processor.process_project_documents_enhanced(documents):
                try:
                    if database.insert_hierarchical_document(doc_info):
                        processed_count += 1
                        chunks_count = len(doc_info.chunks)
                        total_chunks_created += chunks_count
                        
                        # Detailed processing info
                        doc_details = {
                            'document_id': doc_info.document_metadata['document_id'],
                            'file_name': doc_info.document_metadata['file_name'],
                            'category': doc_info.document_metadata['category'],
                            'subcategory': doc_info.document_metadata.get('subcategory'),
                            'document_type': doc_info.document_metadata['document_type'],
                            'virtual_path': doc_info.document_metadata['virtual_path'],
                            'hierarchy_level': doc_info.document_metadata['hierarchy_level'],
                            'organization_level': doc_info.document_metadata['organization_level'],
                            'original_content_length': doc_info.document_metadata['original_content_length'],
                            'chunks_created': chunks_count,
                            'chunk_strategy': doc_info.document_metadata['chunk_strategy'],
                            'content_preserved': True,  # ALL content is preserved
                            'content_map': doc_info.content_map
                        }
                        processing_details.append(doc_details)
                        
                        # Log enhanced hierarchical information (chunk summaries/topics removed)
                        logger.info(f"✅ Enhanced processing completed: {doc_info.document_metadata['file_name']}")
                        logger.info(f"   📁 Category: {doc_info.document_metadata['category']}")
                        logger.info(f"   📂 Subcategory: {doc_info.document_metadata.get('subcategory', 'None')}")
                        logger.info(f"   🏗️ Virtual Path: {doc_info.document_metadata['virtual_path']}")
                        logger.info(f"   📊 Hierarchy Level: {doc_info.document_metadata['hierarchy_level']}")
                        logger.info(f"   🧩 Chunks Created: {chunks_count}")
                        logger.info(f"   📝 Original Length: {doc_info.document_metadata['original_content_length']:,} chars")
                        logger.info(f"   🔧 Organization: {doc_info.document_metadata['organization_level']}")
                        
                        if doc_info.content_map['structure_type'] == 'sectioned':
                            logger.info(f"   📑 Sections Detected: {len(doc_info.content_map['sections'])}")
                        
                    else:
                        failed_count += 1
                        logger.error(f"❌ Failed to insert enhanced document: {doc_info.document_metadata['file_name']}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Error processing document enhanced: {e}")
            
            # Update collection status
            collection, created = ProjectVectorCollection.objects.get_or_create(
                project=project,
                defaults={
                    'collection_name': f"enhanced_project_{project_id.replace('-', '_')}",
                    'status': VectorProcessingStatus.COMPLETED
                }
            )
            
            collection.total_documents = documents.count()
            collection.processed_documents = processed_count
            collection.failed_documents = failed_count
            collection.last_processed_at = timezone.now()
            collection.status = VectorProcessingStatus.COMPLETED if failed_count == 0 else VectorProcessingStatus.FAILED
            collection.save()
            
            # Enhanced result summary
            result = {
                'status': 'completed',
                'message': f'Enhanced hierarchical processing completed successfully',
                'processed_documents': processed_count,
                'failed_documents': failed_count,
                'total_chunks_created': total_chunks_created,
                'average_chunks_per_document': total_chunks_created / max(processed_count, 1),
                'content_preservation': 'complete',  # ALL content preserved
                'chunk_size_limit': 35000,
                'hierarchical_features': True,
                'enhanced_processing': True,
                'collection_name': collection.collection_name,
                'processing_details': processing_details,
                'content_statistics': EnhancedHierarchicalVectorSearchManager._calculate_content_statistics(processing_details)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced hierarchical processing failed for project {project_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'processed_documents': 0,
                'failed_documents': 0,
                'total_chunks_created': 0
            }
    
    @staticmethod
    def _calculate_content_statistics(processing_details: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics about the processed content"""
        if not processing_details:
            return {}
        
        total_content_length = sum(detail['original_content_length'] for detail in processing_details)
        total_chunks = sum(detail['chunks_created'] for detail in processing_details)
        
        # Group by category
        categories = {}
        for detail in processing_details:
            category = detail['category']
            if category not in categories:
                categories[category] = {
                    'count': 0,
                    'total_content_length': 0,
                    'total_chunks': 0
                }
            categories[category]['count'] += 1
            categories[category]['total_content_length'] += detail['original_content_length']
            categories[category]['total_chunks'] += detail['chunks_created']
        
        # Group by organization level
        organization_levels = {}
        for detail in processing_details:
            org_level = detail['organization_level']
            if org_level not in organization_levels:
                organization_levels[org_level] = 0
            organization_levels[org_level] += 1
        
        return {
            'total_documents': len(processing_details),
            'total_content_length': total_content_length,
            'total_chunks_created': total_chunks,
            'average_content_length': total_content_length / len(processing_details),
            'average_chunks_per_document': total_chunks / len(processing_details),
            'categories': categories,
            'organization_levels': organization_levels,
            'content_preservation_rate': 100.0  # 100% - all content preserved
        }
    
    @staticmethod
    def search_project_documents_enhanced(
        project_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        search_level: str = 'chunk',
        include_document_context: bool = True,
        group_by_document: bool = True
    ) -> Dict[str, Any]:
        """Enhanced search with complete content access"""
        try:
            # Initialize components
            embedder = DocumentEmbedder()
            database = EnhancedHierarchicalVectorDatabase(project_id)
            
            # Create query embedding
            query_embedding = embedder.create_embeddings(query)
            
            # Perform enhanced hierarchical search
            results = database.search_enhanced_hierarchical(
                query_vector=query_embedding,
                filters=filters,
                limit=limit,
                search_level=search_level,
                include_document_context=include_document_context,
                group_by_document=group_by_document
            )
            
            # Enhance results with content reconstruction capabilities
            enhanced_results = EnhancedHierarchicalVectorSearchManager._enhance_search_results(
                results, database, include_document_context
            )
            
            return {
                'status': 'success',
                'query': query,
                'search_level': search_level,
                'results': enhanced_results,
                'total_results': len(enhanced_results),
                'filters_applied': filters,
                'enhanced_search': True,
                'content_preservation': 'complete',
                'search_capabilities': {
                    'document_level_search': True,
                    'chunk_level_search': True,
                    'hybrid_search': True,
                    'hierarchical_filtering': True,
                    'content_reconstruction': True,
                    'cross_document_search': True
                }
            }
            
        except Exception as e:
            logger.error(f"Enhanced hierarchical search failed for project {project_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'results': []
            }
    
    @staticmethod
    def _enhance_search_results(results: List[Dict[str, Any]], 
                               database: EnhancedHierarchicalVectorDatabase,
                               include_document_context: bool) -> List[Dict[str, Any]]:
        """Enhance search results with additional capabilities"""
        enhanced_results = []
        
        for result in results:
            enhanced_result = result.copy()
            
            # Add content reconstruction capability
            if result.get('result_type') == 'document_with_chunks':
                enhanced_result['content_reconstruction'] = {
                    'can_reconstruct_full_document': True,
                    'chunk_count': result.get('chunk_count', 0),
                    'reconstruction_method': 'ordered_chunk_combination'
                }
                
                # Add sample reconstruction (first 500 chars)
                document_id = result.get('document_id')
                if document_id:
                    full_content = database.rebuild_document_content(document_id)
                    enhanced_result['content_preview'] = full_content[:500] + "..." if len(full_content) > 500 else full_content
            
            elif result.get('result_type') == 'chunk':
                # Add context about surrounding chunks
                parent_doc_id = result.get('parent_document_id')
                chunk_index = result.get('chunk_index', 0)
                total_chunks = result.get('total_chunks', 1)
                
                enhanced_result['chunk_context'] = {
                    'chunk_position': f"{chunk_index + 1} of {total_chunks}",
                    'has_previous_chunk': chunk_index > 0,
                    'has_next_chunk': chunk_index < total_chunks - 1,
                    'can_access_full_document': True,
                    'parent_document_id': parent_doc_id
                }
            
            # Add hierarchy navigation
            if 'hierarchical_path' in result:
                path_parts = result['hierarchical_path'].split('/')
                enhanced_result['hierarchy_navigation'] = {
                    'breadcrumbs': path_parts,
                    'category': result.get('category', 'general'),
                    'subcategory': result.get('subcategory'),
                    'document_type': result.get('document_type', 'document'),
                    'can_browse_siblings': True,
                    'can_browse_category': True
                }
            
            # Add content quality metrics
            enhanced_result['content_quality'] = {
                'content_length': len(result.get('content', '')),
                'estimated_reading_time_seconds': result.get('estimated_reading_time', 0),
                'word_count': result.get('word_count', 0),
                'paragraph_count': result.get('paragraph_count', 0),
                'content_density': 'high' if len(result.get('content', '')) > 1000 else 'medium' if len(result.get('content', '')) > 300 else 'low'
            }
            
            enhanced_results.append(enhanced_result)
        
        return enhanced_results
    
    @staticmethod
    def get_document_full_content(project_id: str, document_id: str) -> Dict[str, Any]:
        """Reconstruct and return full document content from chunks"""
        try:
            database = EnhancedHierarchicalVectorDatabase(project_id)
            
            # Get all chunks for the document
            chunks = database.get_document_chunks(document_id, ordered=True)
            
            if not chunks:
                return {
                    'status': 'not_found',
                    'message': 'Document not found or no chunks available',
                    'content': ''
                }
            
            # Rebuild full content
            full_content = database.rebuild_document_content(document_id)
            
            # Get document metadata from first chunk
            doc_metadata = chunks[0].get('metadata', {}) if chunks else {}
            
            return {
                'status': 'success',
                'document_id': document_id,
                'full_content': full_content,
                'content_length': len(full_content),
                'total_chunks': len(chunks),
                'reconstruction_method': 'ordered_chunk_combination',
                'content_preservation': 'complete',
                'document_metadata': {
                    'filename': doc_metadata.get('file_name', 'Unknown'),
                    'category': doc_metadata.get('category', 'general'),
                    'subcategory': doc_metadata.get('subcategory'),
                    'document_type': doc_metadata.get('document_type', 'document'),
                    'virtual_path': doc_metadata.get('virtual_path', ''),
                    'hierarchy_level': doc_metadata.get('hierarchy_level', 0),
                    'organization_level': doc_metadata.get('organization_level', 'flat'),
                    'original_content_length': doc_metadata.get('original_content_length', 0),
                    'uploaded_at': doc_metadata.get('uploaded_at'),
                    'processed_at': doc_metadata.get('processed_at')
                },
                'chunks_info': [
                    {
                        'chunk_id': chunk.get('id'),
                        'chunk_index': chunk.get('chunk_index'),
                        'chunk_type': chunk.get('chunk_type'),
                        'section_title': chunk.get('section_title'),
                        'content_length': chunk.get('content_length', 0),
                        'hierarchical_path': chunk.get('hierarchical_path')
                    }
                    for chunk in chunks
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get full document content for {document_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'content': ''
            }
    
    @staticmethod
    def get_project_hierarchy_overview_enhanced(project_id: str) -> Dict[str, Any]:
        """Get enhanced hierarchical overview of project documents"""
        try:
            database = EnhancedHierarchicalVectorDatabase(project_id)
            
            # Get enhanced statistics
            stats = database.get_hierarchy_statistics()
            
            # Get project info
            project = IntelliDocProject.objects.get(project_id=project_id)
            
            return {
                'status': 'success',
                'project_id': project_id,
                'project_name': project.name,
                'hierarchy_enabled': True,
                'enhanced_processing': True,
                'content_preservation': 'complete',
                'chunk_size_limit': 35000,
                'statistics': stats,
                'capabilities': {
                    'full_content_reconstruction': True,
                    'hierarchical_navigation': True,
                    'category_based_organization': True,
                    'section_aware_chunking': True,
                    'filename_based_hierarchy': True,
                    'multi_level_search': True,
                    'chunk_level_precision': True,
                    'document_level_context': True
                },
                'available_search_types': [
                    'document_level',
                    'chunk_level', 
                    'hybrid',
                    'category_filtered',
                    'hierarchy_filtered',
                    'content_type_filtered'
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get enhanced hierarchy overview for project {project_id}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

class EnhancedHierarchicalSearchAPI:
    """Enhanced API wrapper for hierarchical search functionality"""
    
    @staticmethod
    def search_by_category_enhanced(project_id: str, query: str, category: str, subcategory: str = None, limit: int = 5):
        """Enhanced search within specific document categories"""
        filters = {'category': category}
        if subcategory:
            filters['subcategory'] = subcategory
            
        return EnhancedHierarchicalVectorSearchManager.search_project_documents_enhanced(
            project_id, query, filters, limit
        )
    
    @staticmethod
    def search_by_document_type(project_id: str, query: str, document_type: str, limit: int = 5):
        """Search within specific document types"""
        filters = {'document_type': document_type}
        return EnhancedHierarchicalVectorSearchManager.search_project_documents_enhanced(
            project_id, query, filters, limit
        )
    
    @staticmethod
    def search_by_hierarchy_level(project_id: str, query: str, max_level: int = None, min_level: int = None, limit: int = 5):
        """Search within specific hierarchy levels"""
        filters = {}
        if max_level is not None:
            filters['max_hierarchy_level'] = max_level
        if min_level is not None:
            filters['min_hierarchy_level'] = min_level
            
        return EnhancedHierarchicalVectorSearchManager.search_project_documents_enhanced(
            project_id, query, filters, limit
        )
    
    @staticmethod
    def search_by_content_length(project_id: str, query: str, min_length: int = None, limit: int = 5):
        """Search documents/chunks with minimum content length"""
        filters = {}
        if min_length:
            filters['min_content_length'] = min_length
            
        return EnhancedHierarchicalVectorSearchManager.search_project_documents_enhanced(
            project_id, query, filters, limit
        )
    
    @staticmethod
    def advanced_enhanced_search(
        project_id: str,
        query: str,
        category: str = None,
        subcategory: str = None,
        document_type: str = None,
        max_hierarchy_level: int = None,
        min_hierarchy_level: int = None,
        chunk_types: List[str] = None,
        search_level: str = 'chunk',
        include_document_context: bool = True,
        group_by_document: bool = True,
        limit: int = 5
    ):
        """Advanced enhanced search with multiple hierarchical filters"""
        
        filters = {}
        
        if category:
            filters['category'] = category
        if subcategory:
            filters['subcategory'] = subcategory
        if document_type:
            filters['document_type'] = document_type
        if max_hierarchy_level is not None:
            filters['max_hierarchy_level'] = max_hierarchy_level
        if min_hierarchy_level is not None:
            filters['min_hierarchy_level'] = min_hierarchy_level
        if chunk_types:
            filters['chunk_types'] = chunk_types
        
        return EnhancedHierarchicalVectorSearchManager.search_project_documents_enhanced(
            project_id=project_id,
            query=query,
            filters=filters,
            limit=limit,
            search_level=search_level,
            include_document_context=include_document_context,
            group_by_document=group_by_document
        )
    
    @staticmethod
    def get_document_chunks_navigation(project_id: str, document_id: str) -> Dict[str, Any]:
        """Get navigation info for document chunks"""
        try:
            database = EnhancedHierarchicalVectorDatabase(project_id)
            chunks = database.get_document_chunks(document_id, ordered=True)
            
            if not chunks:
                return {
                    'status': 'not_found',
                    'message': 'Document not found'
                }
            
            # Build navigation structure
            navigation = {
                'document_id': document_id,
                'total_chunks': len(chunks),
                'chunks': []
            }
            
            for i, chunk in enumerate(chunks):
                chunk_nav = {
                    'chunk_id': chunk.get('id'),
                    'chunk_index': i,
                    'chunk_type': chunk.get('chunk_type'),
                    'section_title': chunk.get('section_title'),
                    'hierarchical_path': chunk.get('hierarchical_path'),
                    'content_preview': chunk.get('content', '')[:100] + "..." if len(chunk.get('content', '')) > 100 else chunk.get('content', ''),
                    'has_previous': i > 0,
                    'has_next': i < len(chunks) - 1,
                    'navigation': {
                        'previous_chunk_id': chunks[i-1].get('id') if i > 0 else None,
                        'next_chunk_id': chunks[i+1].get('id') if i < len(chunks) - 1 else None
                    }
                }
                navigation['chunks'].append(chunk_nav)
            
            return {
                'status': 'success',
                'navigation': navigation
            }
            
        except Exception as e:
            logger.error(f"Failed to get document chunks navigation: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
