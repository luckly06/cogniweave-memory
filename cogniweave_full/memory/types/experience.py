from __future__ import annotations

from ..base import BaseMemory
from ..enums import MemoryType


class ExperienceMemory(BaseMemory):
    memory_type = MemoryType.EXPERIENCE
