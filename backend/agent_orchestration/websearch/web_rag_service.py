"""
Web RAG Service
===============

Provides semantic search over cached web URL content using ChromaDB.
Chunks PageCapture sections -> embeds -> upserts into a per-project
ChromaDB collection -> searches with user query -> returns top-K chunks.
"""

import hashlib
import logging
import re
import uuid
from typing import Dict, List, Any, Optional

import chromadb
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('agent_orchestration')

# Lazy-loaded singletons (expensive to init)
_embedding_service = None
_chroma_client = None
_chroma_available = None

VECTOR_DIM = 384  # all-MiniLM-L6-v2
MAX_CHUNK_CHARS = 2000
MIN_CHUNK_CHARS = 20
INDEX_FLAG_PREFIX = "websearch_chromadb_idx_"


def _get_chroma_client():
    """Return a module-level ChromaDB PersistentClient singleton."""
    global _chroma_client
    if _chroma_client is None:
        persist_dir = str(getattr(settings, 'CHROMADB_PERSIST_DIR', './chromadb_data'))
        _chroma_client = chromadb.PersistentClient(path=persist_dir)
        logger.info(f"Web RAG: ChromaDB PersistentClient initialized at {persist_dir}")
    return _chroma_client


def _get_embedding_service():
    """Lazy-load the shared embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        from ..docaware.embedding_service import DocAwareEmbeddingService
        _embedding_service = DocAwareEmbeddingService()
    return _embedding_service


def _check_chromadb():
    """Check if ChromaDB is reachable (always True for PersistentClient)."""
    global _chroma_available
    try:
        client = _get_chroma_client()
        # Simple heartbeat -- list collections to verify the client is working
        client.list_collections()
        _chroma_available = True
    except Exception as e:
        logger.warning(f"WEB RAG: ChromaDB not available -- falling back to full content: {e}")
        _chroma_available = False
    return _chroma_available


def _collection_name(project_id: str) -> str:
    """Deterministic collection name for a project's web content."""
    safe_pid = re.sub(r'[^a-zA-Z0-9_]', '_', str(project_id))
    name = f"websearch_{safe_pid}"
    # ChromaDB collection names must be 3-63 chars
    if len(name) > 63:
        name = name[:63]
    # Ensure valid start/end (alphanumeric)
    name = name.strip('_') or f"ws_{safe_pid[:8]}"
    return name


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def _index_flag_key(project_id: str, url: str) -> str:
    safe_pid = str(project_id).replace('-', '_')
    return f"{INDEX_FLAG_PREFIX}{safe_pid}_{_url_hash(url)}"


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

def _get_or_create_collection(project_id: str):
    """Create (or open) the websearch ChromaDB collection for a project."""
    client = _get_chroma_client()
    name = _collection_name(project_id)
    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_page_capture(page: Dict[str, Any], url: str) -> List[Dict[str, Any]]:
    """
    Convert a PageCapture dict into embedding-ready chunks.

    Each section becomes a chunk. Non-heading sections get the nearest
    preceding heading prepended for context.  Very long sections are
    split at sentence boundaries.
    """
    sections = page.get('sections') or []
    title = (page.get('title') or '')[:500]
    chunks: List[Dict[str, Any]] = []
    current_heading = title  # fallback heading

    for idx, sec in enumerate(sections):
        sec_type = sec.get('type', 'other')
        text = (sec.get('text') or '').strip()
        if not text or len(text) < MIN_CHUNK_CHARS:
            # Update heading even if we skip the section
            if sec_type == 'heading':
                current_heading = text or current_heading
            continue

        if sec_type == 'heading':
            current_heading = text
            # Include heading as its own chunk only if substantial
            if len(text) >= MIN_CHUNK_CHARS:
                chunks.append({
                    'content': text,
                    'section_heading': text[:500],
                    'section_type': sec_type,
                    'chunk_index': idx,
                })
            continue

        # Prepend heading context for non-heading sections
        heading_prefix = f"{current_heading}\n\n" if current_heading else ""

        if len(heading_prefix) + len(text) <= MAX_CHUNK_CHARS:
            chunks.append({
                'content': (heading_prefix + text)[:MAX_CHUNK_CHARS],
                'section_heading': current_heading[:500],
                'section_type': sec_type,
                'chunk_index': idx,
            })
        else:
            # Split long sections at sentence boundaries
            for part in _split_text(text, MAX_CHUNK_CHARS - len(heading_prefix)):
                chunks.append({
                    'content': (heading_prefix + part)[:MAX_CHUNK_CHARS],
                    'section_heading': current_heading[:500],
                    'section_type': sec_type,
                    'chunk_index': idx,
                })

    # Add url / title metadata to every chunk
    uh = _url_hash(url)
    for c in chunks:
        c['url'] = url[:2048]
        c['url_hash'] = uh
        c['title'] = title
        c['word_count'] = len(c['content'].split())

    return chunks


