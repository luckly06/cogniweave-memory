from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .enums import MemoryType, TaskType
from .models import PolicyState


@dataclass
class FeedbackEvent:
    task_type: TaskType
    used_channels: List[MemoryType]
    success: bool
    score: float


class FeedbackCollector:
    def __init__(self):
        self.events: List[FeedbackEvent] = []

    def add_event(self, event: FeedbackEvent) -> None:
        self.events.append(event)

    def recent_events(self, limit: int = 100) -> List[FeedbackEvent]:
        return self.events[-limit:]


class PolicyUpdater:
    def __init__(self):
        self.state = PolicyState()

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def update_retrieval_bias(self, events: List[FeedbackEvent]) -> Dict[str, float]:
        if not events:
            return {}

        stats: Dict[str, List[float]] = {}
        for event in events:
            for channel in event.used_channels:
                stats.setdefault(channel.value, [])
                stats[channel.value].append(event.score if event.success else -abs(event.score))

        bias = {}
        for channel, values in stats.items():
            bias[channel] = sum(values) / max(len(values), 1)

        return bias

    def update_policy_state(self, events: List[FeedbackEvent]) -> PolicyState:
        if not events:
            return self.state

        recent = events[-20:]
        avg_score = sum(event.score if event.success else -abs(event.score) for event in recent) / max(len(recent), 1)
        success_rate = sum(1 for event in recent if event.success) / max(len(recent), 1)
        bias = self.update_retrieval_bias(recent)
        self.state.retrieval_bias = bias
        self.state.context_expand_factor = 1.15 if avg_score < 0.3 else 1.0
        self.state.retrieval_expand_factor = 1.20 if success_rate < 0.7 else 1.0
        self.state.write_threshold = 0.60 if success_rate > 0.85 else 0.68
        self.state.key_promotion_threshold = 0.80 if avg_score > 0.6 else 0.88
        self.state.classifier_bias = {
            channel: self._clamp(value * 0.08, -0.12, 0.12)
            for channel, value in bias.items()
        }
        perceptual_bias = bias.get(MemoryType.PERCEPTUAL.value, 0.0)
        episodic_bias = bias.get(MemoryType.EPISODIC.value, 0.0)
        semantic_bias = bias.get(MemoryType.SEMANTIC.value, 0.0)
        experience_bias = bias.get(MemoryType.EXPERIENCE.value, 0.0)
        key_bias = bias.get(MemoryType.KEY.value, 0.0)

        tool_only = 0.55
        if perceptual_bias < -0.20 or episodic_bias < -0.20:
            tool_only += 0.05
        if semantic_bias > 0.25 or experience_bias > 0.25:
            tool_only -= 0.03
        self.state.tool_only_confidence_threshold = self._clamp(tool_only, 0.45, 0.75)

        force_inject = 0.85
        if key_bias > 0.20 or avg_score > 0.60:
            force_inject -= 0.04
        if success_rate < 0.60:
            force_inject += 0.03
        self.state.force_inject_threshold = self._clamp(force_inject, 0.72, 0.92)
        return self.state

    def apply(self, events: List[FeedbackEvent], fusion_policy, forget_policy) -> Dict[str, float]:
        state = self.update_policy_state(events)
        bias = state.retrieval_bias
        if hasattr(fusion_policy, "apply_feedback_bias"):
            fusion_policy.apply_feedback_bias(bias)

        for channel, value in bias.items():
            profile = forget_policy.profiles.get(channel)
            if not profile:
                continue
            if value > 0.25:
                profile.min_retention_score = max(0.05, profile.min_retention_score - 0.02)
            elif value < -0.25:
                profile.min_retention_score = min(0.9, profile.min_retention_score + 0.02)

        return bias
