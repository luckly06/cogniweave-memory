from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from .enums import InjectPolicy, MemoryType
from .models import ActiveContext, MemoryRecord, ScoredCandidate, TaskContext, WorkingMemoryItem
from .utils import normalize_text, simple_keyword_summary, tokenize, truncate


class ConflictResolver:
    def resolve(self, items: Sequence[ScoredCandidate]) -> List[ScoredCandidate]:
        grouped: Dict[Tuple[MemoryType, str], List[ScoredCandidate]] = defaultdict(list)
        for item in items:
            signature = " ".join(sorted(set(tokenize(item.record.summary or item.record.content)))[:12])
            grouped[(item.channel, signature)].append(item)

        resolved: List[ScoredCandidate] = []
        for _, group in grouped.items():
            if len(group) == 1:
                resolved.extend(group)
                continue
            group.sort(
                key=lambda x: (
                    x.record.confidence,
                    x.record.importance,
                    x.unified_score,
                    x.raw_score,
                ),
                reverse=True,
            )
            keep = group[0]
            keep.record.metadata["conflict_flag"] = True
            keep.record.metadata["conflict_candidates"] = [g.record.memory_id for g in group[1:]]
            keep.record.metadata["conflict_ratio"] = len(group[1:]) / max(len(group), 1)
            resolved.append(keep)
        return resolved


class Compressor:
    def __init__(self, summary_char_limit: int = 320):
        self.summary_char_limit = summary_char_limit

    def compress(self, record: MemoryRecord, task_context: TaskContext) -> str:
        text = record.summary or record.content
        if len(text) <= self.summary_char_limit:
            return text
        return simple_keyword_summary(text, limit=self.summary_char_limit)


class ContextOrchestrator:
    def __init__(self, forget_manager=None, compressor: Compressor | None = None, resolver: ConflictResolver | None = None):
        self.forget_manager = forget_manager
        self.compressor = compressor or Compressor()
        self.resolver = resolver or ConflictResolver()

    def _dedup(self, selected: Sequence[ScoredCandidate]) -> List[ScoredCandidate]:
        seen = set()
        out = []
        for item in selected:
            signature = (item.channel.value, normalize_text(item.record.summary or item.record.content))
            if signature in seen:
                continue
            seen.add(signature)
            out.append(item)
        return out

    def _usage_hint(self, memory_type: MemoryType) -> str:
        mapping = {
            MemoryType.KEY: "硬约束或长期偏好，优先遵守。",
            MemoryType.SEMANTIC: "回答事实、规则、知识问题时优先引用。",
            MemoryType.EPISODIC: "补充最近事件、会话经过或任务上下文。",
            MemoryType.PERCEPTUAL: "补充视觉对象、布局、场景与多模态线索。",
            MemoryType.EXPERIENCE: "优先作为策略模板、调试经验或复用方案。",
            MemoryType.SENSORY: "短暂感知线索，只在本轮谨慎参考。",
        }
        return mapping[memory_type]

    def _structuring(self, selected: Sequence[ScoredCandidate], task_context: TaskContext):
        retrieve_items: List[WorkingMemoryItem] = []
        tool_only_items: List[WorkingMemoryItem] = []

        for item in selected:
            summary = self.compressor.compress(item.record, task_context)
            wm = WorkingMemoryItem(
                memory_id=item.record.memory_id,
                channel=item.channel,
                summary=summary,
                evidence=item.record.source_refs[:3] or [truncate(item.record.content, 180)],
                importance=item.record.importance,
                confidence=item.record.confidence,
                usage_hint=self._usage_hint(item.channel),
                conflict_flag=bool(item.record.metadata.get("conflict_flag")),
                expires_in_turns=3 if item.channel == MemoryType.EXPERIENCE else 2,
                metadata={
                    "inject_policy": (
                        InjectPolicy.RETRIEVE.value
                        if item.unified_score > -0.75
                        else InjectPolicy.TOOL_ONLY.value
                    )
                },
            )
            if item.unified_score > -0.75:
                retrieve_items.append(wm)
            else:
                tool_only_items.append(wm)

        return retrieve_items, tool_only_items

    def build_context(
        self,
        system_prompt: str,
        task_goal: str,
        task_context: TaskContext,
        key_items: List[MemoryRecord],
        selected: List[ScoredCandidate],
        sensory_items: List[dict],
        recent_dialogue: List[Dict[str, str]],
        few_shots: List[str] | None = None,
        tool_schemas: List[Dict[str, str]] | None = None,
    ) -> ActiveContext:
        selected = self._dedup(selected)
        selected = self.resolver.resolve(selected)
        retrieve_items, tool_only_items = self._structuring(selected, task_context)

        key_working = [
            WorkingMemoryItem(
                memory_id=record.memory_id,
                channel=MemoryType.KEY,
                summary=record.summary or record.content,
                evidence=record.source_refs[:3],
                importance=record.importance,
                confidence=record.confidence,
                usage_hint="高优先级强制注入。",
                expires_in_turns=999,
                metadata={"inject_policy": InjectPolicy.ALWAYS.value},
            )
            for record in key_items
        ]

        sensory_working = [
            WorkingMemoryItem(
                memory_id=item.get("candidate_id", f"sensory::{idx}"),
                channel=MemoryType.SENSORY,
                summary=item.get("summary") or item.get("input", ""),
                evidence=[str(item.get("input", ""))[:180]],
                importance=float(item.get("importance", 0.5)),
                confidence=float(item.get("confidence", 0.4)),
                usage_hint=self._usage_hint(MemoryType.SENSORY),
                expires_in_turns=1,
                metadata={"inject_policy": InjectPolicy.RETRIEVE.value, **item},
            )
            for idx, item in enumerate(sensory_items)
            if item.get("summary") or item.get("input")
        ]

        if self.forget_manager:
            for item in retrieve_items:
                self.forget_manager.touch(item.memory_id, used_in_context=True)

        return ActiveContext(
            system_prompt=system_prompt,
            current_task_goal=task_goal,
            key_items=key_working,
            retrieved_items=retrieve_items,
            sensory_items=sensory_working,
            recent_dialogue=recent_dialogue,
            trace_summary=str(task_context.metadata.get("trace_summary", "")),
            few_shots=few_shots or [],
            tool_only_candidates=tool_only_items,
            tool_schemas=tool_schemas or [],
            tool_protocol=(
                "When tools are needed, respond in JSON with fields: thought, tool_calls, final_answer. "
                "Tool calls must include name and arguments."
            ),
        )
