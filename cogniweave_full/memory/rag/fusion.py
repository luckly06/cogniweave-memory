from __future__ import annotations

from typing import Dict, List

from ..base import BaseFusionPolicy
from ..enums import MemoryType, TaskType
from ..models import MemoryRecord, ScoredCandidate, TaskContext


class FusionPolicy(BaseFusionPolicy):
    def __init__(self):
        self._weights = {
            TaskType.KNOWLEDGE_QA: {
                MemoryType.KEY: 0.20,
                MemoryType.SEMANTIC: 0.45,
                MemoryType.EPISODIC: 0.10,
                MemoryType.PERCEPTUAL: 0.05,
                MemoryType.EXPERIENCE: 0.20,
            },
            TaskType.DIALOGUE_CONTINUATION: {
                MemoryType.KEY: 0.20,
                MemoryType.SEMANTIC: 0.15,
                MemoryType.EPISODIC: 0.40,
                MemoryType.PERCEPTUAL: 0.05,
                MemoryType.EXPERIENCE: 0.20,
            },
            TaskType.IMAGE_UNDERSTANDING: {
                MemoryType.KEY: 0.10,
                MemoryType.SEMANTIC: 0.15,
                MemoryType.EPISODIC: 0.10,
                MemoryType.PERCEPTUAL: 0.45,
                MemoryType.EXPERIENCE: 0.20,
            },
            TaskType.MULTIMODAL_REASONING: {
                MemoryType.KEY: 0.15,
                MemoryType.SEMANTIC: 0.20,
                MemoryType.EPISODIC: 0.15,
                MemoryType.PERCEPTUAL: 0.30,
                MemoryType.EXPERIENCE: 0.20,
            },
            TaskType.PLANNING: {
                MemoryType.KEY: 0.15,
                MemoryType.SEMANTIC: 0.20,
                MemoryType.EPISODIC: 0.10,
                MemoryType.PERCEPTUAL: 0.00,
                MemoryType.EXPERIENCE: 0.55,
            },
            TaskType.CODING: {
                MemoryType.KEY: 0.15,
                MemoryType.SEMANTIC: 0.20,
                MemoryType.EPISODIC: 0.10,
                MemoryType.PERCEPTUAL: 0.00,
                MemoryType.EXPERIENCE: 0.55,
            },
        }
        self.duplicate_penalty = 0.15
        self.conflict_penalty = 0.20
        self.feedback_bias: Dict[str, float] = {}

    def weights_for(self, task_type: TaskType) -> Dict[MemoryType, float]:
        weights = dict(self._weights[task_type])
        if not self.feedback_bias:
            return weights

        adjusted = {}
        total = 0.0
        for channel, weight in weights.items():
            bias = self.feedback_bias.get(channel.value, 0.0)
            scaled = max(0.0, weight * (1.0 + bias * 0.15))
            adjusted[channel] = scaled
            total += scaled

        if total <= 0:
            return weights
        return {channel: value / total for channel, value in adjusted.items()}

    def apply_feedback_bias(self, bias: Dict[str, float]) -> None:
        self.feedback_bias = dict(bias)

    def fuse(self, normalized: Dict[MemoryType, List[ScoredCandidate]], key_items: List[MemoryRecord], task_context: TaskContext, k_context: int) -> List[ScoredCandidate]:
        weights = self.weights_for(task_context.task_type)
        merged: List[ScoredCandidate] = []
        seen_signatures = set()

        for channel, items in normalized.items():
            w = weights.get(channel, 0.0)
            for item in items:
                signature = (item.channel.value, (item.record.summary or item.record.content).strip().lower())
                duplicate = signature in seen_signatures
                seen_signatures.add(signature)
                key_linked = bool(set(item.record.tags) & {t for record in key_items for t in record.tags})
                conflict = bool(item.record.metadata.get("conflict_flag"))
                item.unified_score = (
                    w * item.normalized_score
                    + (0.08 if key_linked else 0.0)
                    - (self.duplicate_penalty if duplicate else 0.0)
                    - (self.conflict_penalty if conflict else 0.0)
                )
                merged.append(item)

        merged.sort(key=lambda x: x.unified_score, reverse=True)
        return merged[:k_context]