def _split_text(text: str, max_len: int) -> List[str]:
    """Split text at sentence boundaries, keeping each part under max_len."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    parts: List[str] = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_len:
            current = f"{current} {s}".strip() if current else s
        else:
            if current:
                parts.append(current)
            current = s[:max_len]  # truncate individual sentence if needed
    if current:
        parts.append(current)
    return parts or [text[:max_len]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class WebRAGService:
    """Semantic search over cached web URL content via ChromaDB."""

    def is_available(self) -> bool:
        return _check_chromadb()

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    async def ensure_indexed(
        self,
        url: str,
        page_capture: Dict[str, Any],
        project_id: str,
        cache_ttl: int = 3600,
    ) -> bool:
        """
        Chunk + embed + upsert a PageCapture into ChromaDB if not already indexed.
        Returns True if newly indexed, False if already up-to-date.
        """
        flag_key = _index_flag_key(project_id, url)
        if cache.get(flag_key):
            return False  # already indexed and flag still alive

        from asgiref.sync import sync_to_async

        chunks = _chunk_page_capture(page_capture, url)
        if not chunks:
            logger.debug(f"WEB RAG: No chunks for {url[:60]}")
            return False

        try:
            # Embed all chunks
            texts = [c['content'] for c in chunks]
            embeddings = await sync_to_async(_get_embedding_service().batch_encode)(texts)

            # Get or create collection
            col = await sync_to_async(_get_or_create_collection)(project_id)

            # Delete old chunks for this URL (in case content changed)
            uh = _url_hash(url)
            try:
                await sync_to_async(col.delete)(where={"url_hash": {"$eq": uh}})
            except Exception:
                # Collection may be empty or url_hash field may not exist yet
                pass

            # Prepare ChromaDB upsert data
            ids = []
            documents = []
            metadatas = []

            for i, c in enumerate(chunks):
                chunk_id = f"{uh}_{i}_{uuid.uuid4().hex[:8]}"
                ids.append(chunk_id)
                documents.append(c['content'])
                metadatas.append({
                    'url': c['url'],
                    'url_hash': c['url_hash'],
                    'title': c['title'],
                    'section_heading': c['section_heading'],
                    'section_type': c['section_type'],
                    'chunk_index': c['chunk_index'],
                    'word_count': c['word_count'],
                })

            await sync_to_async(col.upsert)(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

            # Set index flag with same TTL as the URL cache
            cache.set(flag_key, 1, timeout=cache_ttl)

            logger.info(f"WEB RAG: Indexed {len(chunks)} chunks for {url[:60]} (project {str(project_id)[:8]})")
            return True

        except Exception as e:
            logger.error(f"WEB RAG: Failed to index {url[:60]}: {e}")
            return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        project_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Embed the query and search the websearch ChromaDB collection.
        Returns top-K chunks with content, url, section_heading, score.
        """
        from asgiref.sync import sync_to_async

        try:
            query_embedding = await sync_to_async(_get_embedding_service().encode_query)(query)

            col = await sync_to_async(_get_or_create_collection)(project_id)

            results = await sync_to_async(col.query)(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            chunks = []
            if results and results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i] if results.get('distances') else 0.0
                    metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                    content = results['documents'][0][i] if results.get('documents') else ''
                    # Cosine distance -> similarity score
                    score = round(1.0 - distance, 4)

                    chunks.append({
                        'content': content,
                        'url': metadata.get('url', ''),
                        'title': metadata.get('title', ''),
                        'section_heading': metadata.get('section_heading', ''),
                        'section_type': metadata.get('section_type', ''),
                        'word_count': metadata.get('word_count', 0),
                        'score': score,
                    })

            logger.info(f"WEB RAG: Found {len(chunks)} chunks for query '{query[:50]}...' (project {str(project_id)[:8]})")
            return chunks

        except Exception as e:
            logger.error(f"WEB RAG: Search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_indexed_urls(self, project_id: str) -> List[str]:
        """Return distinct URLs currently indexed in the project's ChromaDB collection."""
        from asgiref.sync import sync_to_async
        try:
            client = _get_chroma_client()
            name = _collection_name(project_id)

            # Check if collection exists
            existing = [c.name if hasattr(c, 'name') else str(c) for c in client.list_collections()]
            if name not in existing:
                return []

            col = await sync_to_async(_get_or_create_collection)(project_id)

            # Get all entries to extract URLs
            # ChromaDB does not support SELECT DISTINCT, so we fetch metadata
            results = await sync_to_async(col.get)(
                include=["metadatas"],
                limit=16384,
            )

            urls = set()
            if results and results.get('metadatas'):
                for meta in results['metadatas']:
                    if meta and meta.get('url'):
                        urls.add(meta['url'])

            return list(urls)
        except Exception as e:
            logger.warning(f"WEB RAG: Failed to get indexed URLs: {e}")
            return []

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def remove_url(self, url: str, project_id: str):
        """Delete all ChromaDB chunks for a single URL."""
        from asgiref.sync import sync_to_async
        try:
            col = await sync_to_async(_get_or_create_collection)(project_id)
            uh = _url_hash(url)
            await sync_to_async(col.delete)(where={"url_hash": {"$eq": uh}})
            cache.delete(_index_flag_key(project_id, url))
            logger.info(f"WEB RAG: Removed chunks for {url[:60]}")
        except Exception as e:
            logger.warning(f"WEB RAG: Failed to remove URL chunks: {e}")

    async def clear_project(self, project_id: str):
        """Drop the entire websearch collection for a project."""
        from asgiref.sync import sync_to_async
        try:
            client = _get_chroma_client()
            name = _collection_name(project_id)

            existing = [c.name if hasattr(c, 'name') else str(c) for c in client.list_collections()]
            if name in existing:
                await sync_to_async(client.delete_collection)(name=name)
                logger.info(f"WEB RAG: Dropped collection {name}")
            else:
                logger.debug(f"WEB RAG: No collection to drop for {name}")
        except Exception as e:
            logger.warning(f"WEB RAG: Failed to drop collection: {e}")
