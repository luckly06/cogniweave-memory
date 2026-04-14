from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..base import BaseStore
from ..enums import MemoryScope, MemoryType
from ..models import MemoryRecord
from ..stores_compat import _deserialize_record, _serialize_record
from ..utils import cosine_similarity, deterministic_embedding, recency_score, safe_json_dumps, utc_now


class SQLiteMemoryStore(BaseStore):
    def __init__(self, db_path: str | Path, memory_type: MemoryType):
        self.db_path = str(db_path)
        self.memory_type = memory_type
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_records (
                    memory_id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    content TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_by_id(self, memory_id: str) -> Optional[MemoryRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM memory_records WHERE memory_id = ?", (memory_id,)).fetchone()
        return _deserialize_record(json.loads(row["payload"])) if row else None

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        return self.get_by_id(memory_id)

    def upsert(self, record: MemoryRecord) -> None:
        if not record.embedding:
            record.embedding = deterministic_embedding(record.summary or record.content)
        record.created_at = record.created_at or utc_now()
        record.updated_at = utc_now()
        payload = _serialize_record(record)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_records(memory_id, memory_type, scope, content, payload, embedding, tags, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    memory_type=excluded.memory_type,
                    scope=excluded.scope,
                    content=excluded.content,
                    payload=excluded.payload,
                    embedding=excluded.embedding,
                    tags=excluded.tags,
                    updated_at=excluded.updated_at
                """,
                (
                    record.memory_id,
                    record.memory_type.value,
                    record.scope.value,
                    record.content,
                    safe_json_dumps(payload),
                    safe_json_dumps(record.embedding),
                    safe_json_dumps(record.tags),
                    record.updated_at.isoformat(),
                ),
            )
            conn.commit()

    def batch_upsert(self, records: Sequence[MemoryRecord]) -> None:
        for record in records:
            self.upsert(record)

    def delete(self, memory_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM memory_records WHERE memory_id = ?", (memory_id,))
            conn.commit()

    def archive(self, memory_id: str) -> None:
        record = self.get_by_id(memory_id)
        if not record:
            return
        record.archived = True
        record.updated_at = utc_now()
        self.upsert(record)

    def list_by_scope(self, scope: MemoryScope, scope_id: str = "") -> List[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM memory_records WHERE memory_type = ? AND scope = ?",
                (self.memory_type.value, scope.value),
            ).fetchall()
        return [_deserialize_record(json.loads(row["payload"])) for row in rows]

    def list_records(self, include_archived: bool = False) -> List[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM memory_records WHERE memory_type = ?",
                (self.memory_type.value,),
            ).fetchall()
        records = [_deserialize_record(json.loads(row["payload"])) for row in rows]
        return records if include_archived else [record for record in records if not record.archived]

    def vector_query(self, query: str, top_k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[MemoryRecord]:
        filters = filters or {}
        records = self.list_records(include_archived=False)
        query_vec = deterministic_embedding(query)
        scored = []
        for record in records:
            if filters.get("scope") and record.scope.value != filters["scope"]:
                continue
            if filters.get("rag_namespace") and record.metadata.get("rag_namespace") != filters["rag_namespace"]:
                continue
            if filters.get("only_rag_data") and not bool(record.metadata.get("is_rag_data", False)):
                continue
            sim = cosine_similarity(query_vec, record.embedding or [])
            record.recency = recency_score(record.updated_at)
            scored.append((sim, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored[:top_k]]
