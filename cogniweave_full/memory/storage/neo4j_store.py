from __future__ import annotations

from typing import List, Optional

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - optional dependency at runtime
    GraphDatabase = None


class Neo4jGraphStore:
    def __init__(self, uri: str = "", user: str = "", password: str = "", enabled: bool = False):
        self.enabled = enabled and bool(uri) and GraphDatabase is not None
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = GraphDatabase.driver(uri, auth=(user, password)) if self.enabled else None
        self._fallback_edges = {}

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def link(self, source_id: str, target_id: str) -> None:
        self._fallback_edges.setdefault(source_id, set()).add(target_id)
        if not self.driver:
            return
        with self.driver.session() as session:
            session.run(
                """
                MERGE (a:Memory {id: $source_id})
                MERGE (b:Memory {id: $target_id})
                MERGE (a)-[:REFERS_TO]->(b)
                """,
                source_id=source_id,
                target_id=target_id,
            )

    def neighbors(self, source_id: str) -> List[str]:
        if not self.driver:
            return list(self._fallback_edges.get(source_id, set()))
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (:Memory {id: $source_id})-[:REFERS_TO]->(b:Memory)
                RETURN b.id AS id
                """,
                source_id=source_id,
            )
            return [row["id"] for row in result]
