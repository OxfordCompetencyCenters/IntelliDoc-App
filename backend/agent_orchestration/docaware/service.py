"""
Enhanced DocAware Agent Service
==============================

Main service class that integrates with ChromaDB Search to provide
comprehensive RAG capabilities for document-aware agents.
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional, Union
from django.conf import settings
from users.models import IntelliDocProject
from vector_search.chromadb_search_service import ChromaDBSearchService, ChromaSearchRequest, ChromaSearchResult

from .search_methods import DocAwareSearchMethods, SearchMethod, SearchMethodConfig
from .embedding_service import DocAwareEmbeddingService
from .filter_expr import build_content_filter_expression_impl

logger = logging.getLogger('agent_orchestration')

class EnhancedDocAwareAgentService:
    """Enhanced RAG service with multiple search methods using ChromaDB Search"""

    def __init__(self, project_id: str):
        """
        Initialize the enhanced DocAware service

        Args:
            project_id: ID of the project containing documents
        """
        self.project_id = project_id
        logger.info(f"📚 ENHANCED RAG: Initializing service for project {project_id}")

        # Load project
        try:
            self.project = IntelliDocProject.objects.get(project_id=project_id)

            # Use the actual collection name from ProjectVectorCollection if it exists
            # This ensures we use the same name that was used when documents were processed
            from users.models import ProjectVectorCollection
            try:
                vector_collection = ProjectVectorCollection.objects.get(project=self.project)
                self.collection_name = vector_collection.collection_name
                logger.info(f"📚 ENHANCED RAG: Using stored collection name from ProjectVectorCollection: {self.collection_name}")
            except ProjectVectorCollection.DoesNotExist:
                # Fallback to generated name if no collection record exists yet
                self.collection_name = self.project.generate_collection_name()
                logger.info(f"📚 ENHANCED RAG: No ProjectVectorCollection found, using generated name: {self.collection_name}")

            logger.info(f"📚 ENHANCED RAG: Loaded project {self.project.name}, collection: {self.collection_name}")
            logger.info(f"📦 PROJECT ISOLATION: DocAware service initialized for project {project_id} with collection {self.collection_name}")
        except IntelliDocProject.DoesNotExist:
            logger.error(f"📚 ENHANCED RAG: Project {project_id} not found")
            raise ValueError(f"Project {project_id} not found")

        # Initialize services
        self.search_service = ChromaDBSearchService()
        self.embedding_service = DocAwareEmbeddingService()
        
        # Cache conversation context
        self.conversation_context = []
    
    def search_documents(
        self,
        query: str,
        search_method: SearchMethod = SearchMethod.HYBRID_SEARCH,
        method_parameters: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[List[str]] = None,
        content_filters: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents using the specified method

        Args:
            query: Search query text
            search_method: Method to use for searching
            method_parameters: Parameters specific to the search method
            conversation_context: Recent conversation context for contextual search
            content_filters: List of content filter IDs (e.g., ["folder_Reports", "file_doc123"])

        Returns:
            List of search results with content and metadata
        """
        logger.info(f"📚 SEARCH: Starting {search_method.value} search for: '{query[:50]}...'")

        # Build combined content filter expression from multiple filters
        content_filter_expr = self._build_multi_content_filter_expression(content_filters) if content_filters else None
        if content_filter_expr:
            logger.info(f"📚 SEARCH: Applying multi-filter expression with {len(content_filters)} filters")
            logger.debug(f"📚 SEARCH: Filter expression: {content_filter_expr}")
        elif content_filters:
            logger.warning(f"📚 SEARCH: Content filters provided but could not build expression: {content_filters}")
        
        # Get method configuration
        method_config = DocAwareSearchMethods.get_method_config(search_method)
        if not method_config:
            logger.warning(f"📚 SEARCH: Unknown or unsupported search method: {search_method}, returning no results")
            return []
        
        # Validate and set parameters
        parameters = method_parameters or {}
        validated_params = DocAwareSearchMethods.validate_parameters(search_method, parameters)
        
        # Update conversation context if provided
        if conversation_context:
            self.conversation_context = conversation_context[-5:]  # Keep last 5 turns
        
        # Route to appropriate search implementation with content filter
        if search_method == SearchMethod.SEMANTIC_SEARCH:
            return self._semantic_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.HYBRID_SEARCH:
            return self._hybrid_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.CONTEXTUAL_SEARCH:
            return self._contextual_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.SIMILARITY_THRESHOLD:
            return self._similarity_threshold_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.MULTI_COLLECTION:
            return self._multi_collection_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.HIERARCHICAL_SEARCH:
            return self._hierarchical_search(query, validated_params, content_filter_expr)
        elif search_method == SearchMethod.KEYWORD_SEARCH:
            return self._keyword_search(query, validated_params, content_filter_expr)
        else:
            logger.warning(f"📚 SEARCH: Search method not implemented: {search_method}, returning no results")
            return []

    
    def _extract_document_fields(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract document fields with flexible field name mapping
        
        This method handles cases where documents are stored with different field names
        than expected (e.g., 'text' instead of 'content', 'filename' instead of 'source')
        
        Args:
            hit: Raw search result from ChromaDB
            
        Returns:
            Standardized document fields
        """
        # Try multiple possible field names for content
        content = (
            hit.get("content") or 
            hit.get("text") or 
            hit.get("document_text") or 
            hit.get("body") or 
            hit.get("chunk_text") or
            hit.get("passage") or
            hit.get("paragraph") or
            ""
        )
        
        # Try multiple possible field names for source/filename
        source = (
            hit.get("source") or
            hit.get("filename") or
            hit.get("file_name") or
            hit.get("document_name") or
            hit.get("title") or
            hit.get("doc_name") or
            hit.get("file") or
            "Unknown"
        )
        
        # Try multiple possible field names for page number
        page = (
            hit.get("page") or
            hit.get("page_number") or
            hit.get("chunk_page") or
            hit.get("page_num") or
            1
        )
        
        # Try multiple possible field names for document ID
        document_id = (
            hit.get("document_id") or
            hit.get("doc_id") or
            hit.get("id") or
            hit.get("_id") or
            ""
        )
        
        # Try multiple possible field names for chunk type
        chunk_type = (
            hit.get("chunk_type") or
            hit.get("type") or
            hit.get("section_type") or
            hit.get("content_type") or
            "text"
        )
        
        # Enhanced validation and logging for content
        content_length = len(content) if content else 0
        is_empty = not content or len(content.strip()) == 0
        
        if is_empty:
            logger.warning(f"⚠️ FIELD MAPPING: Document has EMPTY content! Content length: {content_length}")
            logger.warning(f"⚠️ FIELD MAPPING: Available fields in hit: {list(hit.keys())}")
            # Show first few characters of each field to help debug
            for key, value in hit.items():
                if isinstance(value, str) and len(value) > 10:
                    logger.info(f"📚 FIELD MAPPING: Field '{key}' contains: {str(value)[:100]}...")
                elif isinstance(value, (int, float, bool)):
                    logger.info(f"📚 FIELD MAPPING: Field '{key}' = {value}")
        else:
            logger.debug(f"📚 FIELD MAPPING: Document content length: {content_length} chars")
        
        if source == "Unknown":
            logger.debug(f"📚 FIELD MAPPING: No source found in hit with keys: {list(hit.keys())}")
        
        return {
            "content": str(content).strip() if content else "",
            "source": str(source).strip() if source else "Unknown",
            "page": int(page) if isinstance(page, (int, float)) or (isinstance(page, str) and page.isdigit()) else 1,
            "document_id": str(document_id) if document_id else "",
            "chunk_type": str(chunk_type) if chunk_type else "text"
        }
    
    def get_collection_metric_type(self, collection_name: str) -> str:
        """
        Return the metric type used by the collection.

        ChromaDB always uses cosine similarity (configured at collection
        creation time via ``hnsw:space``), so this simply returns ``"COSINE"``.

        Args:
            collection_name: Name of the collection to inspect

        Returns:
            ``"COSINE"`` always.
        """
        return "COSINE"
    
    def _build_content_filter_expression(self, content_filter: str) -> str:
        """
        Build filter expression from content filter ID.

        The expression uses Milvus-style syntax which the ChromaDB search
        service parses internally.

        Args:
            content_filter: Content filter ID (e.g., "folder_Reports/Financial" or "file_doc123")

        Returns:
            Filter expression string
        """
        try:
            filter_expr = build_content_filter_expression_impl(content_filter)
            if filter_expr:
                logger.info(f"🔍 CONTENT FILTER: Building expression for filter: {content_filter} -> {filter_expr}")
            elif content_filter:
                logger.warning(f"🔍 CONTENT FILTER: Unknown or empty filter format: {content_filter}")
            return filter_expr
        except Exception as e:
            logger.error(f"❌ CONTENT FILTER: Failed to build filter expression: {e}")
            return ""

    def _build_multi_content_filter_expression(self, content_filters: List[str]) -> str:
        """
        Build filter expression from multiple content filter IDs.
        Combines multiple filters with OR logic.

        The expression uses Milvus-style syntax which the ChromaDB search
        service parses internally.

        Args:
            content_filters: List of content filter IDs
                Examples:
                - ["folder_Reports/Financial", "folder_Legal"]
                - ["file_doc123", "file_doc456"]
                - ["folder_Reports", "file_doc789"]  # Mixed

        Returns:
            Combined filter expression string with OR logic

        Examples:
            Input: ["folder_Reports", "folder_Legal"]
            Output: "(hierarchical_path like 'Reports%') || (hierarchical_path like 'Legal%')"

            Input: ["folder_Reports", "file_doc123"]
            Output: "(hierarchical_path like 'Reports%') || (document_id == 'doc123')"
        """
        if not content_filters or len(content_filters) == 0:
            return ""

        try:
            filter_expressions = []

            for content_filter in content_filters:
                if not content_filter or not isinstance(content_filter, str):
                    logger.warning(f"🔍 MULTI-FILTER: Skipping invalid filter: {content_filter}")
                    continue

                # Build individual filter expression
                individual_expr = self._build_content_filter_expression(content_filter)

                if individual_expr:
                    filter_expressions.append(individual_expr)

            if not filter_expressions:
                logger.warning(f"🔍 MULTI-FILTER: No valid filter expressions generated from {len(content_filters)} filters")
                return ""

            # Combine with OR logic
            if len(filter_expressions) == 1:
                combined_expr = filter_expressions[0]
            else:
                # Wrap each expression in parentheses and join with ||
                combined_expr = " || ".join([f"({expr})" for expr in filter_expressions])

            logger.info(f"🔍 MULTI-FILTER: Generated combined expression with {len(filter_expressions)} filters")
            logger.debug(f"🔍 MULTI-FILTER: Expression: {combined_expr}")

            return combined_expr

        except Exception as e:
            logger.error(f"❌ MULTI-FILTER: Failed to build multi-filter expression: {e}")
            import traceback
            logger.error(f"❌ MULTI-FILTER: Traceback: {traceback.format_exc()}")
            return ""
    
    def _semantic_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Enhanced semantic search using ChromaDB"""
        try:
            detected_metric = self.get_collection_metric_type(self.collection_name)

            logger.info(f"🔍 SEMANTIC: Starting search with metric: {detected_metric}")
            logger.debug(f"🔍 SEMANTIC: Query: '{query[:50]}...', Params: {params}")

            # Generate query embedding
            query_vector = self.embedding_service.encode_query(query)
            logger.debug(f"🔍 SEMANTIC: Generated embedding vector of length {len(query_vector)}")

            # Create search request
            search_request = ChromaSearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                limit=params["search_limit"],
                filter_expression=content_filter_expr if content_filter_expr else "",
                output_fields=["*"]  # Return all fields
            )

            logger.info(f"🔍 SEMANTIC: Search request created - Collection: {self.collection_name}, Metric: {detected_metric}, Limit: {params['search_limit']}")

            # Perform search
            search_result = self.search_service.search(search_request)

            # Filter by relevance threshold and format results
            results = []
            for hit in search_result.hits:
                score = hit.get("score", 0.0)
                if score >= params["relevance_threshold"]:
                    results.append({
                        "content": hit.get("content", ""),
                        "metadata": {
                            "source": hit.get("source", hit.get("file_name", "Unknown")),
                            "page": hit.get("page", hit.get("page_number", 1)),
                            "score": score,
                            "chunk_type": hit.get("chunk_type", "text"),
                            "document_id": hit.get("document_id", ""),
                            "collection": self.collection_name,
                            "search_method": "semantic_search",
                            "metric_used": detected_metric,
                            "vector_dimension": len(query_vector)
                        }
                    })

            logger.info(f"✅ SEMANTIC: Found {len(results)} results above threshold {params['relevance_threshold']} using {detected_metric} metric")
            return results

        except Exception as e:
            logger.error(f"❌ SEMANTIC: Search failed with error: {e}")
            logger.error(f"❌ SEMANTIC: Collection: {self.collection_name}")
            return []
    
    def _hybrid_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Enhanced hybrid search using ChromaDB"""
        try:
            detected_metric = self.get_collection_metric_type(self.collection_name)

            logger.info(f"🔍 HYBRID: Starting search with metric: {detected_metric}")

            # Generate query embedding
            query_vector = self.embedding_service.encode_query(query)

            # Combine existing filter with content filter
            existing_filter = params.get("filter_expression", "")
            if content_filter_expr and existing_filter:
                combined_filter = f"({existing_filter}) && ({content_filter_expr})"
            elif content_filter_expr:
                combined_filter = content_filter_expr
            else:
                combined_filter = existing_filter

            # Create search request
            search_request = ChromaSearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                limit=params["search_limit"],
                filter_expression=combined_filter if combined_filter else "",
                output_fields=["*"]  # Return all fields
            )

            # Perform semantic search
            search_result = self.search_service.search(search_request)

            # Apply keyword weighting
            keyword_weight = params["keyword_weight"]
            results = []

            for hit in search_result.hits:
                # Extract fields with flexible field name mapping
                content = (
                    hit.get("content") or
                    hit.get("text") or
                    hit.get("document_text") or
                    hit.get("body") or
                    hit.get("chunk_text") or
                    ""
                )

                source = (
                    hit.get("source") or
                    hit.get("filename") or
                    hit.get("file_name") or
                    hit.get("document_name") or
                    hit.get("title") or
                    "Unknown"
                )

                page = (
                    hit.get("page") or
                    hit.get("page_number") or
                    1
                )

                # Enhanced validation and logging for content
                content_length = len(content) if content else 0
                is_empty = not content or len(content.strip()) == 0

                if is_empty:
                    logger.warning(f"⚠️ HYBRID SEARCH: Document has EMPTY content! Content length: {content_length}")
                    logger.warning(f"⚠️ HYBRID SEARCH: Available fields in hit: {list(hit.keys())}")
                    # Show sample of each field to help identify the correct one
                    for key, value in hit.items():
                        if isinstance(value, str) and len(value) > 20:
                            logger.info(f"📚 HYBRID SEARCH: Field '{key}' contains: {str(value)[:100]}...")
                        elif isinstance(value, (int, float, bool)):
                            logger.info(f"📚 HYBRID SEARCH: Field '{key}' = {value}")
                else:
                    logger.debug(f"📚 HYBRID SEARCH: Document content length: {content_length} chars")

                semantic_score = hit.get("score", 0.0)

                # Simple keyword matching score
                content_for_keyword = content.lower() if content else ""
                query_words = query.lower().split()
                keyword_matches = sum(1 for word in query_words if word in content_for_keyword)
                keyword_score = keyword_matches / len(query_words) if query_words else 0

                # Combine scores
                final_score = (1 - keyword_weight) * semantic_score + keyword_weight * keyword_score

                results.append({
                    "content": content,  # Use extracted content
                    "metadata": {
                        "source": source,  # Use extracted source
                        "page": page,  # Use extracted page
                        "score": final_score,
                        "semantic_score": semantic_score,
                        "keyword_score": keyword_score,
                        "chunk_type": hit.get("chunk_type", "text"),
                        "document_id": hit.get("document_id", ""),
                        "collection": self.collection_name,
                        "search_method": "hybrid_search",
                        "metric_used": detected_metric
                    }
                })
            
            # Sort by final score
            results.sort(key=lambda x: x["metadata"]["score"], reverse=True)
            
            logger.info(f"✅ HYBRID: Found {len(results)} results with hybrid scoring using {detected_metric} metric")
            return results

        except Exception as e:
            logger.error(f"❌ HYBRID: Search failed with error: {e}")
            logger.error(f"❌ HYBRID: Collection: {self.collection_name}")
            return []
    
    def _contextual_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Perform contextual search using conversation history"""
        try:
            # Generate contextualized query embedding
            context_window = params["context_window"]
            context_weight = params["context_weight"]

            relevant_context = self.conversation_context[-context_window:] if self.conversation_context else []

            query_vector = self.embedding_service.encode_with_context(
                query, relevant_context, context_weight
            )

            detected_metric = self.get_collection_metric_type(self.collection_name)

            # Create search request
            search_request = ChromaSearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                limit=params["search_limit"],
                filter_expression=content_filter_expr if content_filter_expr else "",
                output_fields=["*"]  # Return all fields
            )

            # Perform search
            search_result = self.search_service.search(search_request)

            # Filter and format results
            results = []
            for hit in search_result.hits:
                score = hit.get("score", 0.0)
                if score >= params["relevance_threshold"]:
                    results.append({
                        "content": hit.get("content", ""),
                        "metadata": {
                            "source": hit.get("source", hit.get("file_name", "Unknown")),
                            "page": hit.get("page", hit.get("page_number", 1)),
                            "score": score,
                            "chunk_type": hit.get("chunk_type", "text"),
                            "document_id": hit.get("document_id", ""),
                            "collection": self.collection_name,
                            "search_method": "contextual_search",
                            "context_used": len(relevant_context),
                            "context_weight": context_weight,
                            "metric_used": detected_metric
                        }
                    })

            logger.info(f"✅ CONTEXTUAL: Found {len(results)} results with context from {len(relevant_context)} turns using {detected_metric} metric")
            return results

        except Exception as e:
            logger.error(f"❌ CONTEXTUAL: Search failed with error: {e}")
            logger.error(f"❌ CONTEXTUAL: Collection: {self.collection_name}")
            return []
    
    def _similarity_threshold_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Return all results above similarity threshold using ChromaDB"""
        try:
            detected_metric = self.get_collection_metric_type(self.collection_name)
            logger.info(f"🔍 THRESHOLD: Using metric: {detected_metric}")

            # Generate query embedding
            query_vector = self.embedding_service.encode_query(query)

            # Search with high limit to get all potential matches
            search_request = ChromaSearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                limit=params["max_results"],
                filter_expression=content_filter_expr if content_filter_expr else "",
                output_fields=["*"]  # Return all fields
            )

            # Perform search
            search_result = self.search_service.search(search_request)

            # Filter by strict threshold
            threshold = params["similarity_threshold"]
            results = []

            for hit in search_result.hits:
                score = hit.get("score", 0.0)
                if score >= threshold:
                    results.append({
                        "content": hit.get("content", ""),
                        "metadata": {
                            "source": hit.get("source", hit.get("file_name", "Unknown")),
                            "page": hit.get("page", hit.get("page_number", 1)),
                            "score": score,
                            "chunk_type": hit.get("chunk_type", "text"),
                            "document_id": hit.get("document_id", ""),
                            "collection": self.collection_name,
                            "search_method": "similarity_threshold",
                            "threshold_used": threshold,
                            "metric_used": detected_metric
                        }
                    })

            logger.info(f"✅ THRESHOLD: Found {len(results)} results above threshold {threshold} using {detected_metric} metric")
            return results

        except Exception as e:
            logger.error(f"❌ THRESHOLD: Search failed with error: {e}")
            logger.error(f"❌ THRESHOLD: Collection: {self.collection_name}")
            return []
    
    def _multi_collection_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Search across multiple collections
        
        SECURITY: This method validates that only the project's own collection can be searched.
        Cross-project collection access is explicitly blocked to prevent data leakage.
        """
        try:
            collections = params["collections"]
            collection_weights = json.loads(params.get("collection_weights", "{}"))
            search_limit = params["search_limit_per_collection"]
            merge_strategy = params["merge_strategy"]
            
            # SECURITY: Validate and filter collections to only allow project's own collection
            # This prevents unauthorized cross-project document access
            validated_collections = []
            for collection in collections:
                if collection == "project_documents":
                    # Map to project's actual collection
                    validated_collections.append(("project_documents", self.collection_name))
                elif collection == self.collection_name:
                    # Allow explicit use of own collection name
                    validated_collections.append((collection, self.collection_name))
                else:
                    # SECURITY: Reject any other collection - potential cross-project access attempt
                    logger.warning(f"🚫 SECURITY: Rejected unauthorized collection access attempt: '{collection}' (allowed: 'project_documents' or '{self.collection_name}')")
                    continue
            
            if not validated_collections:
                logger.error("🚫 SECURITY: No valid collections to search after validation")
                return []
            
            logger.info(f"🔒 SECURITY: Validated {len(validated_collections)} collections for search (rejected {len(collections) - len(validated_collections)})")
            
            # Generate query embedding
            query_vector = self.embedding_service.encode_query(query)
            
            all_results = []
            
            # Search each validated collection
            for original_name, actual_collection in validated_collections:
                try:
                    # actual_collection is already validated to be project's own collection

                    detected_metric = self.get_collection_metric_type(actual_collection)
                    logger.debug(f"🔍 MULTI: Collection {actual_collection} uses {detected_metric} metric")

                    search_request = ChromaSearchRequest(
                        collection_name=actual_collection,
                        query_vectors=[query_vector],
                        limit=search_limit,
                        filter_expression=content_filter_expr if content_filter_expr and original_name == "project_documents" else "",
                        output_fields=["*"]  # Return all fields
                    )

                    search_result = self.search_service.search(search_request)
                    weight = collection_weights.get(original_name, 1.0)
                    
                    # Add weighted results
                    for hit in search_result.hits:
                        weighted_score = hit.get("score", 0.0) * weight
                        all_results.append({
                            "content": hit.get("content", ""),
                            "metadata": {
                                "source": hit.get("source", "Unknown"),
                                "page": hit.get("page", 1),
                                "score": weighted_score,
                                "original_score": hit.get("score", 0.0),
                                "weight": weight,
                                "chunk_type": hit.get("chunk_type", "text"),
                                "document_id": hit.get("document_id", ""),
                                "collection": original_name,
                                "search_method": "multi_collection"
                            }
                        })
                        
                except Exception as e:
                    logger.warning(f"❌ MULTI: Failed to search collection {actual_collection}: {e}")
                    continue
            
            # Apply merge strategy
            if merge_strategy == "weighted_merge":
                all_results.sort(key=lambda x: x["metadata"]["score"], reverse=True)
            elif merge_strategy == "top_k_merge":
                # Keep top results from each collection
                all_results.sort(key=lambda x: x["metadata"]["original_score"], reverse=True)
            # round_robin would need more complex logic
            
            logger.info(f"📚 MULTI: Found {len(all_results)} results across {len(validated_collections)} validated collections")
            return all_results[:search_limit * len(validated_collections)]
            
        except Exception as e:
            logger.error(f"❌ MULTI: Search failed: {e}")
            return []
    
    def _hierarchical_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Search with document hierarchy awareness using ChromaDB"""
        try:
            # This would require hierarchy metadata in the vector database
            # For now, implement as enhanced semantic search with structure preservation

            query_vector = self.embedding_service.encode_query(query)
            hierarchy_levels = params["hierarchy_levels"]
            level_weights = json.loads(params.get("level_weights", "{}"))

            # Create filter for hierarchy levels if available
            level_filter = " || ".join([f'chunk_type == "{level}"' for level in hierarchy_levels])

            detected_metric = self.get_collection_metric_type(self.collection_name)
            logger.info(f"🔍 HIERARCHICAL: Using metric: {detected_metric}")

            # Combine level filter with content filter
            combined_filter = ""
            if level_filter and content_filter_expr:
                combined_filter = f"({level_filter}) && ({content_filter_expr})"
            elif level_filter:
                combined_filter = level_filter
            elif content_filter_expr:
                combined_filter = content_filter_expr

            search_request = ChromaSearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                limit=params["search_limit"],
                filter_expression=combined_filter if combined_filter else "",
                output_fields=["*"]  # Return all fields
            )

            search_result = self.search_service.search(search_request)

            # Apply hierarchy weights
            results = []
            for hit in search_result.hits:
                chunk_type = hit.get("chunk_type", "text")
                weight = level_weights.get(chunk_type, 1.0)
                weighted_score = hit.get("score", 0.0) * weight

                results.append({
                    "content": hit.get("content", ""),
                    "metadata": {
                        "source": hit.get("source", hit.get("file_name", "Unknown")),
                        "page": hit.get("page", hit.get("page_number", 1)),
                        "score": weighted_score,
                        "original_score": hit.get("score", 0.0),
                        "hierarchy_weight": weight,
                        "chunk_type": chunk_type,
                        "document_id": hit.get("document_id", ""),
                        "collection": self.collection_name,
                        "search_method": "hierarchical_search",
                        "metric_used": detected_metric
                    }
                })

            # Sort by weighted score
            results.sort(key=lambda x: x["metadata"]["score"], reverse=True)

            logger.info(f"✅ HIERARCHICAL: Found {len(results)} results with hierarchy weighting using {detected_metric} metric")
            return results

        except Exception as e:
            logger.error(f"❌ HIERARCHICAL: Search failed with error: {e}")
            logger.error(f"❌ HIERARCHICAL: Collection: {self.collection_name}")
            return []
    
    def _keyword_search(self, query: str, params: Dict[str, Any], content_filter_expr: str = None) -> List[Dict[str, Any]]:
        """Perform keyword-based search using ChromaDB"""
        try:
            # This is a simplified keyword search implementation
            # In a full implementation, you'd use a text search engine like Elasticsearch

            search_limit = params["search_limit"]
            boost_exact = params["boost_exact_match"]
            min_length = params["min_keyword_length"]

            # Extract keywords
            keywords = [word.lower().strip() for word in query.split()
                       if len(word.strip()) >= min_length]

            if not keywords:
                logger.warning("📚 KEYWORD: No valid keywords found")
                return []

            detected_metric = self.get_collection_metric_type(self.collection_name)
            logger.info(f"🔍 KEYWORD: Using metric: {detected_metric}")

            # For now, use semantic search as fallback and simulate keyword scoring
            query_vector = self.embedding_service.encode_query(query)

            search_request = ChromaSearchRequest(
                collection_name=self.collection_name,
                query_vectors=[query_vector],
                limit=search_limit * 2,  # Get more to filter
                filter_expression=content_filter_expr if content_filter_expr else "",
                output_fields=["*"]  # Return all fields
            )

            search_result = self.search_service.search(search_request)

            # Score based on keyword matches
            results = []
            for hit in search_result.hits:
                content = hit.get("content", "").lower()

                # Count keyword matches
                exact_matches = sum(1 for keyword in keywords if keyword in content)
                partial_matches = sum(1 for keyword in keywords
                                    if any(keyword in word for word in content.split()))

                if exact_matches > 0 or partial_matches > 0:
                    # Calculate keyword score
                    keyword_score = (exact_matches * 2 + partial_matches) / len(keywords)
                    if boost_exact and exact_matches > 0:
                        keyword_score *= 1.5

                    results.append({
                        "content": hit.get("content", ""),
                        "metadata": {
                            "source": hit.get("source", hit.get("file_name", "Unknown")),
                            "page": hit.get("page", hit.get("page_number", 1)),
                            "score": keyword_score,
                            "exact_matches": exact_matches,
                            "partial_matches": partial_matches,
                            "chunk_type": hit.get("chunk_type", "text"),
                            "document_id": hit.get("document_id", ""),
                            "collection": self.collection_name,
                            "search_method": "keyword_search",
                            "keywords_used": keywords,
                            "metric_used": detected_metric
                        }
                    })

            # Sort by keyword score
            results.sort(key=lambda x: x["metadata"]["score"], reverse=True)
            results = results[:search_limit]

            logger.info(f"✅ KEYWORD: Found {len(results)} results for keywords: {keywords} using {detected_metric} metric")
            return results

        except Exception as e:
            logger.error(f"❌ KEYWORD: Search failed with error: {e}")
            logger.error(f"❌ KEYWORD: Collection: {self.collection_name}")
            return []
    
    def create_rag_function_for_agent(self, agent_config: Dict[str, Any]):
        """
        Create a RAG retrieval function for AutoGen agents
        
        Args:
            agent_config: Agent configuration with DocAware settings
            
        Returns:
            Function that can be used by agents for document retrieval
        """
        search_method = SearchMethod(agent_config.get('search_method', SearchMethod.HYBRID_SEARCH))
        method_parameters = agent_config.get('search_parameters', {})
        
        logger.info(f"📚 RAG FUNCTION: Creating function with {search_method.value} method")
        
        def retrieve_documents(query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
            """
            Retrieve relevant documents for agent query
            
            Args:
                query: Search query string
                limit: Override search limit
                
            Returns:
                List of relevant document chunks with metadata
            """
            try:
                # Override limit if provided
                params = method_parameters.copy()
                if limit:
                    if 'search_limit' in params:
                        params['search_limit'] = limit
                    elif 'max_results' in params:
                        params['max_results'] = limit
                
                # Perform search
                results = self.search_documents(
                    query=query,
                    search_method=search_method,
                    method_parameters=params,
                    conversation_context=self.conversation_context
                )
                
                logger.info(f"📚 RAG RETRIEVAL: Found {len(results)} documents for query: '{query[:50]}...'")
                return results
                
            except Exception as e:
                logger.error(f"📚 RAG RETRIEVAL: Failed: {e}")
                return []
        
        return retrieve_documents
    
    def update_conversation_context(self, new_context: List[str]):
        """Update conversation context for future searches"""
        self.conversation_context = new_context[-10:]  # Keep last 10 turns
        logger.debug(f"📚 CONTEXT: Updated with {len(self.conversation_context)} turns")
    
    def get_available_collections(self) -> List[str]:
        """
        Get list of available collections for multi-collection search.
        Only project_documents is allowed (backend enforces this in _multi_collection_search
        for project isolation); other collection names are rejected.
        """
        return ["project_documents"]
    
    def get_hierarchical_paths(self, include_files: bool = False) -> List[Dict[str, Any]]:
        """
        Get unique hierarchical paths for content filtering from ChromaDB collection

        Args:
            include_files: If True, include individual file entries alongside folders

        Returns:
            List of folder entries (and optionally file entries)
        """
        try:
            # Return empty list early if collection does not exist (documents not processed yet)
            try:
                existing = self.search_service.list_collections()
            except Exception:
                existing = []
            if self.collection_name not in existing:
                logger.info(f"📚 HIERARCHICAL PATHS: Collection '{self.collection_name}' not created yet (run Start Processing). Returning empty list.")
                return []

            logger.info(f"📚 HIERARCHICAL PATHS: Getting paths (include_files={include_files}) for {self.collection_name}")

            # Create search request to get all documents
            dummy_query = [0.0] * 384  # 384-dimensional zero vector for all-MiniLM-L6-v2

            search_request = ChromaSearchRequest(
                collection_name=self.collection_name,
                query_vectors=[dummy_query],
                limit=10000,  # High limit to get all documents
                output_fields=["hierarchical_path", "document_id", "file_name"]  # Get additional fields for files
            )

            # Perform search
            search_result = self.search_service.search(search_request)

            # Extract unique folder paths and files
            unique_folder_paths = set()
            unique_files = {}  # Map: document_id -> file info

            for hit in search_result.hits:
                hierarchical_path = hit.get("hierarchical_path", "")
                document_id = hit.get("document_id", "")
                file_name = hit.get("file_name", "Unknown")

                if hierarchical_path and hierarchical_path.strip():
                    clean_path = hierarchical_path.strip().strip('/')

                    if clean_path:
                        # Extract folder path (remove #chunk_XXX suffix)
                        if '#chunk_' in clean_path:
                            file_path = clean_path.split('#chunk_')[0]
                            folder_path = '/'.join(file_path.split('/')[:-1])

                            # Add all parent folder paths
                            if folder_path:
                                unique_folder_paths.add(folder_path)
                                path_parts = folder_path.split('/')
                                for i in range(1, len(path_parts)):
                                    parent_path = '/'.join(path_parts[:i])
                                    if parent_path:
                                        unique_folder_paths.add(parent_path)

                            # Track file for optional inclusion
                            if include_files and document_id and document_id not in unique_files:
                                unique_files[document_id] = {
                                    'document_id': document_id,
                                    'file_name': file_name,
                                    'file_path': file_path,
                                    'folder_path': folder_path
                                }

            # Build result list
            result_list = []

            # Add folders
            for folder_path in sorted(unique_folder_paths):
                result_list.append({
                    "id": f"folder_{folder_path}",
                    "name": folder_path.split('/')[-1],
                    "path": folder_path,
                    "type": "folder",
                    "displayName": folder_path,
                    "isFolder": True
                })

            # Add files if requested
            if include_files:
                for doc_id, file_info in sorted(unique_files.items(), key=lambda x: x[1]['file_name']):
                    result_list.append({
                        "id": f"file_{doc_id}",
                        "name": file_info['file_name'],
                        "path": file_info['file_path'],
                        "type": "file",
                        "displayName": f"{file_info['folder_path']}/{file_info['file_name']}" if file_info['folder_path'] else file_info['file_name'],
                        "isFolder": False,
                        "document_id": doc_id
                    })

            logger.info(f"📚 HIERARCHICAL PATHS: Found {len(result_list)} entries (folders: {len([r for r in result_list if r['isFolder']])}, files: {len([r for r in result_list if not r['isFolder']])})")
            if result_list:
                logger.info(f"📚 HIERARCHICAL PATHS: Sample paths: {[f['displayName'] for f in result_list[:5]]}")

            return result_list

        except Exception as e:
            # Check if this is a collection not found error (expected when documents haven't been processed)
            error_message = str(e)
            is_collection_not_found = (
                'not exist' in error_message.lower() or 
                'SchemaNotReadyException' in str(type(e).__name__) or
                'collection' in error_message.lower() and ('not found' in error_message.lower() or 'not exist' in error_message.lower())
            )
            
            if is_collection_not_found:
                # Collection doesn't exist yet - this is expected when documents haven't been processed
                logger.warning(f"📚 HIERARCHICAL PATHS: Collection '{self.collection_name}' does not exist yet. Documents may not have been processed. Returning empty list.")
                return []
            else:
                # Unexpected error - log as error
                logger.error(f"📚 HIERARCHICAL PATHS: Failed to get paths: {e}")
                import traceback
                logger.error(f"📚 HIERARCHICAL PATHS: Traceback: {traceback.format_exc()}")
                return []

