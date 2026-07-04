"""OpenAlex literature search integration.

Queries the OpenAlex works API and returns normalized ``Paper`` objects.
No API key is required; see https://openalex.org for usage guidelines.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .paper import Paper

OPENALEX_API = "https://api.openalex.org/works"


def search_openalex(query: str, *, per_page: int = 25) -> list[Paper]:
    """Search OpenAlex for works matching a free-text query.

    Args:
        query: Search terms (e.g. ``"bone species image classification"``).
        per_page: Maximum number of results to return (default 25).

    Returns:
        A list of ``Paper`` objects parsed from the OpenAlex response.

    Raises:
        urllib.error.URLError: On network failure.
        urllib.error.HTTPError: If the OpenAlex API returns an error status.
    """
    params = urllib.parse.urlencode(
        {
            "search": query,
            "per_page": per_page,
            "mailto": "bone-research-agent@example.com",
        }
    )
    url = f"{OPENALEX_API}?{params}"

    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.load(response)

    return [Paper.from_openalex(work) for work in payload.get("results", [])]
