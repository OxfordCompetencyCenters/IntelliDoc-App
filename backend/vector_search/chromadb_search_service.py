"""
ChromaDB Search Service
=======================

Singleton search service replacing ``MilvusSearchService`` from
``django_milvus_search/services.py``.

This service is consumed primarily by the DocAware RAG pipeline
(``agent_orchestration/docaware/service.py``) which constructs
``SearchRequest``-style objects with Milvus filter expressions.
The ``_parse_filter_expression`` method translates those expressions
into ChromaDB ``where`` clauses so that no changes are needed on the
calling side.
"""

import re as regex
import time
import logging
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

import chromadb
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes (mirror django_milvus_search.models)
# ---------------------------------------------------------------------------

@dataclass
class ChromaSearchRequest:
    """
    Search request compatible with the ``SearchRequest`` interface from
    ``django_milvus_search.models``.

    Fields intentionally kept as a superset so that existing callers
    can pass ``index_type`` / ``metric_type`` without error — those
    fields are simply ignored since ChromaDB uses a single HNSW+cosine
    index.
    """
    collection_name: str
    query_vectors: List[List[float]]
    limit: int = 10
    offset: int = 0
    output_fields: List[str] = field(default_factory=list)
    filter_expression: str = ""
    # Accepted but ignored — kept for interface compatibility
    index_type: Any = None
    metric_type: Any = None
    search_params: Any = None


