"""Store and search paper embeddings in Qdrant.

Embeds ``Paper`` objects with an OpenAI-compatible API (SCADS AI by default)
and upserts vectors plus metadata into a Qdrant collection.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .paper import Paper

DEFAULT_COLLECTION = "papers"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_EMBEDDING_BASE_URL = "https://llm.scads.ai/v1"


def _load_api_key() -> str:
    """Load an API key from env vars or the SCADS key file."""
    for env_name in ("OPENAI_API_KEY", "SCADS_API_KEY"):
        value = os.environ.get(env_name)
        if value:
            return value

    for path in (
        os.path.join(os.path.expanduser("~"), ".scadsai-api-key"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".scadsai-api-key"),
    ):
        if os.path.exists(path):
            with open(path) as keyfile:
                key = keyfile.readline().strip()
                if key and not key.startswith("#"):
                    return key

    raise ValueError(
        "No embedding API key found. Set OPENAI_API_KEY or SCADS_API_KEY, "
        "or create ~/.scadsai-api-key."
    )


def get_embedding_client() -> OpenAI:
    """Create an OpenAI-compatible client for embedding requests."""
    return OpenAI(
        api_key=_load_api_key(),
        base_url=os.environ.get("EMBEDDING_BASE_URL", DEFAULT_EMBEDDING_BASE_URL),
    )


def get_qdrant_client() -> QdrantClient:
    """Create a Qdrant client from environment configuration."""
    url = os.environ.get("QDRANT_URL", DEFAULT_QDRANT_URL)
    api_key = os.environ.get("QDRANT_API_KEY")
    return QdrantClient(url=url, api_key=api_key)


def paper_point_id(paper: Paper) -> str:
    """Return a stable UUID for a paper based on DOI, source ID, or title."""
    key = paper.doi or paper.source_id or paper.title
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
    client: OpenAI | None = None,
) -> list[list[float]]:
    """Generate embedding vectors for a list of texts.

    Args:
        texts: Strings to embed.
        model: Embedding model name. Defaults to ``EMBEDDING_MODEL`` env var or
            ``text-embedding-3-small``.
        client: Optional preconfigured OpenAI-compatible client.

    Returns:
        Embedding vectors in the same order as ``texts``.
    """
    if not texts:
        return []

    embedding_client = client or get_embedding_client()
    embedding_model = model or os.environ.get(
        "EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
    )
    response = embedding_client.embeddings.create(
        input=texts,
        model=embedding_model,
    )
    return [item.embedding for item in response.data]


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    """Create the Qdrant collection if it does not already exist."""
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def embed_papers(
    papers: list[Paper],
    *,
    collection_name: str | None = None,
    model: str | None = None,
    qdrant_client: QdrantClient | None = None,
    embedding_client: OpenAI | None = None,
) -> list[str]:
    """Embed papers and upsert them into Qdrant.

    Args:
        papers: Papers to index.
        collection_name: Target Qdrant collection. Defaults to ``QDRANT_COLLECTION``
            env var or ``papers``.
        model: Embedding model name.
        qdrant_client: Optional preconfigured Qdrant client.
        embedding_client: Optional preconfigured embedding client.

    Returns:
        Point IDs written to Qdrant, in the same order as ``papers``.
    """
    if not papers:
        return []

    collection = collection_name or os.environ.get(
        "QDRANT_COLLECTION", DEFAULT_COLLECTION
    )
    qdrant = qdrant_client or get_qdrant_client()
    texts = [paper.embedding_text() for paper in papers]
    vectors = embed_texts(texts, model=model, client=embedding_client)

    ensure_collection(qdrant, collection, len(vectors[0]))

    points = [
        PointStruct(
            id=paper_point_id(paper),
            vector=vector,
            payload=paper.to_dict(),
        )
        for paper, vector in zip(papers, vectors)
    ]
    qdrant.upsert(collection_name=collection, points=points)

    return [paper_point_id(paper) for paper in papers]


def search_similar_papers(
    query: str,
    *,
    limit: int = 10,
    collection_name: str | None = None,
    model: str | None = None,
    qdrant_client: QdrantClient | None = None,
    embedding_client: OpenAI | None = None,
) -> list[dict[str, Any]]:
    """Search indexed papers by semantic similarity to a query string.

    Args:
        query: Free-text search query.
        limit: Maximum number of results to return.
        collection_name: Qdrant collection to search.
        model: Embedding model name.
        qdrant_client: Optional preconfigured Qdrant client.
        embedding_client: Optional preconfigured embedding client.

    Returns:
        List of dicts with ``score`` and ``paper`` keys.
    """
    collection = collection_name or os.environ.get(
        "QDRANT_COLLECTION", DEFAULT_COLLECTION
    )
    qdrant = qdrant_client or get_qdrant_client()
    vector = embed_texts([query], model=model, client=embedding_client)[0]

    hits = qdrant.search(
        collection_name=collection,
        query_vector=vector,
        limit=limit,
    )

    return [
        {
            "score": hit.score,
            "paper": hit.payload,
            "id": hit.id,
        }
        for hit in hits
    ]
