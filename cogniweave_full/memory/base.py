from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence

from .enums import MemoryType
from .models import CandidateSet, MemoryRecord, ScoredCandidate, TaskContext


class BaseStore(ABC):
    memory_type: MemoryType

    @abstractmethod
    def get_by_id(self, memory_id: str) -> Optional[MemoryRecord]:
        ...

    @abstractmethod
    def upsert(self, record: MemoryRecord) -> None:
        ...

    @abstractmethod
    def batch_upsert(self, records: Sequence[MemoryRecord]) -> None:
        ...

    @abstractmethod
    def delete(self, memory_id: str) -> None:
        ...

    @abstractmethod
    def list_by_scope(self, scope, scope_id: str = "") -> List[MemoryRecord]:
        ...

    @abstractmethod
    def list_records(self, include_archived: bool = False) -> List[MemoryRecord]:
        ...

    @abstractmethod
    def archive(self, memory_id: str) -> None:
        ...


class BaseMemory(ABC):
    memory_type: MemoryType

    def __init__(self, store: BaseStore):
        self.store = store

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        return self.store.get_by_id(memory_id)

    def put(self, record: MemoryRecord) -> None:
        self.store.upsert(record)

    def delete(self, memory_id: str) -> None:
        self.store.delete(memory_id)


class BaseRetriever(ABC):
    memory_type: MemoryType

    @abstractmethod
    def retrieve(
        self,
        query: str,
        task_context: TaskContext,
        top_k: int,
        filters: Optional[Dict] = None,
    ) -> CandidateSet:
        ...


class BaseScorer(ABC):
    memory_type: MemoryType

    @abstractmethod
    def score(
        self,
        query: str,
        candidates: CandidateSet,
        task_context: TaskContext,
    ) -> List[ScoredCandidate]:
        ...


class BaseNormalizer(ABC):
    @abstractmethod
    def normalize(
        self,
        scored: Dict[MemoryType, List[ScoredCandidate]],
    ) -> Dict[MemoryType, List[ScoredCandidate]]:
        ...


class BaseFusionPolicy(ABC):
    @abstractmethod
    def fuse(
        self,
        normalized: Dict[MemoryType, List[ScoredCandidate]],
        key_items: List[MemoryRecord],
        task_context: TaskContext,
        k_context: int,
    ) -> List[ScoredCandidate]:
        ...


class BaseRAGPipeline(ABC):
    @abstractmethod
    def run(self, user_id: str, session_id: str, query: str, task_context: TaskContext, config=None):
        ...
