"""Hugging Face Hub search integration.

Queries the Hugging Face API for models and spaces, returning normalized
``CodeRepository`` objects. Set ``HF_TOKEN`` or ``HUGGINGFACE_TOKEN`` for
authenticated requests.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .code_repo import CodeRepository

HF_API = "https://huggingface.co/api"


def _huggingface_request(url: str) -> list[dict]:
    """Send a GET request to the Hugging Face Hub API.

    Args:
        url: Fully qualified Hugging Face API URL.

    Returns:
        Parsed JSON response body as a list of repository objects.

    Raises:
        urllib.error.URLError: On network failure.
        urllib.error.HTTPError: If the API returns an error status.
    """
    headers = {
        "Accept": "application/json",
        "User-Agent": "bone-research-agent",
    }

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if isinstance(payload, list):
        return payload
    return payload.get("models") or payload.get("spaces") or []


def _search_huggingface_endpoint(
    endpoint: str,
    query: str,
    *,
    limit: int,
    kind: str,
    extra_params: dict[str, str] | None = None,
) -> list[CodeRepository]:
    params = {"search": query, "limit": str(limit), **(extra_params or {})}
    url = f"{HF_API}/{endpoint}?{urllib.parse.urlencode(params)}"
    return [
        CodeRepository.from_huggingface(item, kind=kind)
        for item in _huggingface_request(url)
    ]


def search_huggingface_models(query: str, *, limit: int = 20) -> list[CodeRepository]:
    """Search Hugging Face models matching a query.

    Args:
        query: Free-text search terms.
        limit: Maximum number of results to return.

    Returns:
        Matching models as ``CodeRepository`` objects.
    """
    return _search_huggingface_endpoint(
        "models",
        query,
        limit=limit,
        kind="model",
        extra_params={"full": "true", "sort": "downloads"},
    )


def search_huggingface_spaces(query: str, *, limit: int = 20) -> list[CodeRepository]:
    """Search Hugging Face Spaces matching a query.

    Args:
        query: Free-text search terms.
        limit: Maximum number of results to return.

    Returns:
        Matching spaces as ``CodeRepository`` objects.
    """
    return _search_huggingface_endpoint("spaces", query, limit=limit, kind="space")


def search_huggingface(
    query: str,
    *,
    limit: int = 20,
    repo_type: str = "all",
) -> list[CodeRepository]:
    """Search Hugging Face models and/or spaces matching a query.

    Args:
        query: Free-text search terms (e.g. ``"bone classification"``).
        limit: Maximum results per endpoint (default 20).
        repo_type: ``"all"``, ``"models"``, or ``"spaces"``.

    Returns:
        Deduplicated list of ``CodeRepository`` objects.

    Raises:
        ValueError: If ``repo_type`` is not recognized.
        urllib.error.URLError: On network failure.
        urllib.error.HTTPError: If the API returns an error status.
    """
    repositories: list[CodeRepository] = []

    if repo_type in ("all", "models"):
        repositories.extend(search_huggingface_models(query, limit=limit))
    if repo_type in ("all", "spaces"):
        repositories.extend(search_huggingface_spaces(query, limit=limit))
    if repo_type not in ("all", "models", "spaces"):
        raise ValueError("repo_type must be 'all', 'models', or 'spaces'")

    seen: set[str] = set()
    unique: list[CodeRepository] = []
    for repo in repositories:
        key = repo.source_id or repo.full_name or repo.name
        if key in seen:
            continue
        seen.add(key)
        unique.append(repo)

    return unique
