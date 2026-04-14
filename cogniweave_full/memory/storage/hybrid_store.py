from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from ..base import BaseStore
from ..enums import MemoryScope, MemoryType
from ..models import MemoryRecord
from ..utils import deterministic_embedding, recency_score
from .neo4j_store import Neo4jGraphStore
from .qdrant_store import QdrantVectorStore
from .sqlite_store import SQLiteMemoryStore


class _BaseHybridStore(BaseStore):
    def __init__(
        self,
        memory_type: MemoryType,
        metadata_store: SQLiteMemoryStore,
        vector_store: QdrantVectorStore,
        graph_store: Optional[Neo4jGraphStore] = None,
    ):
        self.memory_type = memory_type
        self.metadata_store = metadata_store
        self.vector_store = vector_store
        self.graph_store = graph_store

    def get_by_id(self, memory_id: str) -> Optional[MemoryRecord]:
        return self.metadata_store.get_by_id(memory_id)

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        return self.get_by_id(memory_id)

    def upsert(self, record: MemoryRecord) -> None:
        if not record.embedding:
            record.embedding = deterministic_embedding(record.summary or record.content)
        self.metadata_store.upsert(record)
        self.vector_store.upsert(record)
        if self.graph_store:
            for ref in record.graph_refs:
                self.graph_store.link(record.memory_id, ref)

    def batch_upsert(self, records: Sequence[MemoryRecord]) -> None:
        for record in records:
            self.upsert(record)

    def delete(self, memory_id: str) -> None:
        self.metadata_store.delete(memory_id)
        self.vector_store.delete(memory_id)

    def archive(self, memory_id: str) -> None:
        self.metadata_store.archive(memory_id)

    def list_by_scope(self, scope: MemoryScope, scope_id: str = "") -> List[MemoryRecord]:
        return self.metadata_store.list_by_scope(scope, scope_id)

    def list_records(self, include_archived: bool = False) -> List[MemoryRecord]:
        return self.metadata_store.list_records(include_archived)

    def vector_query(self, query: str, top_k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[MemoryRecord]:
        filters = filters or {}
        query_vector = deterministic_embedding(query)
        candidate_ids = self.vector_store.search(query_vector, top_k=top_k, filters=filters)
        records: List[MemoryRecord] = []
        seen = set()

        for memory_id in candidate_ids:
            record = self.metadata_store.get_by_id(memory_id)
            if not record or record.archived:
                continue
            record.recency = recency_score(record.updated_at)
            records.append(record)
            seen.add(record.memory_id)

        if self.graph_store and self.memory_type == MemoryType.SEMANTIC:
            neighbor_ids = []
            for memory_id in list(candidate_ids)[: max(1, top_k // 2)]:
                neighbor_ids.extend(self.graph_store.neighbors(memory_id))
            for memory_id in neighbor_ids:
                if memory_id in seen:
                    continue
                record = self.metadata_store.get_by_id(memory_id)
                if not record or record.archived:
                    continue
                record.recency = recency_score(record.updated_at)
                records.append(record)
                seen.add(record.memory_id)

        if records:
            return records[:top_k]

        return self.metadata_store.vector_query(query, top_k=top_k, filters=filters)


class SemanticHybridStore(_BaseHybridStore):
    def __init__(self, metadata_store, vector_store, graph_store):
        super().__init__(MemoryType.SEMANTIC, metadata_store, vector_store, graph_store)


class EpisodicHybridStore(_BaseHybridStore):
    def __init__(self, metadata_store, vector_store):
        super().__init__(MemoryType.EPISODIC, metadata_store, vector_store, None)


class PerceptualHybridStore(_BaseHybridStore):
    def __init__(self, metadata_store, vector_store):
        super().__init__(MemoryType.PERCEPTUAL, metadata_store, vector_store, None)


class ExperienceHybridStore(_BaseHybridStore):
    def __init__(self, metadata_store, vector_store):
        super().__init__(MemoryType.EXPERIENCE, metadata_store, vector_store, None)
