from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..base import BaseStore
from ..enums import MemoryScope, MemoryType
from ..models import MemoryRecord
from ..stores_compat import _deserialize_record, _serialize_record
from ..utils import deterministic_embedding, tokenize, utc_now


class JsonKeyValueStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")
        self._lock = threading.RLock()

    def _load(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _save(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key: str) -> Any:
        with self._lock:
            return self._load().get(key)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            data = self._load()
            data[key] = value
            self._save(data)

    def all(self) -> Dict[str, Any]:
        with self._lock:
            return self._load()


class KeyMemoryStore(BaseStore):
    def __init__(self, path: str | Path):
        self.memory_type = MemoryType.KEY
        self._store = JsonKeyValueStore(path)

    def _all_records(self) -> Dict[str, Any]:
        return self._store.all()

    def get_by_id(self, memory_id: str) -> Optional[MemoryRecord]:
        payload = self._all_records().get(memory_id)
        return _deserialize_record(payload) if payload else None

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        return self.get_by_id(memory_id)

    def upsert(self, record: MemoryRecord) -> None:
        if not record.embedding:
            record.embedding = deterministic_embedding(record.summary or record.content)
        record.created_at = record.created_at or utc_now()
        record.updated_at = utc_now()
        self._store.set(record.memory_id, _serialize_record(record))

    def batch_upsert(self, records: Sequence[MemoryRecord]) -> None:
        for record in records:
            self.upsert(record)

    def delete(self, memory_id: str) -> None:
        data = self._store.all()
        if memory_id in data:
            del data[memory_id]
            self._store._save(data)

    def archive(self, memory_id: str) -> None:
        record = self.get_by_id(memory_id)
        if not record:
            return
        record.archived = True
        record.updated_at = utc_now()
        self.upsert(record)

    def list_by_scope(self, scope: MemoryScope, scope_id: str = "") -> List[MemoryRecord]:
        return [_deserialize_record(v) for v in self._all_records().values() if v["scope"] == scope.value]

    def list_records(self, include_archived: bool = False) -> List[MemoryRecord]:
        records = [_deserialize_record(v) for v in self._all_records().values()]
        return records if include_archived else [record for record in records if not record.archived]

    def _match_scope_terms(self, expected: Any, actual_terms: List[str]) -> bool:
        if not expected:
            return True
        if isinstance(expected, str):
            expected_terms = tokenize(expected)
        elif isinstance(expected, (list, tuple, set)):
            expected_terms = []
            for item in expected:
                expected_terms.extend(tokenize(str(item)))
        else:
            expected_terms = tokenize(str(expected))
        if not expected_terms:
            return True
        return bool(set(expected_terms) & set(actual_terms))

    def _match_policy_scope(self, expected: Any, policy_scope: str) -> bool:
        if not expected:
            return True
        if isinstance(expected, str):
            scopes = [expected]
        elif isinstance(expected, (list, tuple, set)):
            scopes = [str(item) for item in expected]
        else:
            scopes = [str(expected)]
        scopes = [scope.strip().lower() for scope in scopes if str(scope).strip()]
        if not scopes:
            return True
        if "*" in scopes or "all" in scopes or "global" in scopes:
            return True
        return policy_scope.strip().lower() in scopes

    def fetch_for_injection(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None,
        task_scope: Optional[str] = None,
        policy_scope: Optional[str] = None,
    ) -> List[MemoryRecord]:
        records = [_deserialize_record(v) for v in self._all_records().values()]
        results = []
        task_scope_terms = tokenize(task_scope or "")
        policy_scope = policy_scope or task_type or ""
        for record in records:
            metadata = record.metadata or {}
            if not self._match_policy_scope(metadata.get("policy_scope"), policy_scope):
                continue
            if not self._match_scope_terms(metadata.get("task_scope_terms") or metadata.get("task_scope"), task_scope_terms):
                continue
            if record.scope == MemoryScope.USER and record.metadata.get("user_id") == user_id:
                results.append(record)
            elif record.scope == MemoryScope.GLOBAL:
                results.append(record)
            elif session_id and record.scope == MemoryScope.SESSION and record.metadata.get("session_id") == session_id:
                results.append(record)
        results.sort(
            key=lambda r: (
                r.pinned,
                r.importance,
                r.confidence,
                r.updated_at,
            ),
            reverse=True,
        )
        return results
