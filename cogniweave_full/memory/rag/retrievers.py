from __future__ import annotations

from typing import Dict, Optional

from ..base import BaseRetriever
from ..enums import MemoryType
from ..models import CandidateSet, TaskContext


class _StoreBackedRetriever(BaseRetriever):
    def __init__(self, memory_type: MemoryType, store):
        self.memory_type = memory_type
        self.store = store

    def retrieve(self, query: str, task_context: TaskContext, top_k: int, filters: Optional[Dict] = None) -> CandidateSet:
        items = self.store.vector_query(query, top_k=top_k, filters=filters)
        return CandidateSet(channel=self.memory_type, items=items)


class SemanticRetriever(_StoreBackedRetriever):
    def __init__(self, store):
        super().__init__(MemoryType.SEMANTIC, store)


class EpisodicRetriever(_StoreBackedRetriever):
    def __init__(self, store):
        super().__init__(MemoryType.EPISODIC, store)


class PerceptualRetriever(_StoreBackedRetriever):
    def __init__(self, store):
        super().__init__(MemoryType.PERCEPTUAL, store)


class ExperienceRetriever(_StoreBackedRetriever):
    def __init__(self, store):
        super().__init__(MemoryType.EXPERIENCE, store)
