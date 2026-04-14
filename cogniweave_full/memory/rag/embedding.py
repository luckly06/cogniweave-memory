from __future__ import annotations

from typing import List

from ..utils import deterministic_embedding


class EmbeddingService:
    """
    首版仍然用 deterministic_embedding 作为统一 fallback。
    后续接真实 embedding provider 时，只替换这个文件。
    """
    def embed_text(self, text: str) -> List[float]:
        return deterministic_embedding(text)

    def embed_multimodal(self, payload: str) -> List[float]:
        return deterministic_embedding(payload)
