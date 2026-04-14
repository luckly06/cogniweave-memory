from __future__ import annotations

from ..base import BaseTool
from ...memory.enums import MemoryScope, MemoryType


class MemoryForgetTool(BaseTool):
    name = "memory_forget"
    description = "Explicitly forget a memory by memory_id."

    def __init__(self, manager):
        self.manager = manager

    def run(self, memory_id: str, **kwargs):
        ok = self.manager.forget_manager.explicit_forget(memory_id)
        return {"forgotten": ok, "memory_id": memory_id}


class MemoryLifecycleTool(BaseTool):
    name = "memory_lifecycle"
    description = "Archive, demote, or inspect lifecycle decisions for a memory channel."

    def __init__(self, manager):
        self.manager = manager

    def run(self, action: str, channel: str = "", memory_id: str = "", to_channel: str = "semantic", dry_run: bool = True, **kwargs):
        if action == "run_channel_cycle":
            return {
                "channel": channel,
                "decisions": [
                    {
                        "memory_id": item.memory_id,
                        "action": item.action.value,
                        "reason": item.reason,
                        "retention_score": item.retention_score,
                    }
                    for item in self.manager.forget_manager.run_channel_cycle(channel=channel, dry_run=dry_run)
                ],
            }
        if action == "archive" and memory_id:
            self.manager.archive_memory(channel, memory_id)
            return {"archived": True, "memory_id": memory_id, "channel": channel}
        if action == "demote" and memory_id:
            self.manager.demote_memory(memory_id=memory_id, from_channel=channel, to_channel=to_channel)
            return {"demoted": True, "memory_id": memory_id, "from_channel": channel, "to_channel": to_channel}
        return {"error": "unsupported action"}


class OfflineIngestionTool(BaseTool):
    name = "offline_ingest"
    description = "Ingest text/log/multimodal payload into long-term memory."

    def __init__(self, manager):
        self.manager = manager

    def run(
        self,
        source_id: str,
        payload: str,
        source_type: str = "document",
        memory_type: str = "semantic",
        scope: str = "global",
        rag_namespace: str = "",
        **kwargs,
    ):
        records = self.manager.offline_ingestion.ingest_payload(
            source_id=source_id,
            payload=payload,
            source_type=source_type,
            rag_namespace=rag_namespace or None,
            memory_type=MemoryType(memory_type),
            scope=MemoryScope(scope),
            tags=[source_type, memory_type],
        )
        return {
            "source_id": source_id,
            "count": len(records),
            "memory_ids": [record.memory_id for record in records],
        }
