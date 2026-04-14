from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict

from .enums import MemoryScope, MemoryType
from .models import MemoryRecord


def _serialize_record(record: MemoryRecord) -> Dict[str, Any]:
    payload = asdict(record)
    for key in ("created_at", "updated_at", "last_access_at"):
        if payload.get(key):
            payload[key] = payload[key].isoformat()
    payload["memory_type"] = record.memory_type.value
    payload["scope"] = record.scope.value
    return payload


def _deserialize_record(payload: Dict[str, Any]) -> MemoryRecord:
    payload = dict(payload)
    payload["memory_type"] = MemoryType(payload["memory_type"])
    payload["scope"] = MemoryScope(payload["scope"])
    for key in ("created_at", "updated_at", "last_access_at"):
        if payload.get(key):
            payload[key] = datetime.fromisoformat(payload[key])
    return MemoryRecord(**payload)
