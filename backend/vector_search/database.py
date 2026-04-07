# Vector Database - ChromaDB Implementation (Electron Desktop)
# This module re-exports the ChromaDB implementation to maintain backward compatibility
# with existing imports like `from vector_search.database import create_project_vector_database`

from .chromadb_service import (
    ChromaDBProjectVectorDatabase,
    create_project_vector_database,
    get_chroma_client,
)

# Backward-compatible alias
MilvusProjectVectorDatabase = ChromaDBProjectVectorDatabase
ProjectVectorDatabase = ChromaDBProjectVectorDatabase
