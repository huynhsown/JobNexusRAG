"""
Job-domain Chroma collections (cv_chunks / jd_chunks).

Shared by matching and job ingestion; no Docling/LLM dependency.
"""
from __future__ import annotations

from app.services.vector_store import VectorStore

CV_COLLECTION = "cv_chunks"
JD_COLLECTION = "jd_chunks"

# Workspace id for DeepDocumentParser output paths (docling artifacts)
_JOB_PLATFORM_WORKSPACE_ID = 9999


class _NamedVectorStore(VectorStore):
    """VectorStore subclass that uses a fixed collection name instead of kb_{id}."""

    def __init__(self, name: str):
        self.workspace_id = 0
        self.collection_name = name
        self._collection = None


def get_cv_vector_store() -> VectorStore:
    """ChromaDB collection for CV chunks (shared across all candidates)."""
    return _NamedVectorStore(CV_COLLECTION)


def get_jd_vector_store() -> VectorStore:
    """ChromaDB collection for JD chunks (shared across all jobs)."""
    return _NamedVectorStore(JD_COLLECTION)


# Backward-compatible names for imports from copied services
def _get_cv_vector_store() -> VectorStore:
    return get_cv_vector_store()


def _get_jd_vector_store() -> VectorStore:
    return get_jd_vector_store()


_KG_WORKSPACE_ID = _JOB_PLATFORM_WORKSPACE_ID
