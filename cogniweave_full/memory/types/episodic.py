from __future__ import annotations

from ..base import BaseMemory
from ..enums import MemoryType


class EpisodicMemory(BaseMemory):
    memory_type = MemoryType.EPISODIC
