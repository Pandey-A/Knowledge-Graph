from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from neo4j import GraphDatabase

from app.config import settings


class Neo4jClient:
    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def run(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._driver.session(database=settings.neo4j_database) as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]

    def run_many(self, statements: Iterable[str]) -> None:
        with self._driver.session(database=settings.neo4j_database) as session:
            for statement in statements:
                session.run(statement)