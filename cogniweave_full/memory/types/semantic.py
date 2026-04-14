from __future__ import annotations

from ..base import BaseMemory
from ..enums import MemoryType


class SemanticMemory(BaseMemory):
    memory_type = MemoryType.SEMANTIC
