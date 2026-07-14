"""Export Neo4j knowledge graph data for Cytoscape.js visualization."""

from __future__ import annotations

from typing import Any

from neo4j import Driver

from ..code_repos.code_repo import CodeRepository
from ..knowledge_graph.build_graph import _cosine_similarity
from ..knowledge_graph.neo4j_client import get_neo4j_driver
from ..literature.paper import Paper
from ..literature.qdrant_store import paper_point_id

NODE_COLORS = {
    "Paper": "#4A90D9",
    "Author": "#7BC96F",
    "Topic": "#F9C74F",
    "Venue": "#F8961E",
    "CodeRepository": "#C084FC",
}

NODE_QUERY = """
MATCH (n)
RETURN labels(n) AS labels, properties(n) AS props
"""

EDGE_QUERY = """
MATCH (source)-[relationship]->(target)
RETURN
    labels(source) AS source_labels,
    properties(source) AS source_props,
    type(relationship) AS relationship_type,
    properties(relationship) AS relationship_props,
    labels(target) AS target_labels,
    properties(target) AS target_props
"""


def _node_label(node_type: str, props: dict[str, Any]) -> str:
    if node_type == "Paper":
        title = props.get("title") or "Untitled paper"
        return title if len(title) <= 60 else f"{title[:57]}..."
    if node_type == "CodeRepository":
        return props.get("full_name") or props.get("name") or "Repository"
    return props.get("name") or props.get("title") or node_type


def _node_id(node_type: str, props: dict[str, Any]) -> str | None:
    if node_type == "Paper":
        value = props.get("id")
    elif node_type == "CodeRepository":
        value = props.get("id") or props.get("full_name") or props.get("name")
    else:
        value = props.get("name")
    if not value:
        return None
    return f"{node_type.lower()}:{value}"


def _build_node(node_type: str, props: dict[str, Any]) -> dict[str, Any] | None:
    element_id = _node_id(node_type, props)
    if not element_id:
        return None

    return {
        "data": {
            "id": element_id,
            "label": _node_label(node_type, props),
            "type": node_type,
            "color": NODE_COLORS.get(node_type, "#999999"),
            **props,
        }
    }


def _add_edge(
    edges: list[dict[str, Any]],
    edge_index: int,
    source_id: str,
    target_id: str,
    label: str,
    **props: Any,
) -> int:
    edge_index += 1
    edges.append(
        {
            "data": {
                "id": f"edge:{edge_index}",
                "source": source_id,
                "target": target_id,
                "label": label,
                **props,
            }
        }
    )
    return edge_index


def build_cytoscape_from_search_results(
    papers: list[Paper],
    repositories: list[CodeRepository],
    *,
    paper_vectors: list[list[float]] | None = None,
    similarity_threshold: float = 0.75,
    max_similar_links: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """Build Cytoscape elements directly from search results.

    Useful when Neo4j is unavailable. Creates the same node and edge types as
    the Neo4j graph builder.
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    edge_index = 0

    def ensure_node(node_type: str, props: dict[str, Any]) -> str | None:
        node = _build_node(node_type, props)
        if not node:
            return None
        nodes[node["data"]["id"]] = node
        return node["data"]["id"]

    for paper in papers:
        paper_id = paper_point_id(paper)
        paper_node_id = ensure_node(
            "Paper",
            {
                "id": paper_id,
                "title": paper.title,
                "year": paper.year,
                "abstract": paper.abstract,
                "doi": paper.doi,
                "url": paper.url,
                "source": paper.source,
                "source_id": paper.source_id,
                "citation_count": paper.citation_count,
            },
        )
        if not paper_node_id:
            continue

        for author in paper.authors:
            author_id = ensure_node("Author", {"name": author})
            if author_id:
                edge_index = _add_edge(
                    edges, edge_index, author_id, paper_node_id, "AUTHORED"
                )

        for topic in paper.topics:
            topic_id = ensure_node("Topic", {"name": topic})
            if topic_id:
                edge_index = _add_edge(
                    edges, edge_index, paper_node_id, topic_id, "HAS_TOPIC"
                )

        if paper.venue:
            venue_id = ensure_node("Venue", {"name": paper.venue})
            if venue_id:
                edge_index = _add_edge(
                    edges, edge_index, paper_node_id, venue_id, "PUBLISHED_IN"
                )

    if paper_vectors and len(paper_vectors) == len(papers):
        for index, source_vector in enumerate(paper_vectors):
            source_id = paper_point_id(papers[index])
            scores: list[tuple[str, float]] = []
            for target_index, target_vector in enumerate(paper_vectors):
                if index == target_index:
                    continue
                score = _cosine_similarity(source_vector, target_vector)
                if score >= similarity_threshold:
                    scores.append((paper_point_id(papers[target_index]), score))
            scores.sort(key=lambda item: item[1], reverse=True)
            for target_id, score in scores[:max_similar_links]:
                edge_index = _add_edge(
                    edges,
                    edge_index,
                    source_id,
                    target_id,
                    "SIMILAR_TO",
                    score=score,
                )

    for repo in repositories:
        repo_id_value = repo.source_id or repo.full_name or repo.name
        repo_node_id = ensure_node(
            "CodeRepository",
            {
                "id": repo_id_value,
                "name": repo.name,
                "full_name": repo.full_name,
                "url": repo.url,
                "description": repo.description,
                "language": repo.language,
                "stars": repo.stars,
                "forks": repo.forks,
                "license": repo.license,
                "source": repo.source,
            },
        )
        if not repo_node_id:
            continue

        for topic in repo.topics:
            topic_id = ensure_node("Topic", {"name": topic})
            if topic_id:
                edge_index = _add_edge(
                    edges, edge_index, repo_node_id, topic_id, "HAS_TOPIC"
                )

    return {"nodes": list(nodes.values()), "edges": edges}


def fetch_cytoscape_elements(
    *,
    driver: Driver | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Load nodes and edges from Neo4j in Cytoscape.js element format.

    Args:
        driver: Optional preconfigured Neo4j driver.

    Returns:
        Dict with ``nodes`` and ``edges`` lists for Cytoscape.js.
    """
    neo4j = driver or get_neo4j_driver()
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    with neo4j.session() as session:
        for record in session.run(NODE_QUERY):
            labels = record["labels"] or []
            props = record["props"] or {}
            node_type = labels[0] if labels else "Unknown"
            node = _build_node(node_type, props)
            if node:
                nodes[node["data"]["id"]] = node

        edge_index = 0
        for record in session.run(EDGE_QUERY):
            source_labels = record["source_labels"] or []
            target_labels = record["target_labels"] or []
            source_type = source_labels[0] if source_labels else "Unknown"
            target_type = target_labels[0] if target_labels else "Unknown"
            source_props = record["source_props"] or {}
            target_props = record["target_props"] or {}
            source_id = _node_id(source_type, source_props)
            target_id = _node_id(target_type, target_props)
            if not source_id or not target_id:
                continue

            relationship_type = record["relationship_type"]
            relationship_props = record["relationship_props"] or {}
            edge_index = _add_edge(
                edges,
                edge_index,
                source_id,
                target_id,
                relationship_type,
                **relationship_props,
            )

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
    }
