"""Execute Cypher queries against the research knowledge graph."""

from __future__ import annotations
from typing import Any
from neo4j import Driver
from .neo4j_client import get_neo4j_driver


def query_graph(
    cypher: str,
    parameters: dict[str, Any] | None = None,
    *,
    driver: Driver | None = None,
) -> list[dict[str, Any]]:
    """Run a read Cypher query and return result records as dictionaries.

    Args:
        cypher: Cypher query string.
        parameters: Optional query parameters.
        driver: Optional preconfigured Neo4j driver.

    Returns:
        List of result rows as plain dictionaries.
    """
    neo4j = driver or get_neo4j_driver()
    with neo4j.session() as session:
        result = session.run(cypher, parameters or {})
        return [record.data() for record in result]
