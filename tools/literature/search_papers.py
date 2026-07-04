"""Combined literature search across multiple sources.

Runs OpenAlex and Semantic Scholar in parallel (sequentially in code) and
deduplicates overlapping results into a single list of ``Paper`` objects.
"""

from .openalex import search_openalex
from .paper import Paper
from .semantic_scholar import search_semantic_scholar


def _dedupe_papers(papers: list[Paper]) -> list[Paper]:
    """Remove duplicate papers, preferring DOI, then source ID, then title.

    Args:
        papers: Papers from one or more search sources.

    Returns:
        Deduplicated papers in original encounter order.
    """
    seen: set[str] = set()
    unique: list[Paper] = []

    for paper in papers:
        key = paper.doi or paper.source_id or paper.title.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)

    return unique


def search_papers(query: str) -> list[Paper]:
    """Search literature across OpenAlex and Semantic Scholar.

    Args:
        query: Free-text search terms.

    Returns:
        Deduplicated list of ``Paper`` objects from both sources.
    """
    papers = search_openalex(query) + search_semantic_scholar(query)
    return _dedupe_papers(papers)


tool = {
    "name": "search_papers",
    "description": "Search scientific literature",
    "parameters": {
        "query": "string",
    },
}
