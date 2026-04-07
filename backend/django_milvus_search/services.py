"""
Core Milvus search service for Django applications
"""
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Union
from contextlib import contextmanager
import threading
from django.conf import settings
from django.core.cache import cache

try:
    from pymilvus import connections, Collection, utility
    from pymilvus.exceptions import MilvusException
except ImportError:
    raise ImportError("pymilvus is required. Install with: pip install pymilvus")

from .models import (
    ConnectionConfig, SearchRequest, SearchResult, SearchParams,
    IndexType, MetricType
)
from .exceptions import (
    MilvusConnectionError, MilvusSearchError, MilvusConfigurationError,
    MilvusCollectionError
)

logger = logging.getLogger(__name__)


class MilvusSearchService:
    """
    Main service class for Milvus search operations in Django applications.
    
    Features:
    - Connection pooling and management
    - Thread-safe operations
    - Caching support
    - Comprehensive error handling
    - Django settings integration
    - Performance monitoring
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern implementation"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[ConnectionConfig] = None, 
                 max_workers: int = 10, enable_monitoring: bool = True):
        """
        Initialize Milvus search service
        
        Args:
            config: Connection configuration
            max_workers: Maximum number of worker threads
            enable_monitoring: Enable performance monitoring
        """
        if hasattr(self, '_initialized'):
            return
            
        self.config = config or self._get_config_from_settings()
        self.max_workers = max_workers
        self.enable_monitoring = enable_monitoring
        self.connections = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._connection_lock = threading.Lock()
        self._initialized = True
        
        # Performance monitoring
        self.metrics = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_search_time': 0.0,
            'connections_created': 0,
        }
        
        # Initialize default connection
        self._setup_connection()
    
    def _get_config_from_settings(self) -> ConnectionConfig:
        """Get configuration from Django settings"""
        try:
            milvus_settings = getattr(settings, 'MILVUS_CONFIG', {})
            return ConnectionConfig(**milvus_settings)
        except Exception as e:
            logger.warning(f"Failed to load Milvus config from settings: {e}")
            return ConnectionConfig()
    
    def _setup_connection(self, alias: str = "default") -> bool:
        """Setup connection to Milvus"""
        try:
            with self._connection_lock:
                if alias in self.connections:
                    return True
                
                connections.connect(
                    alias=alias,
                    **self.config.to_dict()
                )
                
                self.connections[alias] = True
                self.metrics['connections_created'] += 1
                logger.info(f"Connected to Milvus with alias '{alias}'")
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise MilvusConnectionError(f"Connection failed: {e}")
    
    @contextmanager
    def get_connection(self, alias: str = "default"):
        """Get a connection context manager"""
        try:
            if alias not in self.connections:
                self._setup_connection(alias)
            yield alias
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise MilvusConnectionError(f"Connection error: {e}")
    
    def search(self, request: SearchRequest) -> SearchResult:
        """
        Perform vector search
        
        Args:
            request: Search request object
            
        Returns:
            SearchResult object with results and metadata
        """
        start_time = time.time()
        self.metrics['total_searches'] += 1
        
        try:
            with self.get_connection() as conn_alias:
                collection = Collection(request.collection_name, using=conn_alias)
                
                # Check if collection exists and is loaded
                if not utility.has_collection(request.collection_name, using=conn_alias):
                    raise MilvusCollectionError(f"Collection '{request.collection_name}' does not exist")
                
                # Load collection if not loaded
                try:
                    collection.load()
                except Exception as e:
                    logger.debug(f"Collection already loaded or load failed: {e}")
                
                # Prepare search parameters
                search_params = {}
                if request.search_params:
                    search_params = request.search_params.to_dict()
                
                # Add index and metric type to search params
                search_params.update({
                    "metric_type": request.metric_type.value,
                })
                
                # Perform search
                search_start = time.time()
                
                # Auto-detect vector field name
                vector_field = self._detect_vector_field_name(collection)
                if not vector_field:
                    raise MilvusSearchError(f"No vector field found in collection {request.collection_name}")
                
                results = collection.search(
                    data=request.query_vectors,
                    anns_field=vector_field,  # Use detected field name
                    param=search_params,
                    limit=request.limit,
                    offset=request.offset,
                    output_fields=request.output_fields,
                    expr=request.filter_expression
                )
                search_time = time.time() - search_start
                
                # Process results
                hits = []
                total_results = len(results[0]) if results else 0
                
                for result in results:
                    for hit in result:
                        hit_data = {
                            "id": hit.id,
                            "distance": hit.distance,
                            "score": 1.0 - hit.distance if request.metric_type == MetricType.L2 else hit.distance,
                        }
                        
                        # Add output fields if available
                        if hasattr(hit, 'entity'):
                            for field, value in hit.entity.fields.items():
                                hit_data[field] = value
                        
                        hits.append(hit_data)
                
                # Create result object
                result_obj = SearchResult(
                    hits=hits,
                    search_time=search_time,
                    total_results=total_results,
                    algorithm_used=f"{request.index_type.value}+{request.metric_type.value}",
                    parameters_used=search_params,
                    collection_name=request.collection_name
                )
                
                self.metrics['successful_searches'] += 1
                self.metrics['total_search_time'] += search_time
                
                if self.enable_monitoring:
                    logger.info(f"Search completed in {search_time:.4f}s, found {total_results} results")
                    # Log project isolation info if collection name contains project ID
                    if request.collection_name and '_' in request.collection_name:
                        logger.debug(f"📦 PROJECT ISOLATION: Search performed on collection {request.collection_name} (thread-safe)")
                
                return result_obj
                
        except Exception as e:
            self.metrics['failed_searches'] += 1
            logger.error(f"Search failed: {e}")
            raise MilvusSearchError(f"Search operation failed: {e}")
        
        finally:
            total_time = time.time() - start_time
            if self.enable_monitoring:
                logger.debug(f"Total search operation time: {total_time:.4f}s")
    
    def batch_search(self, requests: List[SearchRequest]) -> List[SearchResult]:
        """
        Perform batch vector searches using thread pool
        
        Args:
            requests: List of search requests
            
        Returns:
            List of SearchResult objects
        """
        if not requests:
            return []
        
        results = []
        futures = []
        
        # Submit all search tasks
        for request in requests:
            future = self.executor.submit(self.search, request)
            futures.append((future, request))
        
        # Collect results as they complete
        for future, request in futures:
            try:
                result = future.result(timeout=self.config.timeout)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch search failed for collection {request.collection_name}: {e}")
                # Create error result
                error_result = SearchResult(
                    hits=[],
                    search_time=0.0,
                    total_results=0,
                    algorithm_used="FAILED",
                    parameters_used={},
                    collection_name=request.collection_name
                )
                results.append(error_result)
        
        return results
    
    def _detect_vector_field_name(self, collection) -> Optional[str]:
        """
        Automatically detect the vector field name in a collection
        
        Args:
            collection: Milvus Collection object
            
        Returns:
            Name of the vector field, or None if not found
        """
        try:
            schema = collection.schema
            
            # Look for vector fields (fields with vector data type)
            vector_fields = []
            embedding_fields = []
            
            for field in schema.fields:
                # Check if field is a vector field by data type
                if hasattr(field, 'dtype'):
                    # Common vector field types in Milvus
                    if field.dtype == 101:  # FLOAT_VECTOR
                        vector_fields.append(field.name)
                        logger.info(f"Found FLOAT_VECTOR field: {field.name}")
                    elif field.dtype == 100:  # BINARY_VECTOR
                        vector_fields.append(field.name)
                        logger.info(f"Found BINARY_VECTOR field: {field.name}")
                    elif 'embedding' in field.name.lower():
                        embedding_fields.append(field.name)
                        logger.info(f"Found embedding-named field: {field.name} (type: {field.dtype})")
            
            # Return properly typed vector fields first
            if vector_fields:
                return vector_fields[0]
            
            # If no properly typed vector fields, try embedding fields
            if embedding_fields:
                logger.info(f"Using embedding field: {embedding_fields[0]}")
                return embedding_fields[0]
            
            # If no explicit vector fields found, try common field names
            common_vector_names = ['vector', 'embedding', 'embeddings', 'vec', 'feature_vector', 'dense_vector']
            
            field_names = [field.name for field in schema.fields]
            logger.info(f"Available fields in collection {collection.name}: {field_names}")
            
            for common_name in common_vector_names:
                if common_name in field_names:
                    logger.info(f"Found vector field by name: {common_name}")
                    return common_name
            
            logger.warning(f"No vector field found in collection {collection.name}")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting vector field in collection {collection.name}: {e}")
            return None
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection"""
        try:
            with self.get_connection() as conn_alias:
                if not utility.has_collection(collection_name, using=conn_alias):
                    raise MilvusCollectionError(f"Collection '{collection_name}' does not exist")
                
                collection = Collection(collection_name, using=conn_alias)
                
                return {
                    "name": collection_name,
                    "num_entities": collection.num_entities,
                    "schema": collection.schema.to_dict(),
                    "indexes": collection.indexes,
                    "is_loaded": utility.loading_progress(collection_name, using=conn_alias)
                }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            raise MilvusCollectionError(f"Failed to get collection info: {e}")
    
    def list_collections(self) -> List[str]:
        """List all collections"""
        try:
            with self.get_connection() as conn_alias:
                return utility.list_collections(using=conn_alias)
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise MilvusCollectionError(f"Failed to list collections: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            collections = self.list_collections()
            return {
                "status": "healthy",
                "collections_count": len(collections),
                "metrics": self.metrics.copy(),
                "config": {
                    "host": self.config.host,
                    "port": self.config.port,
                    "max_workers": self.max_workers,
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "metrics": self.metrics.copy(),
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        metrics = self.metrics.copy()
        if metrics['successful_searches'] > 0:
            metrics['average_search_time'] = metrics['total_search_time'] / metrics['successful_searches']
        else:
            metrics['average_search_time'] = 0.0
        
        if metrics['total_searches'] > 0:
            metrics['success_rate'] = metrics['successful_searches'] / metrics['total_searches']
        else:
            metrics['success_rate'] = 0.0
        
        return metrics
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.metrics = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_search_time': 0.0,
            'connections_created': 0,
        }
    
    def shutdown(self):
        """Shutdown service and cleanup resources"""
        try:
            self.executor.shutdown(wait=True)
            
            for alias in list(self.connections.keys()):
                try:
                    connections.disconnect(alias)
                    logger.info(f"Disconnected from Milvus alias '{alias}'")
                except Exception as e:
                    logger.warning(f"Error disconnecting from alias '{alias}': {e}")
            
            self.connections.clear()
            logger.info("Milvus search service shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.shutdown()
        except:
            pass
