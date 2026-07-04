"""Dataclasses for code repository search results and paper–repo links."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CodeRepository:
    """A code repository normalized from a GitHub API response.

    Attributes:
        name: Short repository name (e.g. ``"OsteoAI"``).
        full_name: Owner-qualified name (e.g. ``"user/OsteoAI"``).
        url: GitHub HTML URL.
        description: Repository description text.
        language: Primary language reported by GitHub.
        stars: Star count.
        forks: Fork count.
        license: SPDX ID or license name.
        topics: GitHub topic tags.
        source: Source platform (always ``github``).
        source_id: GitHub numeric repository ID as a string.
    """

    name: str
    full_name: str | None = None
    url: str | None = None
    description: str | None = None
    language: str | None = None
    stars: int | None = None
    forks: int | None = None
    license: str | None = None
    topics: list[str] = field(default_factory=list)
    source: str = "github"
    source_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize this repository to a plain dictionary for JSON export."""
        return asdict(self)

    @classmethod
    def from_github(cls, repo: dict[str, Any]) -> CodeRepository:
        """Build a ``CodeRepository`` from a GitHub search API repository object.

        Args:
            repo: A single repository dict from the GitHub ``/search/repositories``
                endpoint.

        Returns:
            A ``CodeRepository`` with ``source`` set to ``github``.
        """
        license_info = repo.get("license") or {}
        license_name = license_info.get("spdx_id") or license_info.get("name")

        return cls(
            name=repo.get("name") or "",
            full_name=repo.get("full_name"),
            url=repo.get("html_url"),
            description=repo.get("description"),
            language=repo.get("language"),
            stars=repo.get("stargazers_count"),
            forks=repo.get("forks_count"),
            license=license_name,
            topics=repo.get("topics") or [],
            source="github",
            source_id=str(repo["id"]) if repo.get("id") is not None else None,
        )


@dataclass
class PaperRepositoryLink:
    """A relationship between a paper and a code repository.

    Intended for knowledge-graph storage when linking publications to
    implementations (e.g. a paper that describes a model and the GitHub
    repo that implements it).

    Attributes:
        paper_id: Paper identifier (DOI or ``Paper.source_id``).
        repo_id: Repository ``CodeRepository.source_id``.
        relation_type: Relationship label (default ``"implements"``).
        confidence: Optional match confidence score between 0 and 1.
        evidence: Optional text explaining why the link was inferred.
    """

    paper_id: str | None
    repo_id: str | None
    relation_type: str = "implements"
    confidence: float | None = None
    evidence: str | None = None
