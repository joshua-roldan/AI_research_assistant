"""Build a Neo4j knowledge graph from Qdrant paper embeddings.

Reads embedded papers from Qdrant, creates Paper/Author/Topic/Venue nodes,
and links papers with ``SIMILAR_TO`` relationships derived from vector
similarity.
"""

from __future__ import annotations

import os
from typing import Any

from neo4j import Driver
from qdrant_client import QdrantClient

from ..literature.paper import Paper
from ..literature.qdrant_store import (
    DEFAULT_COLLECTION,
    get_qdrant_client,
    paper_point_id,
)
from ..code_repos.code_repo import CodeRepository

from .neo4j_client import ensure_constraints, get_neo4j_driver


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _paper_from_payload(payload: dict[str, Any]) -> Paper:
    return Paper(
        title=payload.get("title") or "",
        authors=payload.get("authors") or [],
        year=payload.get("year"),
        abstract=payload.get("abstract"),
        doi=payload.get("doi"),
        url=payload.get("url"),
        source_id=payload.get("source_id"),
        source=payload.get("source") or "unknown",
        venue=payload.get("venue"),
        citation_count=payload.get("citation_count"),
        topics=payload.get("topics") or [],
    )


def fetch_embedded_papers(
    *,
    collection_name: str | None = None,
    qdrant_client: QdrantClient | None = None,
) -> list[dict[str, Any]]:
    """Load all embedded papers and vectors from Qdrant.

    Args:
        collection_name: Qdrant collection to read from.
        qdrant_client: Optional preconfigured Qdrant client.

    Returns:
        List of dicts with ``id``, ``paper``, and ``vector`` keys.
    """
    collection = collection_name or os.environ.get(
        "QDRANT_COLLECTION", DEFAULT_COLLECTION
    )
    qdrant = qdrant_client or get_qdrant_client()

    if not qdrant.collection_exists(collection):
        return []

    records: list[dict[str, Any]] = []
    offset = None

    while True:
        points, offset = qdrant.scroll(
            collection_name=collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        for point in points:
            if not point.payload or not point.vector:
                continue
            records.append(
                {
                    "id": str(point.id),
                    "paper": _paper_from_payload(point.payload),
                    "vector": point.vector,
                }
            )
        if offset is None:
            break

    return records


def _upsert_paper_graph(tx, paper: Paper, qdrant_id: str) -> None:
    paper_id = paper_point_id(paper)
    tx.run(
        """
        MERGE (p:Paper {id: $id})
        SET p.title = $title,
            p.year = $year,
            p.abstract = $abstract,
            p.doi = $doi,
            p.url = $url,
            p.source = $source,
            p.source_id = $source_id,
            p.citation_count = $citation_count,
            p.qdrant_id = $qdrant_id
        """,
        id=paper_id,
        title=paper.title,
        year=paper.year,
        abstract=paper.abstract,
        doi=paper.doi,
        url=paper.url,
        source=paper.source,
        source_id=paper.source_id,
        citation_count=paper.citation_count,
        qdrant_id=qdrant_id,
    )

    for author in paper.authors:
        tx.run(
            """
            MATCH (p:Paper {id: $paper_id})
            MERGE (a:Author {name: $name})
            MERGE (a)-[:AUTHORED]->(p)
            """,
            paper_id=paper_id,
            name=author,
        )

    for topic in paper.topics:
        tx.run(
            """
            MATCH (p:Paper {id: $paper_id})
            MERGE (t:Topic {name: $name})
            MERGE (p)-[:HAS_TOPIC]->(t)
            """,
            paper_id=paper_id,
            name=topic,
        )

    if paper.venue:
        tx.run(
            """
            MATCH (p:Paper {id: $paper_id})
            MERGE (v:Venue {name: $name})
            MERGE (p)-[:PUBLISHED_IN]->(v)
            """,
            paper_id=paper_id,
            name=paper.venue,
        )


def _upsert_similarity_edge(
    tx,
    source_id: str,
    target_id: str,
    score: float,
) -> None:
    tx.run(
        """
        MATCH (source:Paper {id: $source_id})
        MATCH (target:Paper {id: $target_id})
        MERGE (source)-[r:SIMILAR_TO]->(target)
        SET r.score = $score
        """,
        source_id=source_id,
        target_id=target_id,
        score=score,
    )


def build_graph_from_embeddings(
    embedded_papers: list[dict[str, Any]],
    *,
    driver: Driver | None = None,
    similarity_threshold: float = 0.75,
    max_similar_links: int = 5,
) -> dict[str, int]:
    """Create Neo4j nodes and relationships from embedded paper records.

    Args:
        embedded_papers: Records from ``fetch_embedded_papers`` with ``id``,
            ``paper``, and ``vector`` keys.
        driver: Optional preconfigured Neo4j driver.
        similarity_threshold: Minimum cosine similarity for ``SIMILAR_TO`` edges.
        max_similar_links: Maximum similar-paper links created per paper.

    Returns:
        Counts of papers, authors, topics, venues, and similarity edges written.
    """
    if not embedded_papers:
        return {
            "papers": 0,
            "authors": 0,
            "topics": 0,
            "venues": 0,
            "similarity_edges": 0,
        }

    neo4j = driver or get_neo4j_driver()
    ensure_constraints(neo4j)

    paper_ids: list[str] = []
    with neo4j.session() as session:
        for record in embedded_papers:
            paper = record["paper"]
            paper_id = paper_point_id(paper)
            paper_ids.append(paper_id)
            session.execute_write(_upsert_paper_graph, paper, record["id"])

        similarity_edges = 0
        for index, source in enumerate(embedded_papers):
            source_id = paper_point_id(source["paper"])
            scores: list[tuple[str, float]] = []

            for target_index, target in enumerate(embedded_papers):
                if index == target_index:
                    continue
                score = _cosine_similarity(source["vector"], target["vector"])
                if score >= similarity_threshold:
                    scores.append((paper_point_id(target["paper"]), score))

            scores.sort(key=lambda item: item[1], reverse=True)
            for target_id, score in scores[:max_similar_links]:
                session.execute_write(
                    _upsert_similarity_edge,
                    source_id,
                    target_id,
                    score,
                )
                similarity_edges += 1

    authors = {name for record in embedded_papers for name in record["paper"].authors}
    topics = {name for record in embedded_papers for name in record["paper"].topics}
    venues = {
        record["paper"].venue
        for record in embedded_papers
        if record["paper"].venue
    }

    return {
        "papers": len(embedded_papers),
        "authors": len(authors),
        "topics": len(topics),
        "venues": len(venues),
        "similarity_edges": similarity_edges,
    }


def build_graph_from_qdrant(
    *,
    collection_name: str | None = None,
    qdrant_client: QdrantClient | None = None,
    driver: Driver | None = None,
    similarity_threshold: float = 0.75,
    max_similar_links: int = 5,
) -> dict[str, int]:
    """Fetch embedded papers from Qdrant and build the Neo4j knowledge graph.

    Args:
        collection_name: Qdrant collection to read from.
        qdrant_client: Optional preconfigured Qdrant client.
        driver: Optional preconfigured Neo4j driver.
        similarity_threshold: Minimum cosine similarity for ``SIMILAR_TO`` edges.
        max_similar_links: Maximum similar-paper links created per paper.

    Returns:
        Counts of graph elements written.
    """
    embedded_papers = fetch_embedded_papers(
        collection_name=collection_name,
        qdrant_client=qdrant_client,
    )
    return build_graph_from_embeddings(
        embedded_papers,
        driver=driver,
        similarity_threshold=similarity_threshold,
        max_similar_links=max_similar_links,
    )


def _upsert_repository_graph(tx, repo: CodeRepository) -> None:
    repo_id = repo.source_id or repo.full_name or repo.name
    tx.run(
        """
        MERGE (r:CodeRepository {id: $id})
        SET r.name = $name,
            r.full_name = $full_name,
            r.url = $url,
            r.description = $description,
            r.language = $language,
            r.stars = $stars,
            r.forks = $forks,
            r.license = $license,
            r.source = $source
        """,
        id=repo_id,
        name=repo.name,
        full_name=repo.full_name,
        url=repo.url,
        description=repo.description,
        language=repo.language,
        stars=repo.stars,
        forks=repo.forks,
        license=repo.license,
        source=repo.source,
    )

    for topic in repo.topics:
        tx.run(
            """
            MATCH (r:CodeRepository {id: $repo_id})
            MERGE (t:Topic {name: $name})
            MERGE (r)-[:HAS_TOPIC]->(t)
            """,
            repo_id=repo_id,
            name=topic,
        )


def upsert_repositories(
    repositories: list[CodeRepository],
    *,
    driver: Driver | None = None,
) -> int:
    """Add or update code repository nodes in Neo4j.

    Args:
        repositories: GitHub repositories to store in the graph.
        driver: Optional preconfigured Neo4j driver.

    Returns:
        Number of repositories upserted.
    """
    if not repositories:
        return 0

    neo4j = driver or get_neo4j_driver()
    ensure_constraints(neo4j)

    with neo4j.session() as session:
        for repo in repositories:
            session.execute_write(_upsert_repository_graph, repo)

    return len(repositories)
