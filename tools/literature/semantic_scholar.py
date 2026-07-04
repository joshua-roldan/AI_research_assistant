"""Semantic Scholar literature search integration.

Queries the Semantic Scholar paper search API and returns normalized
``Paper`` objects. No API key is required for basic use.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .paper import Paper

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = (
    "title,authors,year,abstract,externalIds,url,paperId,venue,journal,"
    "citationCount,fieldsOfStudy"
)


def search_semantic_scholar(query: str, *, limit: int = 25) -> list[Paper]:
    """Search Semantic Scholar for papers matching a free-text query.

    Args:
        query: Search terms (e.g. ``"osteology deep learning"``).
        limit: Maximum number of results to return (default 25).

    Returns:
        A list of ``Paper`` objects parsed from the Semantic Scholar response.

    Raises:
        urllib.error.URLError: On network failure.
        urllib.error.HTTPError: If the API returns an error status (e.g. 429).
    """
    params = urllib.parse.urlencode(
        {
            "query": query,
            "limit": limit,
            "fields": SEMANTIC_SCHOLAR_FIELDS,
        }
    )
    url = f"{SEMANTIC_SCHOLAR_API}?{params}"

    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.load(response)

    return [Paper.from_semantic_scholar(work) for work in payload.get("data", [])]
