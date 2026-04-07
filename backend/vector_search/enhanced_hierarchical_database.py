# Enhanced Hierarchical Vector Database with Complete Chunk Management
# backend/vector_search/enhanced_hierarchical_database.py

import logging
from typing import Dict, Any, List, Optional, Tuple
import uuid
from datetime import datetime
import json

from .enhanced_hierarchical_processor import HierarchicalDocumentInfo, DocumentChunk, EnhancedHierarchicalChunkMapper
from .database import create_project_vector_database  # Use the real database factory

logger = logging.getLogger(__name__)

class EnhancedHierarchicalVectorDatabase:
    """Enhanced vector database with complete hierarchical chunk management"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        # Use the REAL Milvus database implementation
        self.real_database = create_project_vector_database(project_id)
        
        logger.info(f"Initializing enhanced collections for project {project_id}")
        logger.info(f"Using database type: {type(self.real_database).__name__}")
    
    @staticmethod
    def search_documents(project_id: str, query: str, limit: int = 5, relevance_threshold: float = 0.7) -> Dict[str, Any]:
        """
        Static method for document search - used by RAG service
        
        Args:
            project_id: Project identifier
            query: Search query string
            limit: Maximum number of results
            relevance_threshold: Minimum relevance score
            
        Returns:
            Dictionary with search results and metadata
        """
        try:
            logger.info(f"🔍 RAG SEARCH: Searching documents for project {project_id}")
            logger.info(f"🔍 RAG SEARCH: Query: '{query}', Limit: {limit}, Threshold: {relevance_threshold}")
            
            # Create database instance for this project
            db_instance = EnhancedHierarchicalVectorDatabase(project_id)
            
            # Use the real database search functionality
            search_results = db_instance.real_database.search(
                query_text=query,
                limit=limit
            )
            
            # Format results for RAG consumption
            formatted_results = []
            
            if search_results and 'matches' in search_results:
                for match in search_results['matches']:
                    # Extract relevance score
                    score = match.get('score', 0.0)
                    
                    # Only include results above threshold
                    if score >= relevance_threshold:
                        formatted_result = {
                            'content': match.get('content', ''),
                            'score': score,
                            'metadata': {
                                'source': match.get('metadata', {}).get('file_name', 'Unknown'),
                                'document_id': match.get('metadata', {}).get('document_id', ''),
                                'chunk_id': match.get('metadata', {}).get('chunk_id', ''),
                                'chunk_type': match.get('metadata', {}).get('chunk_type', 'text'),
                                'section_title': match.get('metadata', {}).get('section_title', ''),
                                'hierarchical_path': match.get('metadata', {}).get('hierarchical_path', []),
                                'page': match.get('metadata', {}).get('page_number', 1),
                                'chunk_index': match.get('metadata', {}).get('chunk_index', 0)
                            }
                        }
                        formatted_results.append(formatted_result)
            
            logger.info(f"🔍 RAG SEARCH: Found {len(formatted_results)} relevant documents above threshold")
            
            return {
                'success': True,
                'results': formatted_results,
                'total_found': len(formatted_results),
                'query': query,
                'project_id': project_id,
                'search_metadata': {
                    'limit': limit,
                    'relevance_threshold': relevance_threshold,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"🔍 RAG SEARCH: Search failed for project {project_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'total_found': 0,
                'query': query,
                'project_id': project_id
            }
    
    # Alias for backward compatibility
    @classmethod
    def search_project_documents(cls, project_id: str, query: str, limit: int = 5) -> Dict[str, Any]:
        """Backward compatibility alias for search_documents"""
        return cls.search_documents(project_id, query, limit)
    
    def insert_hierarchical_document(self, doc_info: HierarchicalDocumentInfo) -> bool:
        """Insert document with all chunks preserving hierarchical structure using BATCH insertion"""
        try:
            doc_metadata = doc_info.document_metadata
            file_name = doc_metadata['file_name']

            logger.info(f"   [DB] Starting BATCH insertion for document: {file_name} ({len(doc_info.chunks)} chunks)")

            # Prepare all chunks as document info objects for batch insertion
            chunks_data = []

            for i, chunk in enumerate(doc_info.chunks):
                try:
                    # Prepare chunk info for the real database
                    chunk_doc_info = {
                        'document_id': chunk.parent_document_id,
                        'file_name': doc_metadata['file_name'],
                        'content': chunk.content,
                        'chunk_index': chunk.chunk_index,
                        'total_chunks': chunk.total_chunks,
                        'chunk_id': chunk.chunk_id,
                        'chunk_type': chunk.chunk_type,
                        'section_title': chunk.section_title,
                        'hierarchical_path': chunk.hierarchical_path,
                        'embedding': chunk.embedding,

                        # Enhanced metadata
                        'metadata': chunk.metadata,

                        # Hierarchical fields
                        'hierarchy_level': doc_metadata['hierarchy_level'],
                        'category': doc_metadata['category'],
                        'subcategory': doc_metadata.get('subcategory'),
                        'document_type': doc_metadata['document_type'],
                        'virtual_path': doc_metadata['virtual_path'],
                        'organization_level': doc_metadata['organization_level'],

                        # File info
                        'file_size': doc_metadata.get('file_size', 0),
                        'file_type': doc_metadata.get('file_type', ''),
                        'content_length': len(chunk.content),
                        'is_complete_document': chunk.total_chunks == 1,

                        # Additional chunk metadata
                        'chunk_folder': chunk.metadata.get('chunk_folder'),
                        'chunk_relative_path': chunk.metadata.get('chunk_relative_path'),

                        # Search optimization fields
                        'word_count': len(chunk.content.split()),
                        'paragraph_count': len(chunk.content.split('\n\n')),
                        'estimated_reading_time': len(chunk.content.split()) // 200,

                        # Processing info
                        'processing_time_ms': 0,  # Could be calculated
                        'error_message': '',
                        'uploaded_at': doc_metadata.get('uploaded_at', datetime.now().isoformat()),
                        'has_embedding': chunk.embedding is not None
                    }

                    # Create a simple object wrapper for the real database
                    class DocumentInfo:
                        def __init__(self, data):
                            self.content = data['content']
                            self.embedding = data['embedding']
                            self.metadata = data

                    # Create document info object and add to batch
                    doc_info_obj = DocumentInfo(chunk_doc_info)
                    chunks_data.append(doc_info_obj)

                except Exception as chunk_error:
                    logger.exception(f"      [DB.{i+1}] 💥 Error preparing chunk {chunk.chunk_index} for {file_name}: {chunk_error}")
                    return False

            # Perform BATCH insertion - all chunks inserted in a single operation
            logger.info(f"   [DB] 🚀 Performing BATCH insertion for all {len(chunks_data)} chunks...")
            success = self.real_database.batch_insert_document_chunks(chunks_data, file_name)

            if success:
                logger.info(f"   [DB] ✅ Successfully BATCH inserted all {len(doc_info.chunks)} chunks for {file_name}")
                return True
            else:
                logger.error(f"   [DB] ❌ BATCH insertion failed for {file_name}")
                return False

        except Exception as e:
            logger.exception(f"   [DB] 💥 Unhandled error inserting hierarchical document: {e}")
            return False

    def search_enhanced_hierarchical(self, 
                                   query_vector: List[float],
                                   filters: Optional[Dict[str, Any]] = None,
                                   limit: int = 5,
                                   search_level: str = 'chunk',
                                   include_document_context: bool = True,
                                   group_by_document: bool = True) -> List[Dict[str, Any]]:
        """Enhanced hierarchical search with multiple options"""
        try:
            # Use the real database's search method
            search_results = self.real_database.search_documents(
                query_vector=query_vector,
                filters=filters,
                limit=limit * 2  # Get more results to process
            )
            
            # Process and enhance results
            enhanced_results = []
            for result in search_results:
                enhanced_result = {
                    **result,
                    'result_type': 'chunk',
                    'hierarchy_navigation': {
                        'can_expand': False,
                        'chunk_count': 1,
                        'hierarchy_level': result.get('hierarchy_level', 0),
                        'category': result.get('category', 'general'),
                        'subcategory': result.get('subcategory'),
                        'document_type': result.get('document_type', 'document')
                    }
                }
                enhanced_results.append(enhanced_result)
            
            return enhanced_results[:limit]
            
        except Exception as e:
            logger.error(f"Enhanced hierarchical search failed: {e}")
            return []

    def get_document_chunks(self, document_id: str, ordered: bool = True) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document"""
        try:
            # Use the real database to get chunks
            filters = {'document_id': document_id}
            chunks = self.real_database.search_documents(
                query_vector=None,  # Get all chunks, no vector search
                filters=filters,
                limit=1000  # Large limit to get all chunks
            )
            
            if ordered:
                # Sort by chunk index to maintain document order
                chunks.sort(key=lambda x: x.get('chunk_index', 0))
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to get document chunks for {document_id}: {e}")
            return []

    def rebuild_document_content(self, document_id: str) -> str:
        """Rebuild complete document content from chunks"""
        try:
            chunks = self.get_document_chunks(document_id, ordered=True)
            
            if not chunks:
                return ""
            
            # Combine chunk content in order
            full_content = ""
            for chunk in chunks:
                content = chunk.get('content', '')
                chunk_type = chunk.get('chunk_type', 'content')
                
                if chunk_type == 'complete_document':
                    return content
                
                # Add appropriate separators
                if full_content and chunk_type in ['section', 'introduction']:
                    full_content += "\n\n"
                elif full_content:
                    full_content += "\n"
                
                full_content += content
            
            return full_content
            
        except Exception as e:
            logger.error(f"Failed to rebuild document content for {document_id}: {e}")
            return ""

    def get_hierarchy_statistics(self) -> Dict[str, Any]:
        """Get statistics about the hierarchical structure"""
        try:
            stats = {
                'total_documents': 0,
                'total_chunks': 0,
                'categories': {},
                'document_types': {},
                'hierarchy_levels': {},
                'chunk_types': {},
                'average_chunks_per_document': 0,
                'content_distribution': {}
            }
            
            # Use real database to get statistics
            # This is a simplified implementation
            all_documents = self.real_database.search_documents(
                query_vector=None,
                filters={},
                limit=10000  # Large limit to get all documents
            )
            
            stats['total_chunks'] = len(all_documents)
            
            # Group by document to count documents
            document_ids = set()
            for doc in all_documents:
                document_ids.add(doc.get('document_id', ''))
            
            stats['total_documents'] = len(document_ids)
            
            if stats['total_documents'] > 0:
                stats['average_chunks_per_document'] = stats['total_chunks'] / stats['total_documents']
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get hierarchy statistics: {e}")
            return {}

    def delete_document_and_chunks(self, document_id: str) -> bool:
        """Delete document and all associated chunks"""
        try:
            # Use the real database's delete method if available
            if hasattr(self.real_database, 'delete_documents'):
                success = self.real_database.delete_documents({'document_id': document_id})
                if success:
                    logger.info(f"Successfully deleted document {document_id} and all chunks")
                    return True
            
            logger.warning(f"Delete method not available for document {document_id}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False
