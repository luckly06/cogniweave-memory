from __future__ import annotations

from statistics import mean, pstdev
from typing import Dict, List

from ..base import BaseNormalizer
from ..enums import MemoryType
from ..models import ScoredCandidate
from ..utils import robust_zscore


class Normalizer(BaseNormalizer):
    def __init__(self, mode: str = "zscore"):
        self.mode = mode

    def normalize(self, scored: Dict[MemoryType, List[ScoredCandidate]]) -> Dict[MemoryType, List[ScoredCandidate]]:
        normalized: Dict[MemoryType, List[ScoredCandidate]] = {}
        for channel, items in scored.items():
            raw_values = [item.raw_score for item in items]
            if not raw_values:
                normalized[channel] = []
                continue

            if self.mode == "robust":
                zs = robust_zscore(raw_values)
            else:
                mu = mean(raw_values)
                sigma = pstdev(raw_values) or 1.0
                zs = [(v - mu) / sigma for v in raw_values]

            for item, z in zip(items, zs):
                item.normalized_score = z
            normalized[channel] = items
        return normalized
