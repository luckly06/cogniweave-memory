from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
except ImportError:  # pragma: no cover - optional dependency at runtime
    QdrantClient = None
    rest = None

from ..models import MemoryRecord
from ..utils import cosine_similarity


class QdrantVectorStore:
    """
    支持两种模式：
    1. local mode: QdrantClient(path="...")
    2. remote mode: QdrantClient(url="...", api_key="...")
    """
    def __init__(
        self,
        collection_name: str,
        vector_size: int = 64,
        local_path: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
    ):
        self.collection_name = collection_name
        self.vector_size = vector_size

        if local_path and QdrantClient is not None:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=local_path)
        else:
            self.client = QdrantClient(url=url, api_key=api_key or None) if (url and QdrantClient is not None) else None

        if self.client and rest is not None:
            self._ensure_collection()

        self._fallback_records: Dict[str, MemoryRecord] = {}

    def _ensure_collection(self) -> None:
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection_name in existing:
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=rest.VectorParams(size=self.vector_size, distance=rest.Distance.COSINE),
        )

    def upsert(self, record: MemoryRecord) -> None:
        self._fallback_records[record.memory_id] = record
        if not self.client or not record.embedding:
            return
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                rest.PointStruct(
                    id=record.memory_id,
                    vector=record.embedding,
                    payload={
                        "memory_id": record.memory_id,
                        "memory_type": record.memory_type.value,
                        "scope": record.scope.value,
                        "tags": record.tags,
                        "rag_namespace": record.metadata.get("rag_namespace"),
                        "is_rag_data": record.metadata.get("is_rag_data", False),
                    },
                )
            ],
        )

    def delete(self, memory_id: str) -> None:
        self._fallback_records.pop(memory_id, None)
        if not self.client:
            return
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.PointIdsList(points=[memory_id]),
        )

    def search(self, query_vector: List[float], top_k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[str]:
        if not self.client or rest is None:
            ranked = sorted(
                self._fallback_records.values(),
                key=lambda record: cosine_similarity(query_vector, record.embedding or []),
                reverse=True,
            )
            return [record.memory_id for record in ranked[:top_k]]

        must = []
        filters = filters or {}
        if filters.get("rag_namespace"):
            must.append(rest.FieldCondition(key="rag_namespace", match=rest.MatchValue(value=filters["rag_namespace"])))
        if filters.get("only_rag_data"):
            must.append(rest.FieldCondition(key="is_rag_data", match=rest.MatchValue(value=True)))

        payload_filter = rest.Filter(must=must) if must else None
        if hasattr(self.client, "search"):
            hits = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=payload_filter,
                limit=top_k,
            )
            return [str(hit.id) for hit in hits]

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=payload_filter,
            limit=top_k,
            with_payload=False,
            with_vectors=False,
        )
        points = getattr(response, "points", None) or []
        return [str(point.id) for point in points]
