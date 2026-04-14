from __future__ import annotations

from ..base import BaseMemory
from ..enums import MemoryType


class KeyMemory(BaseMemory):
    memory_type = MemoryType.KEY

    def fetch_for_injection(
        self,
        user_id: str,
        session_id: str | None = None,
        task_type: str | None = None,
        task_scope: str | None = None,
        policy_scope: str | None = None,
    ):
        return self.store.fetch_for_injection(
            user_id=user_id,
            session_id=session_id,
            task_type=task_type,
            task_scope=task_scope,
            policy_scope=policy_scope,
        )
