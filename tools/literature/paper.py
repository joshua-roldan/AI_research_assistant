"""Normalized dataclass for literature search results.

Provides a single ``Paper`` type that can be constructed from OpenAlex or
Semantic Scholar API responses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Paper:
    """A scientific paper normalized from one or more literature APIs.

    Attributes:
        title: Paper title.
        authors: Author display names.
        year: Publication year, if known.
        abstract: Abstract text, if available.
        doi: DOI without the ``https://doi.org/`` prefix.
        url: Canonical link to the record.
        source_id: Identifier from the source API (OpenAlex URL or S2 paper ID).
        source: API that produced this record (``openalex``, ``semantic_scholar``,
            or ``unknown``).
        venue: Journal or conference name.
        citation_count: Number of citations, if reported by the source.
        topics: Subject areas or fields of study.
    """

    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None
    source_id: str | None = None
    source: str = "unknown"
    venue: str | None = None
    citation_count: int | None = None
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this paper to a plain dictionary for JSON export."""
        return asdict(self)

    def embedding_text(self) -> str:
        """Build the text representation used for semantic embedding."""
        parts = [self.title]
        if self.abstract:
            parts.append(self.abstract)
        if self.authors:
            parts.append("Authors: " + ", ".join(self.authors))
        if self.topics:
            parts.append("Topics: " + ", ".join(self.topics))
        if self.venue:
            parts.append(f"Venue: {self.venue}")
        return "\n\n".join(parts)

    @classmethod
    def from_openalex(cls, work: dict[str, Any]) -> Paper:
        """Build a ``Paper`` from an OpenAlex works API response object.

        Args:
            work: A single work dict from the OpenAlex ``/works`` endpoint.

        Returns:
            A ``Paper`` with ``source`` set to ``openalex``.
        """
        authors = [
            author["author"]["display_name"]
            for author in work.get("authorships", [])
            if author.get("author", {}).get("display_name")
        ]
        topics = [
            topic["display_name"]
            for topic in work.get("topics", [])
            if topic.get("display_name")
        ]
        doi = work.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi.removeprefix("https://doi.org/")

        return cls(
            title=work.get("title") or "",
            authors=authors,
            year=work.get("publication_year"),
            abstract=work.get("abstract"),
            doi=doi,
            url=work.get("id"),
            source_id=work.get("id"),
            source="openalex",
            venue=(work.get("primary_location") or {})
            .get("source", {})
            .get("display_name"),
            citation_count=work.get("cited_by_count"),
            topics=topics,
        )

    @classmethod
    def from_semantic_scholar(cls, work: dict[str, Any]) -> Paper:
        """Build a ``Paper`` from a Semantic Scholar search result object.

        Args:
            work: A single paper dict from the Semantic Scholar search API.

        Returns:
            A ``Paper`` with ``source`` set to ``semantic_scholar``.
        """
        authors = [
            author.get("name", "")
            for author in work.get("authors", [])
            if author.get("name")
        ]
        external_ids = work.get("externalIds") or {}

        return cls(
            title=work.get("title") or "",
            authors=authors,
            year=work.get("year"),
            abstract=work.get("abstract"),
            doi=external_ids.get("DOI"),
            url=work.get("url"),
            source_id=work.get("paperId"),
            source="semantic_scholar",
            venue=(work.get("venue") or work.get("journal", {}).get("name")),
            citation_count=work.get("citationCount"),
            topics=work.get("fieldsOfStudy") or [],
        )
