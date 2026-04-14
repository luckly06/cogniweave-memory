from __future__ import annotations

from ..base import BaseTool


class MemorySearchTool(BaseTool):
    name = "memory_search"
    description = "Search CogniWeave memories directly."

    def __init__(self, manager):
        self.manager = manager

    def run(
        self,
        query: str,
        top_k: int = 6,
        rag_namespace: str = "",
        only_rag_data: bool = False,
        channel: str = "",
        **kwargs,
    ):
        if channel == "key":
            items = self.manager.key_store.fetch_for_injection(
                user_id=kwargs.get("user_id", "tool_user"),
                session_id=kwargs.get("session_id", "tool_session"),
                task_scope=query,
            )
            return [
                {
                    "memory_id": item.memory_id,
                    "channel": "key",
                    "summary": item.summary or item.content[:200],
                    "score": 1.0,
                }
                for item in items[:top_k]
                if query.strip().lower() in (item.summary or item.content).lower() or not query.strip()
            ]

        task_context = self.manager.task_router.route(
            self.manager._tool_raw_input(
                kwargs.get("user_id", "tool_user"),
                kwargs.get("session_id", "tool_session"),
                query,
            )
        )
        if channel:
            task_context.candidate_channels = [type_ for type_ in task_context.candidate_channels if type_.value == channel]

        _, selected = self.manager.retrieval.run(
            user_id=kwargs.get("user_id", "tool_user"),
            session_id=kwargs.get("session_id", "tool_session"),
            query=query,
            task_context=task_context,
            rag_namespace=rag_namespace or None,
            only_rag_data=only_rag_data,
            enable_mqe=False,
            enable_hyde=False,
        )
        return [
            {
                "memory_id": item.record.memory_id,
                "channel": item.channel.value,
                "summary": item.record.summary or item.record.content[:200],
                "score": item.unified_score,
            }
            for item in selected[:top_k]
        ]
