"""GitHub repository search integration.

Queries the GitHub repository search API and returns normalized
``CodeRepository`` objects. Set ``GITHUB_TOKEN`` or ``GH_TOKEN`` for
higher rate limits.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .code_repo import CodeRepository

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_API_VERSION = "2022-11-28"


def _github_request(url: str) -> dict:
    """Send an authenticated GET request to the GitHub REST API.

    Args:
        url: Fully qualified GitHub API URL.

    Returns:
        Parsed JSON response body.

    Raises:
        urllib.error.URLError: On network failure.
        urllib.error.HTTPError: If GitHub returns an error status.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "bone-research-agent",
    }

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def search_github(
    query: str,
    *,
    per_page: int = 30,
    sort: str = "stars",
    order: str = "desc",
) -> list[CodeRepository]:
    """Search GitHub repositories matching a query.

    Supports GitHub search qualifiers in ``query`` (e.g.
    ``"bone classification language:python stars:>5"``).

    Args:
        query: Free-text search string with optional GitHub qualifiers.
        per_page: Maximum number of results to return (default 30).
        sort: Sort field — ``stars``, ``forks``, ``help-wanted-issues``, or
            ``updated``.
        order: Sort direction — ``asc`` or ``desc``.

    Returns:
        A list of ``CodeRepository`` objects parsed from the GitHub response.

    Raises:
        urllib.error.URLError: On network failure.
        urllib.error.HTTPError: If GitHub returns an error status (e.g. 403).
    """
    params = urllib.parse.urlencode(
        {
            "q": query,
            "per_page": per_page,
            "sort": sort,
            "order": order,
        }
    )
    url = f"{GITHUB_SEARCH_API}?{params}"
    payload = _github_request(url)

    return [CodeRepository.from_github(repo) for repo in payload.get("items", [])]
