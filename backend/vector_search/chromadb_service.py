"""
ChromaDB Project Vector Database
================================

Drop-in replacement for MilvusProjectVectorDatabase using ChromaDB PersistentClient.
Provides per-project collection management, document insertion, search, and deletion.

ChromaDB stores data on disk — no external server required, ideal for Electron desktop apps.
"""

import chromadb
from django.conf import settings
import uuid
import re
import logging
import time
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level ChromaDB client (singleton)
# ---------------------------------------------------------------------------
_chroma_client = None


def get_chroma_client():
    """
    Return a module-level ChromaDB PersistentClient singleton.

    The persist directory is read from ``settings.CHROMADB_PERSIST_DIR``
    (default ``./chromadb_data``).
    """
    global _chroma_client
    if _chroma_client is None:
        persist_dir = str(getattr(settings, 'CHROMADB_PERSIST_DIR', './chromadb_data'))
        _chroma_client = chromadb.PersistentClient(path=persist_dir)
        logger.info(f"ChromaDB PersistentClient initialized at {persist_dir}")
    return _chroma_client


def create_project_vector_database(project_id: str) -> 'ChromaDBProjectVectorDatabase':
    """Factory function matching the Milvus interface."""
    return ChromaDBProjectVectorDatabase(project_id)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class ChromaDBProjectVectorDatabase:
    """
    Per-project vector database backed by a ChromaDB collection.

    This class mirrors the public API of ``MilvusProjectVectorDatabase`` so that
    callers (document processing pipeline, DocAware RAG, etc.) can switch
    backends without code changes.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = get_chroma_client()
        self.collection_name = self._generate_collection_name()
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # cosine similarity
        )
        logger.info(
            f"ChromaDB collection '{self.collection_name}' ready "
            f"(count: {self.collection.count()})"
        )

    # ------------------------------------------------------------------
    # Collection name generation
    # ------------------------------------------------------------------

    def _generate_collection_name(self) -> str:
        """
        Generate a ChromaDB-safe collection name for the project.

        Tries to look up the project name from the database (matching the
        Milvus implementation) and falls back to a UUID-based name.

        ChromaDB collection name rules:
        - 3-63 characters long
        - Starts and ends with an alphanumeric character
        - Contains only alphanumeric characters, underscores, or hyphens
        """
        try:
            from users.models import IntelliDocProject, ProjectVectorCollection

            project = IntelliDocProject.objects.get(project_id=self.project_id)

            # Check if a stored collection name exists
            try:
                vector_collection = ProjectVectorCollection.objects.get(project=project)
                stored_name = vector_collection.collection_name
                # Sanitise for ChromaDB
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', stored_name)
                if len(safe_name) > 63:
                    safe_name = safe_name[:63]
                # Ensure valid start/end
                safe_name = safe_name.strip('_') or f"proj_{self.project_id[:8]}"
                logger.info(
                    f"Using stored collection name '{safe_name}' for project "
                    f"'{project.name}' (ID: {self.project_id})"
                )
                return safe_name
            except Exception:
                pass

            # Build from project name
            sanitized = re.sub(r'[^a-zA-Z0-9]', '', project.name.lower())
            if not sanitized or sanitized[0].isdigit():
                sanitized = f"project_{sanitized}"
            if len(sanitized) > 20:
                sanitized = sanitized[:20]
            safe_id = self.project_id.replace('-', '_')
            name = f"{sanitized}_{safe_id}"
            if len(name) > 63:
                name = name[:63]
            # Ensure valid start/end characters
            name = name.strip('_') or f"proj_{self.project_id[:8]}"
            logger.info(
                f"Generated collection name '{name}' for project "
                f"'{project.name}' (ID: {self.project_id})"
            )
            return name

        except Exception as e:
            logger.warning(
                f"Failed to get project name for {self.project_id}: {e}. "
                f"Falling back to generic collection name."
            )
            safe_id = re.sub(r'[^a-zA-Z0-9_]', '_', str(self.project_id))
            name = f"project_{safe_id}"
            if len(name) > 63:
                name = name[:63]
            name = name.strip('_') or f"proj_{self.project_id[:8]}"
            return name

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def batch_insert_document_chunks(self, chunks_data: List[Any], document_name: str) -> bool:
        """
        Insert all chunks for a document.

        Each element of *chunks_data* may be either:
        - A dict with keys ``embedding``, ``content``, and flat metadata fields, or
        - An object with ``.embedding``, ``.content``, and ``.metadata`` attributes
          (the format produced by the existing document processing pipeline).

        Returns ``True`` on success, ``False`` on failure.
        """
        try:
            start_time = time.time()
            ids: List[str] = []
            embeddings: List[List[float]] = []
            documents: List[str] = []
            metadatas: List[Dict[str, Any]] = []

            for chunk in chunks_data:
                # ----- Normalise chunk access (dict vs object) -----
                if isinstance(chunk, dict):
                    chunk_id = chunk.get('chunk_id') or str(uuid.uuid4())
                    embedding = chunk.get('embedding', [])
                    content = str(chunk.get('content', ''))
                    raw_meta = {k: v for k, v in chunk.items()
                                if k not in ('embedding', 'content', 'chunk_id')}
                else:
                    # Object with .embedding, .content, .metadata attributes
                    chunk_id = (
                        getattr(chunk, 'chunk_id', None)
                        or (chunk.metadata.get('chunk_id') if hasattr(chunk, 'metadata') else None)
                        or str(uuid.uuid4())
                    )
                    embedding = getattr(chunk, 'embedding', [])
                    content = str(getattr(chunk, 'content', ''))
                    raw_meta = dict(getattr(chunk, 'metadata', {}))

                ids.append(str(chunk_id))

                # Convert numpy arrays to plain lists
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
                embeddings.append(embedding)

                documents.append(content)

                # Build metadata dict — ChromaDB only supports str, int, float, or bool
                meta: Dict[str, Any] = {}
                metadata_keys = [
                    'document_id', 'file_name', 'file_type', 'file_size',
                    'content_length', 'chunk_index', 'total_chunks', 'chunk_type',
                    'section_title', 'hierarchical_path', 'hierarchy_level',
                    'virtual_path', 'category', 'subcategory', 'document_type',
                    'is_complete_document', 'vector_id', 'has_embedding',
                    'processing_time_ms', 'uploaded_at', 'organization_level',
                    'error_message',
                ]
                for key in metadata_keys:
                    val = raw_meta.get(key)
                    if val is not None:
                        if isinstance(val, (str, int, float, bool)):
                            meta[key] = val
                        else:
                            meta[key] = str(val)

                # Ensure essential fields are always present
                if 'document_id' not in meta:
                    meta['document_id'] = raw_meta.get('document_id', document_name)
                if 'file_name' not in meta:
                    meta['file_name'] = document_name

                metadatas.append(meta)

            if not ids:
                logger.warning(f"No chunks to insert for document '{document_name}'")
                return True

            # ChromaDB upsert handles duplicates gracefully
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

            elapsed = time.time() - start_time
            logger.info(
                f"Inserted {len(ids)} chunks for '{document_name}' into "
                f"'{self.collection_name}' in {elapsed:.2f}s"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to insert chunks for '{document_name}': {e}")
            return False

    def insert_document(self, doc_info) -> bool:
        """
        Insert a single document (legacy interface).

        Delegates to ``batch_insert_document_chunks`` with a one-element list so
        that the normalisation logic is shared.
        """
        file_name = 'unknown'
        if hasattr(doc_info, 'metadata'):
            file_name = doc_info.metadata.get('file_name', 'unknown')
        return self.batch_insert_document_chunks([doc_info], file_name)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_documents(
        self,
        query_vector,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search documents by vector similarity with optional metadata filtering.

        Returns a list of result dicts compatible with the Milvus output format,
        including ``id``, ``content``, ``distance``, ``score``, and all stored
        metadata fields.
        """
        try:
            if isinstance(query_vector, np.ndarray):
                query_vector = query_vector.tolist()

            query_params: Dict[str, Any] = {
                'query_embeddings': [query_vector],
                'n_results': limit,
            }

            # Convert filter dict to ChromaDB where clause
            if filters:
                where = self._build_where_clause(filters)
                if where:
                    query_params['where'] = where

            results = self.collection.query(**query_params)

            # Format results to match Milvus output shape
            formatted: List[Dict[str, Any]] = []
            if results and results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if results['distances'] else 0.0
                    content = results['documents'][0][i] if results['documents'] else ''

                    formatted.append({
                        'id': doc_id,
                        'content': content,
                        'distance': distance,
                        'score': 1.0 - distance,  # cosine distance -> similarity
                        'similarity': 1.0 - distance,  # alias used by Milvus caller
                        **metadata,
                    })

            return formatted

        except Exception as e:
            logger.error(f"Search failed in '{self.collection_name}': {e}")
            return []

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete_document(self, document_id: str) -> bool:
        """Delete all chunks belonging to a specific document."""
        try:
            self.collection.delete(where={"document_id": {"$eq": document_id}})
            logger.info(
                f"Deleted document '{document_id}' from collection "
                f"'{self.collection_name}'"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete document '{document_id}': {e}")
            return False

    def delete_collection(self) -> bool:
        """Delete the entire collection for this project."""
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted collection '{self.collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{self.collection_name}': {e}")
            return False

    # ------------------------------------------------------------------
    # Stats / Info
    # ------------------------------------------------------------------

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            count = self.collection.count()
            return {
                'collection_name': self.collection_name,
                'name': self.collection_name,
                'count': count,
                'total_documents': count,
                'project_id': self.project_id,
                'storage_type': 'ChromaDB PersistentClient',
            }
        except Exception as e:
            logger.error(f"Failed to get stats for '{self.collection_name}': {e}")
            return {
                'collection_name': self.collection_name,
                'name': self.collection_name,
                'count': 0,
                'total_documents': 0,
                'project_id': self.project_id,
                'error': str(e),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_where_clause(self, filters: Dict[str, Any]) -> Optional[Dict]:
        """
        Convert a filter dict to a ChromaDB ``where`` clause.

        Supports:
        - Simple equality: ``{"field": "value"}``
        - ``$in`` lists:   ``{"field": ["a", "b"]}``
        - Operator dicts:  ``{"field": {"$eq": "value"}}`` (passed through)
        """
        if not filters:
            return None

        conditions: List[Dict] = []
        for key, value in filters.items():
            if isinstance(value, dict):
                # Already a ChromaDB operator dict — pass through
                conditions.append({key: value})
            elif isinstance(value, list):
                conditions.append({key: {"$in": value}})
            elif isinstance(value, str):
                conditions.append({key: {"$eq": value}})
            elif isinstance(value, (int, float)):
                conditions.append({key: {"$eq": value}})
            elif isinstance(value, bool):
                conditions.append({key: {"$eq": value}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}


# Compatibility alias
ProjectVectorDatabase = create_project_vector_database
