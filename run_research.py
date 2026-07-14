#!/usr/bin/env python3
"""Run a full bone-classification research search and open the knowledge graph."""

from __future__ import annotations

import os
import sys
import time
import urllib.error

from tools.code_repos import search_github
from tools.knowledge_graph.build_graph import (
    build_graph_from_embeddings,
    upsert_repositories,
)
from tools.knowledge_graph.neo4j_client import get_neo4j_driver
from tools.literature import search_openalex, search_semantic_scholar
from tools.literature.paper import Paper
from tools.literature.qdrant_store import embed_papers, embed_texts
from tools.visualization import build_cytoscape_from_search_results, visualize_elements

PAPER_QUERY = "AI bone classification machine learning image zooarchaeology"
REPO_QUERY = "AI bone classification machine learning image"
DEFAULT_NEO4J_PASSWORD = "research-agent"


def _dedupe_papers(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    unique: list[Paper] = []
    for paper in papers:
        key = paper.doi or paper.source_id or paper.title.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


def search_literature(query: str, *, per_source: int = 8) -> list[Paper]:
    papers: list[Paper] = []
    for name, search_fn, kwargs in (
        ("OpenAlex", search_openalex, {"per_page": per_source}),
        ("Semantic Scholar", search_semantic_scholar, {"limit": per_source}),
    ):
        try:
            results = search_fn(query, **kwargs)
            print(f"{name}: {len(results)} papers")
            papers.extend(results)
        except urllib.error.HTTPError as error:
            print(f"{name}: HTTP {error.code}")
        except urllib.error.URLError as error:
            print(f"{error}")
        time.sleep(1)
    return _dedupe_papers(papers)


def try_persist_to_neo4j(
    papers: list[Paper],
    repositories,
    paper_vectors: list[list[float]] | None,
    qdrant_ids: list[str] | None,
) -> bool:
    os.environ.setdefault("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD)
    try:
        driver = get_neo4j_driver()
        driver.verify_connectivity()
    except Exception as error:
        print(f"Neo4j unavailable ({error}); using in-memory graph.")
        return False

    embedded = []
    if qdrant_ids:
        embedded = [
            {"id": qdrant_id, "paper": paper, "vector": vector}
            for paper, qdrant_id, vector in zip(papers, qdrant_ids, paper_vectors or [])
            if vector is not None
        ]
    elif paper_vectors:
        embedded = [
            {"id": f"local:{index}", "paper": paper, "vector": vector}
            for index, (paper, vector) in enumerate(zip(papers, paper_vectors))
        ]

    if embedded:
        stats = build_graph_from_embeddings(embedded, driver=driver)
        print(f"Neo4j paper graph: {stats}")
    repo_count = upsert_repositories(repositories, driver=driver)
    print(f"Neo4j repositories upserted: {repo_count}")
    driver.close()
    return True


def main() -> int:
    print("=" * 72)
    print("Bone classification research pipeline")
    print("=" * 72)

    print("\nSearching literature...")
    papers = search_literature(PAPER_QUERY)
    print(f"Unique papers: {len(papers)}")
    for index, paper in enumerate(papers[:5], 1):
        print(f"  {index}. {paper.title} ({paper.year})")

    print("\nSearching GitHub repositories...")
    repositories = search_github(REPO_QUERY, per_page=8)
    print(f"Repositories: {len(repositories)}")
    for index, repo in enumerate(repositories[:5], 1):
        print(f"  {index}. {repo.full_name} ({repo.stars} stars)")

    paper_vectors: list[list[float]] | None = None
    qdrant_ids: list[str] | None = None

    print("\nGenerating embeddings...")
    try:
        qdrant_ids = embed_papers(papers)
        paper_vectors = embed_texts([paper.embedding_text() for paper in papers])
        print(f"Embedded {len(qdrant_ids)} papers in Qdrant.")
    except Exception as error:
        print(f"Qdrant/embeddings unavailable ({error}); trying embeddings only.")
        try:
            paper_vectors = embed_texts([paper.embedding_text() for paper in papers])
            print(f"Generated {len(paper_vectors)} local embedding vectors.")
        except Exception as embed_error:
            print(f"Embeddings unavailable ({embed_error}); graph will omit similarity edges.")

    used_neo4j = try_persist_to_neo4j(
        papers,
        repositories,
        paper_vectors,
        qdrant_ids,
    )

    if used_neo4j:
        from tools.visualization import visualize_knowledge_graph

        print("\nOpening Cytoscape visualization from Neo4j...")
        visualize_knowledge_graph(open_browser=True, block=True)
        return 0

    elements = build_cytoscape_from_search_results(
        papers,
        repositories,
        paper_vectors=paper_vectors,
    )
    print(
        f"\nIn-memory graph: {len(elements['nodes'])} nodes, "
        f"{len(elements['edges'])} edges."
    )
    print("Opening Cytoscape visualization...")
    visualize_elements(elements, open_browser=True, block=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
