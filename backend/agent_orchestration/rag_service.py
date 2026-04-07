"""
Document-Aware Agent RAG Service - Phase 2 AutoGen Integration

Provides RAG (Retrieval-Augmented Generation) capabilities for document-aware agents
using the existing Milvus vector database infrastructure.
"""

import logging
from typing import Dict, List, Any, Optional
from django.conf import settings
from users.models import IntelliDocProject

logger = logging.getLogger('agent_orchestration')

class DocumentAwareAgentService:
    """RAG service for document-aware agents using existing Milvus infrastructure"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        logger.info(f"📚 RAG SERVICE: Initializing DocumentAwareAgentService for project {project_id}")
        
        # Load project for access to processing capabilities
        try:
            self.project = IntelliDocProject.objects.get(project_id=project_id)
            logger.info(f"📚 RAG SERVICE: Loaded project {self.project.name}")
        except IntelliDocProject.DoesNotExist:
            logger.error(f"📚 RAG SERVICE: Project {project_id} not found")
            raise ValueError(f"Project {project_id} not found")
    
    def create_retrieval_function(self, agent_config: Dict[str, Any]):
        """
        Create RAG retrieval function for AutoGen agents
        
        Args:
            agent_config: Agent configuration containing RAG settings
            
        Returns:
            Function that can be registered with AutoGen agents
        """
        vector_collections = agent_config.get('vector_collections', ['project_documents'])
        search_limit = agent_config.get('rag_search_limit', 5)
        relevance_threshold = agent_config.get('rag_relevance_threshold', 0.7)
        
        logger.info(f"📚 RAG FUNCTION: Creating retrieval function for collections: {vector_collections}")
        logger.info(f"📚 RAG FUNCTION: Search limit: {search_limit}, Relevance threshold: {relevance_threshold}")
        
        def retrieve_documents(query: str, limit: Optional[int] = None) -> List[Dict]:
            """
            Retrieve relevant documents for agent query using Milvus vector search
            
            Args:
                query: Search query string
                limit: Maximum number of documents to retrieve
                
            Returns:
                List of relevant document chunks with metadata
            """
            try:
                effective_limit = limit or search_limit
                logger.info(f"📚 RAG RETRIEVAL: Searching for '{query}' with limit {effective_limit}")
                
                # Use existing EnhancedHierarchicalDatabase for search
                from vector_search.enhanced_hierarchical_database import EnhancedHierarchicalDatabase
                
                # Perform vector search across specified collections
                search_results = EnhancedHierarchicalDatabase.search_documents(
                    project_id=self.project_id,
                    query=query,
                    limit=effective_limit,
                    relevance_threshold=relevance_threshold
                )
                
                # Process and format results for AutoGen consumption
                formatted_results = []
                if search_results and 'results' in search_results:
                    for result in search_results['results'][:effective_limit]:
                        formatted_result = {
                            'content': result.get('content', ''),
                            'metadata': {
                                'source': result.get('metadata', {}).get('source', 'Unknown'),
                                'page': result.get('metadata', {}).get('page', 1),
                                'score': result.get('score', 0.0),
                                'chunk_type': result.get('metadata', {}).get('chunk_type', 'text'),
                                'document_id': result.get('metadata', {}).get('document_id', ''),
                                'collection': 'project_documents'  # Main collection
                            }
                        }
                        
                        # Only include results above relevance threshold
                        if formatted_result['metadata']['score'] >= relevance_threshold:
                            formatted_results.append(formatted_result)
                
                logger.info(f"📚 RAG RETRIEVAL: Found {len(formatted_results)} relevant documents")
                return formatted_results
                
            except Exception as e:
                logger.error(f"📚 RAG RETRIEVAL: Failed to retrieve documents: {str(e)}")
                # Return empty list instead of failing to keep agent functional
                return []
        
        return retrieve_documents
    
    def enhance_agent_with_rag(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add RAG capabilities to AutoGen agent configuration
        
        Args:
            agent_config: Original agent configuration
            
        Returns:
            Enhanced configuration with RAG functions
        """
        if not agent_config.get('doc_aware', False):
            logger.info(f"📚 RAG ENHANCEMENT: Agent not doc_aware, skipping RAG enhancement")
            return agent_config
        
        logger.info(f"📚 RAG ENHANCEMENT: Adding RAG capabilities to agent")
        
        # Create retrieval function
        retrieval_function = self.create_retrieval_function(agent_config)
        
        # Enhance system message with RAG instructions
        original_system_message = agent_config.get('system_message', 'You are a helpful AI assistant.')
        
        enhanced_system_message = f"""
{original_system_message}

DOCUMENT ACCESS CAPABILITY:
You have access to project documents through a retrieval function. When you need information from uploaded documents, use the retrieve_documents function with relevant search queries.

Available function:
- retrieve_documents(query: str, limit: int = 5) -> List[Dict]: Search project documents for relevant content

The function returns a list of document chunks with:
- content: The actual text content
- metadata: Source, page number, relevance score, and document information

Use this function when:
1. The user asks about document content
2. You need context from uploaded files
3. You want to cite specific information from project documents

Example usage:
docs = retrieve_documents("financial projections", limit=3)
for doc in docs:
    print(f"From {doc['metadata']['source']}: {doc['content']}")
"""
        
        # Create enhanced configuration
        enhanced_config = {
            **agent_config,
            'system_message': enhanced_system_message,
            'rag_functions': {
                'retrieve_documents': retrieval_function
            },
            'rag_enabled': True
        }
        
        logger.info(f"📚 RAG ENHANCEMENT: Agent enhanced with RAG capabilities")
        logger.info(f"📚 RAG ENHANCEMENT: Collections: {agent_config.get('vector_collections', [])}")
        
        return enhanced_config
    
    def get_rag_status(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get RAG status information for agent
        
        Args:
            agent_config: Agent configuration
            
        Returns:
            RAG status information
        """
        if not agent_config.get('doc_aware', False):
            return {
                'enabled': False,
                'status': 'disabled',
                'collections': [],
                'document_count': 0
            }
        
        try:
            # Get document count from vector database
            from vector_search.enhanced_hierarchical_database import EnhancedHierarchicalDatabase
            
            # This would ideally get actual document counts from Milvus
            # For now, return basic status
            vector_collections = agent_config.get('vector_collections', ['project_documents'])
            
            return {
                'enabled': True,
                'status': 'active',
                'collections': vector_collections,
                'search_limit': agent_config.get('rag_search_limit', 5),
                'relevance_threshold': agent_config.get('rag_relevance_threshold', 0.7),
                'document_count': 'Available',  # Could be enhanced with actual count
                'function_name': 'retrieve_documents'
            }
            
        except Exception as e:
            logger.error(f"📚 RAG STATUS: Failed to get status: {str(e)}")
            return {
                'enabled': True,
                'status': 'error',
                'error': str(e),
                'collections': agent_config.get('vector_collections', [])
            }

class MultiCollectionRAGService:
    """Enhanced RAG service supporting multiple vector collections"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.base_service = DocumentAwareAgentService(project_id)
        logger.info(f"📚 MULTI-RAG: Initializing multi-collection RAG service")
    
    def search_across_collections(self, query: str, collections: List[str], limit: int = 5) -> List[Dict]:
        """
        Search across multiple vector collections
        
        Args:
            query: Search query
            collections: List of collection names to search
            limit: Maximum results per collection
            
        Returns:
            Combined and ranked results from all collections
        """
        logger.info(f"📚 MULTI-RAG: Searching across collections: {collections}")
        
        all_results = []
        
        for collection in collections:
            try:
                # For each collection, we could potentially have different search logic
                if collection == 'project_documents':
                    # Use main document retrieval
                    results = self.base_service.create_retrieval_function({
                        'vector_collections': [collection],
                        'rag_search_limit': limit,
                        'rag_relevance_threshold': 0.7
                    })(query, limit)
                    
                    # Add collection info to metadata
                    for result in results:
                        result['metadata']['collection'] = collection
                    
                    all_results.extend(results)
                    
                elif collection == 'knowledge_base':
                    # Could implement knowledge base specific search
                    logger.info(f"📚 MULTI-RAG: Knowledge base search not yet implemented")
                    
                elif collection == 'chat_history':
                    # Could implement chat history search
                    logger.info(f"📚 MULTI-RAG: Chat history search not yet implemented")
                    
            except Exception as e:
                logger.error(f"📚 MULTI-RAG: Failed to search collection {collection}: {str(e)}")
        
        # Sort all results by relevance score
        all_results.sort(key=lambda x: x['metadata'].get('score', 0.0), reverse=True)
        
        # Return top results across all collections
        return all_results[:limit * len(collections)]
