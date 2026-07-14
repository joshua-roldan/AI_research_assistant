"""Neo4j connection helpers for the research knowledge graph."""

from __future__ import annotations

import os

from neo4j import Driver, GraphDatabase

DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"


def get_neo4j_driver() -> Driver:
    """Create a Neo4j driver from environment configuration.

    Environment variables:
        NEO4J_URI: Bolt URI (default ``bolt://localhost:7687``).
        NEO4J_USER: Database username (default ``neo4j``).
        NEO4J_PASSWORD: Database password (required).

    Returns:
        A configured Neo4j ``Driver``.

    Raises:
        ValueError: If ``NEO4J_PASSWORD`` is not set.
    """
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise ValueError("NEO4J_PASSWORD environment variable is required.")

    uri = os.environ.get("NEO4J_URI", DEFAULT_NEO4J_URI)
    user = os.environ.get("NEO4J_USER", DEFAULT_NEO4J_USER)
    return GraphDatabase.driver(uri, auth=(user, password))


def ensure_constraints(driver: Driver) -> None:
    """Create uniqueness constraints for core node types if they do not exist."""
    statements = [
        "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT author_name IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT venue_name IF NOT EXISTS FOR (v:Venue) REQUIRE v.name IS UNIQUE",
        "CREATE CONSTRAINT repository_id IF NOT EXISTS FOR (r:CodeRepository) REQUIRE r.id IS UNIQUE",
    ]
    with driver.session() as session:
        for statement in statements:
            session.run(statement)
