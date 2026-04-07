"""
Search Methods Configuration for DocAware Agents
===============================================

Defines available search methods and their parameter configurations
for document-aware agents using the ChromaDB Search backend.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

class SearchMethod(str, Enum):
    """Available search methods for DocAware agents"""
    SEMANTIC_SEARCH = "semantic_search"
    HYBRID_SEARCH = "hybrid_search" 
    KEYWORD_SEARCH = "keyword_search"
    CONTEXTUAL_SEARCH = "contextual_search"
    SIMILARITY_THRESHOLD = "similarity_threshold"
    MULTI_COLLECTION = "multi_collection"
    HIERARCHICAL_SEARCH = "hierarchical_search"

@dataclass
class SearchMethodConfig:
    """Configuration for each search method"""
    name: str
    description: str
    parameters: Dict[str, Any]
    default_values: Dict[str, Any]
    requires_embedding: bool = True

class DocAwareSearchMethods:
    """Registry of available search methods and their configurations"""
    
    METHODS = {
        SearchMethod.SEMANTIC_SEARCH: SearchMethodConfig(
            name="Semantic Search",
            description="Vector similarity search using embeddings for semantic understanding",
            parameters={
                "search_limit": {
                    "type": "number",
                    "min": 1,
                    "max": 100,
                    "description": "Maximum number of results to return"
                },
                "relevance_threshold": {
                    "type": "number",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "description": "Minimum relevance score threshold"
                }
            },
            default_values={
                "search_limit": 5,
                "relevance_threshold": 0.7
            }
        ),
        
        SearchMethod.HYBRID_SEARCH: SearchMethodConfig(
            name="Hybrid Search",
            description="Combines semantic search with keyword filtering for precise results",
            parameters={
                "search_limit": {
                    "type": "number",
                    "min": 1,
                    "max": 50,
                    "description": "Maximum semantic results"
                },
                "keyword_weight": {
                    "type": "number",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "description": "Weight for keyword matching (0=semantic only, 1=keyword only)"
                },
                "filter_expression": {
                    "type": "text",
                    "description": "Filter expression (e.g., 'document_type == \"pdf\"')"
                }
            },
            default_values={
                "search_limit": 10,
                "keyword_weight": 0.3,
                "filter_expression": ""
            }
        ),
        
        SearchMethod.CONTEXTUAL_SEARCH: SearchMethodConfig(
            name="Contextual Search", 
            description="Search with conversation context for more relevant results",
            parameters={
                "context_window": {
                    "type": "number",
                    "min": 1,
                    "max": 10,
                    "description": "Number of recent conversation turns to use as context"
                },
                "context_weight": {
                    "type": "number",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "description": "Weight for conversation context in search"
                },
                "search_limit": {
                    "type": "number",
                    "min": 1,
                    "max": 50,
                    "description": "Maximum results to return"
                },
                "relevance_threshold": {
                    "type": "number",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "description": "Minimum relevance score"
                }
            },
            default_values={
                "context_window": 3,
                "context_weight": 0.4,
                "search_limit": 8,
                "relevance_threshold": 0.6
            }
        ),
        
        SearchMethod.SIMILARITY_THRESHOLD: SearchMethodConfig(
            name="Similarity Threshold",
            description="Return all results above a specific similarity threshold",
            parameters={
                "similarity_threshold": {
                    "type": "number",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "description": "Minimum similarity score (higher = more strict)"
                },
                "max_results": {
                    "type": "number",
                    "min": 1,
                    "max": 200,
                    "description": "Maximum results to return even if above threshold"
                }
            },
            default_values={
                "similarity_threshold": 0.8,
                "max_results": 20
            }
        ),
        
        SearchMethod.MULTI_COLLECTION: SearchMethodConfig(
            name="Multi-Collection Search",
            description="Search across multiple document collections simultaneously. Only the project's document collection is searchable (project_documents).",
            parameters={
                "collections": {
                    "type": "multiselect",
                    "options": ["project_documents"],
                    "description": "Collections to search across (only project_documents is allowed for project isolation)"
                },
                "collection_weights": {
                    "type": "text",
                    "description": "JSON object with collection weights (e.g., {\"project_documents\": 1.0, \"knowledge_base\": 0.8})"
                },
                "search_limit_per_collection": {
                    "type": "number",
                    "min": 1,
                    "max": 20,
                    "description": "Max results per collection"
                },
                "merge_strategy": {
                    "type": "select",
                    "options": ["weighted_merge", "top_k_merge", "round_robin"],
                    "description": "How to combine results from multiple collections"
                }
            },
            default_values={
                "collections": ["project_documents"],
                "collection_weights": "{\"project_documents\": 1.0}",
                "search_limit_per_collection": 5,
                "merge_strategy": "weighted_merge"
            }
        ),
        
        SearchMethod.HIERARCHICAL_SEARCH: SearchMethodConfig(
            name="Hierarchical Search",
            description="Search with document hierarchy awareness (sections, chapters, etc.)",
            parameters={
                "hierarchy_levels": {
                    "type": "multiselect",
                    "options": ["document", "chapter", "section", "paragraph", "sentence"],
                    "description": "Hierarchy levels to include in search"
                },
                "level_weights": {
                    "type": "text",
                    "description": "JSON weights for each level (e.g., {\"document\": 0.2, \"section\": 0.8})"
                },
                "search_limit": {
                    "type": "number",
                    "min": 1,
                    "max": 30,
                    "description": "Maximum results to return"
                },
                "preserve_structure": {
                    "type": "boolean",
                    "description": "Maintain document structure in results"
                }
            },
            default_values={
                "hierarchy_levels": ["section", "paragraph"],
                "level_weights": "{\"section\": 0.6, \"paragraph\": 0.4}",
                "search_limit": 10,
                "preserve_structure": True
            }
        ),
        
        SearchMethod.KEYWORD_SEARCH: SearchMethodConfig(
            name="Keyword Search",
            description="Traditional keyword-based search with BM25 scoring",
            parameters={
                "search_limit": {
                    "type": "number",
                    "min": 1,
                    "max": 50,
                    "description": "Maximum results to return"
                },
                "boost_exact_match": {
                    "type": "boolean",
                    "description": "Give higher scores to exact keyword matches"
                },
                "min_keyword_length": {
                    "type": "number",
                    "min": 1,
                    "max": 10,
                    "description": "Minimum length for keywords to be considered"
                }
            },
            default_values={
                "search_limit": 10,
                "boost_exact_match": True,
                "min_keyword_length": 3
            },
            requires_embedding=False
        )
    }
    
    @classmethod
    def get_method_config(cls, method: SearchMethod) -> Optional[SearchMethodConfig]:
        """Get configuration for a specific search method"""
        return cls.METHODS.get(method)
    
    @classmethod
    def get_all_methods(cls) -> Dict[SearchMethod, SearchMethodConfig]:
        """Get all available search methods"""
        return cls.METHODS.copy()
    
    @classmethod
    def get_method_names(cls) -> List[str]:
        """Get list of method names for UI dropdown"""
        return [(method.value, config.name) for method, config in cls.METHODS.items()]
    
    @classmethod
    def validate_parameters(cls, method: SearchMethod, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean parameters for a search method"""
        config = cls.get_method_config(method)
        if not config:
            raise ValueError(f"Unknown search method: {method}")
        
        validated = {}
        for param_name, param_config in config.parameters.items():
            value = parameters.get(param_name, config.default_values.get(param_name))
            
            # Type validation and conversion
            if param_config["type"] == "number":
                try:
                    value = float(value) if "step" in param_config else int(value)
                    if "min" in param_config:
                        value = max(value, param_config["min"])
                    if "max" in param_config:
                        value = min(value, param_config["max"])
                except (ValueError, TypeError):
                    value = config.default_values.get(param_name, 0)
            
            elif param_config["type"] == "boolean":
                value = bool(value)
            
            elif param_config["type"] == "select":
                if value not in param_config["options"]:
                    value = config.default_values.get(param_name, param_config["options"][0])
            
            elif param_config["type"] == "multiselect":
                if not isinstance(value, list):
                    value = config.default_values.get(param_name, [])
                # Filter valid options
                value = [v for v in value if v in param_config["options"]]
            
            validated[param_name] = value
        
        return validated