@dataclass
class ChromaSearchResult:
    """
    Search result compatible with ``SearchResult`` from
    ``django_milvus_search.models``.
    """
    hits: List[Dict[str, Any]]
    search_time: float
    total_results: int
    algorithm_used: str = "HNSW+cosine"
    parameters_used: Dict[str, Any] = field(default_factory=dict)
    collection_name: str = ""
    query_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (matches Milvus SearchResult API)."""
        return {
            "hits": self.hits,
            "search_time": self.search_time,
            "total_results": self.total_results,
            "algorithm_used": self.algorithm_used,
            "parameters_used": self.parameters_used,
            "collection_name": self.collection_name,
            "query_id": self.query_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


# ---------------------------------------------------------------------------
# Singleton service
# ---------------------------------------------------------------------------

class ChromaDBSearchService:
    """
    Singleton ChromaDB search service replacing ``MilvusSearchService``.

    The DocAware RAG service instantiates this as::

        self.milvus_service = MilvusSearchService()

    After the migration shim swaps the import, the same code will do::

        self.milvus_service = ChromaDBSearchService()

    All public methods (``search``, ``batch_search``, ``get_collection_info``,
    ``list_collections``, ``health_check``, ``get_metrics``, ``reset_metrics``)
    are compatible.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config=None, max_workers: int = 10,
                 enable_monitoring: bool = True):
        """
        Accept (and ignore) the same ``config`` / ``max_workers`` /
        ``enable_monitoring`` kwargs that ``MilvusSearchService.__init__``
        accepts, so that callers do not need to change.
        """
        if self._initialized:
            return
        self._initialized = True
        self.enable_monitoring = enable_monitoring

        persist_dir = str(getattr(settings, 'CHROMADB_PERSIST_DIR', './chromadb_data'))
        self.client = chromadb.PersistentClient(path=persist_dir)

        self._metrics: Dict[str, Any] = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_search_time': 0.0,
            'connections_created': 1,  # always "connected" — embedded DB
            'errors': 0,
        }
        logger.info(f"ChromaDBSearchService initialized (persist: {persist_dir})")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, request) -> ChromaSearchResult:
        """
        Execute a single vector search.

        *request* may be either a ``ChromaSearchRequest`` or the original
        ``django_milvus_search.models.SearchRequest`` — we duck-type the
        attributes we need.
        """
        start_time = time.time()
        self._metrics['total_searches'] += 1

        # Duck-type request attributes
        collection_name = getattr(request, 'collection_name', '')
        query_vectors = getattr(request, 'query_vectors', [])
        limit = getattr(request, 'limit', 10)
        filter_expression = getattr(request, 'filter_expression', '') or ''
        output_fields = getattr(request, 'output_fields', [])

        try:
            collection = self.client.get_collection(name=collection_name)

            query_params: Dict[str, Any] = {
                'query_embeddings': query_vectors,
                'n_results': limit,
            }

            # Parse Milvus-style filter expression into ChromaDB where clause
            if filter_expression:
                where = self._parse_filter_expression(filter_expression)
                if where:
                    query_params['where'] = where

            results = collection.query(**query_params)

            hits: List[Dict[str, Any]] = []
            if results and results['ids']:
                for batch_idx, id_batch in enumerate(results['ids']):
                    for i, doc_id in enumerate(id_batch):
                        distance = (
                            results['distances'][batch_idx][i]
                            if results.get('distances') else 0.0
                        )
                        hit: Dict[str, Any] = {
                            'id': doc_id,
                            'distance': distance,
                            # For cosine distance: score = 1 - distance
                            # For IP in Milvus the score IS the distance.
                            # We provide both so callers can pick.
                            'score': 1.0 - distance,
                        }

                        # Merge metadata fields into the hit (flat, like Milvus)
                        if results.get('metadatas'):
                            meta = results['metadatas'][batch_idx][i] or {}
                            hit.update(meta)

                        # Add content
                        if results.get('documents'):
                            content = results['documents'][batch_idx][i] or ''
                            hit['content'] = content

                        hits.append(hit)

            search_time = time.time() - start_time
            self._metrics['successful_searches'] += 1
            self._metrics['total_search_time'] += search_time

            if self.enable_monitoring:
                logger.info(
                    f"Search completed in {search_time:.4f}s, "
                    f"found {len(hits)} results in '{collection_name}'"
                )

            return ChromaSearchResult(
                hits=hits,
                search_time=search_time,
                total_results=len(hits),
                collection_name=collection_name,
                parameters_used={'n_results': limit},
            )

        except Exception as e:
            self._metrics['failed_searches'] += 1
            self._metrics['errors'] += 1
            search_time = time.time() - start_time
            logger.error(f"Search failed on '{collection_name}': {e}")
            return ChromaSearchResult(
                hits=[],
                search_time=search_time,
                total_results=0,
                collection_name=collection_name,
            )

    def batch_search(self, requests: List) -> List[ChromaSearchResult]:
        """Execute multiple searches sequentially."""
        return [self.search(req) for req in requests]

    # ------------------------------------------------------------------
    # Collection info
    # ------------------------------------------------------------------

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get collection metadata (compatible with MilvusSearchService)."""
        try:
            collection = self.client.get_collection(name=collection_name)
            return {
                'name': collection_name,
                'num_entities': collection.count(),
                'count': collection.count(),
                'metadata': collection.metadata or {},
                # Provide a stub so callers checking for indexes don't crash
                'indexes': [],
                'is_loaded': True,  # always loaded — embedded DB
            }
        except Exception as e:
            return {'name': collection_name, 'error': str(e)}

    def list_collections(self) -> List[str]:
        """List all collection names."""
        try:
            collections = self.client.list_collections()
            return [c.name if hasattr(c, 'name') else str(c) for c in collections]
        except Exception:
            return []

    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        try:
            collections = self.list_collections()
            return {
                'status': 'healthy',
                'collections_count': len(collections),
                'backend': 'chromadb_persistent',
                'metrics': self._metrics.copy(),
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'metrics': self._metrics.copy(),
            }

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics (compatible with MilvusSearchService)."""
        metrics = self._metrics.copy()
        if metrics['successful_searches'] > 0:
            metrics['average_search_time'] = (
                metrics['total_search_time'] / metrics['successful_searches']
            )
        else:
            metrics['average_search_time'] = 0.0
        if metrics['total_searches'] > 0:
            metrics['success_rate'] = (
                metrics['successful_searches'] / metrics['total_searches']
            )
        else:
            metrics['success_rate'] = 0.0
        return metrics

    def reset_metrics(self):
        """Reset performance metrics."""
        self._metrics = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_search_time': 0.0,
            'connections_created': 1,
            'errors': 0,
        }

    def shutdown(self):
        """No-op for interface compatibility — ChromaDB PersistentClient
        needs no explicit shutdown."""
        logger.info("ChromaDBSearchService shutdown (no-op for embedded DB)")

    # ------------------------------------------------------------------
    # Milvus filter expression parser
    # ------------------------------------------------------------------

    def _parse_filter_expression(self, expr: str) -> Optional[Dict]:
        """
        Parse Milvus-style filter expressions into ChromaDB ``where`` clauses.

        The DocAware service builds expressions such as::

            document_id == "abc123"
            file_type in ["pdf", "docx"]
            document_id == "abc" and file_type == "pdf"
            hierarchy_level > 2
            category != "draft"

        Milvus uses ``&&`` as the AND operator in some places while DocAware's
        ``build_content_filter_expression_impl`` uses `` and ``.  We handle
        both.

        Returns ``None`` if the expression cannot be parsed.
        """
        if not expr or not expr.strip():
            return None

        expr = expr.strip()

        # Normalise Milvus-style && to 'and'
        expr = expr.replace('&&', ' and ')
        # Normalise Milvus-style || to 'or'
        expr = expr.replace('||', ' or ')

        # Handle compound AND conditions
        if ' and ' in expr.lower():
            # Split carefully (case-insensitive) while keeping the parts
            parts = regex.split(r'\s+and\s+', expr, flags=regex.IGNORECASE)
            conditions = []
            for part in parts:
                parsed = self._parse_single_condition(part.strip())
                if parsed:
                    conditions.append(parsed)
            if len(conditions) == 0:
                return None
            if len(conditions) == 1:
                return conditions[0]
            return {"$and": conditions}

        # Handle compound OR conditions
        if ' or ' in expr.lower():
            parts = regex.split(r'\s+or\s+', expr, flags=regex.IGNORECASE)
            conditions = []
            for part in parts:
                parsed = self._parse_single_condition(part.strip())
                if parsed:
                    conditions.append(parsed)
            if len(conditions) == 0:
                return None
            if len(conditions) == 1:
                return conditions[0]
            return {"$or": conditions}

        return self._parse_single_condition(expr)

    def _parse_single_condition(self, condition: str) -> Optional[Dict]:
        """Parse a single Milvus filter condition into a ChromaDB where dict."""
        condition = condition.strip()
        if not condition:
            return None

        # ---- field in ["val1", "val2"] / field in ['val1', 'val2'] ----
        in_match = regex.match(
            r'(\w+)\s+in\s+\[(.+?)\]', condition, regex.IGNORECASE
        )
        if in_match:
            field_name = in_match.group(1)
            values_str = in_match.group(2)
            values = [v.strip().strip("'\"") for v in values_str.split(',')]
            return {field_name: {"$in": values}}

        # ---- field == "value" / field == 'value' ----
        eq_str_match = regex.match(r'(\w+)\s*==\s*["\'](.+?)["\']', condition)
        if eq_str_match:
            return {eq_str_match.group(1): {"$eq": eq_str_match.group(2)}}

        # ---- field == number ----
        eq_num_match = regex.match(r'(\w+)\s*==\s*(-?\d+(?:\.\d+)?)', condition)
        if eq_num_match:
            field_name = eq_num_match.group(1)
            val = float(eq_num_match.group(2))
            if val == int(val):
                val = int(val)
            return {field_name: {"$eq": val}}

        # ---- field == true / field == false (bool) ----
        eq_bool_match = regex.match(
            r'(\w+)\s*==\s*(true|false)', condition, regex.IGNORECASE
        )
        if eq_bool_match:
            field_name = eq_bool_match.group(1)
            val = eq_bool_match.group(2).lower() == 'true'
            return {field_name: {"$eq": val}}

        # ---- field != "value" ----
        ne_str_match = regex.match(r'(\w+)\s*!=\s*["\'](.+?)["\']', condition)
        if ne_str_match:
            return {ne_str_match.group(1): {"$ne": ne_str_match.group(2)}}

        # ---- field != number ----
        ne_num_match = regex.match(r'(\w+)\s*!=\s*(-?\d+(?:\.\d+)?)', condition)
        if ne_num_match:
            field_name = ne_num_match.group(1)
            val = float(ne_num_match.group(2))
            if val == int(val):
                val = int(val)
            return {field_name: {"$ne": val}}

        # ---- field >= / <= / > / < number ----
        cmp_match = regex.match(
            r'(\w+)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)', condition
        )
        if cmp_match:
            field_name = cmp_match.group(1)
            op_map = {'>': '$gt', '>=': '$gte', '<': '$lt', '<=': '$lte'}
            op = op_map[cmp_match.group(2)]
            val = float(cmp_match.group(3))
            if val == int(val):
                val = int(val)
            return {field_name: {op: val}}

        # ---- field like "pattern%" (Milvus LIKE → ChromaDB has no LIKE,
        #      but we can approximate startsWith via no-op or log) ----
        like_match = regex.match(
            r'(\w+)\s+like\s+["\'](.+?)["\']', condition, regex.IGNORECASE
        )
        if like_match:
            field_name = like_match.group(1)
            pattern = like_match.group(2)
            # ChromaDB does not support LIKE. If the pattern is a simple
            # prefix match (e.g., "Reports/%"), we cannot translate it
            # directly.  Log a warning and skip.
            logger.warning(
                f"ChromaDB does not support LIKE filters. "
                f"Ignoring condition: {condition}"
            )
            return None

        logger.warning(f"Could not parse filter condition: '{condition}'")
        return None
