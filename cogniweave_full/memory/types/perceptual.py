from __future__ import annotations

from ..base import BaseMemory
from ..enums import MemoryType


class PerceptualMemory(BaseMemory):
    memory_type = MemoryType.PERCEPTUAL
