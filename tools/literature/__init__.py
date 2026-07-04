"""Literature search tools for the bone research agent.

Exports the ``Paper`` dataclass and search functions for OpenAlex, Semantic
Scholar, and combined multi-source queries.
"""

from .openalex import search_openalex
from .paper import Paper
from .search_papers import search_papers
from .semantic_scholar import search_semantic_scholar

__all__ = [
    "Paper",
    "search_openalex",
    "search_papers",
    "search_semantic_scholar",
]
