from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .enums import (
    InjectPolicy,
    MemoryScope,
    MemoryType,
    ModalityType,
    TaskType,
    WritePolicy,
)


def utc_now() -> datetime:
    return datetime.utcnow()


@dataclass
class RawInput:
    user_id: str
    session_id: str
    turn_id: str
    modality: ModalityType
    content: Any
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskContext:
    task_type: TaskType
    task_complexity: float
    token_budget: int
    context_slots: int
    candidate_channels: List[MemoryType]
    modality_type: ModalityType
    ambiguity: float = 0.0
    retrieval_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryRecord:
    memory_id: str
    memory_type: MemoryType
    scope: MemoryScope
    content: str
    summary: str = ""
    embedding: Optional[List[float]] = None
    graph_refs: List[str] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5
    confidence: float = 0.5
    recency: float = 1.0
    novelty: float = 0.5
    consistency: float = 0.5
    reuse_score: float = 0.5
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Forget 生命周期字段
    last_access_at: Optional[datetime] = None
    access_count: int = 0
    hit_count: int = 0
    use_count: int = 0
    pinned: bool = False
    archived: bool = False
    ttl_seconds: Optional[int] = None
    decay_rate: float = 1.0
    parent_memory_id: Optional[str] = None
    child_memory_ids: List[str] = field(default_factory=list)


@dataclass
class CandidateSet:
    channel: MemoryType
    items: List[MemoryRecord]


@dataclass
class ScoredCandidate:
    record: MemoryRecord
    channel: MemoryType
    raw_score: float
    normalized_score: float = 0.0
    unified_score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class WorkingMemoryItem:
    memory_id: str
    channel: MemoryType
    summary: str
    evidence: List[str] = field(default_factory=list)
    importance: float = 0.0
    confidence: float = 0.0
    usage_hint: str = ""
    conflict_flag: bool = False
    expires_in_turns: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActiveContext:
    system_prompt: str
    current_task_goal: str
    key_items: List[WorkingMemoryItem]
    retrieved_items: List[WorkingMemoryItem]
    sensory_items: List[WorkingMemoryItem]
    recent_dialogue: List[Dict[str, str]]
    trace_summary: str = ""
    tool_protocol: str = ""
    output_schema: str = ""
    few_shots: List[str] = field(default_factory=list)
    tool_only_candidates: List[WorkingMemoryItem] = field(default_factory=list)
    tool_schemas: List[Dict[str, Any]] = field(default_factory=list)

    def to_messages(self) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        compiled: List[str] = []
        if self.current_task_goal:
            compiled.append("Current Task Goal:\n" + self.current_task_goal)
        if self.key_items:
            compiled.append("Key Memory:\n" + "\n".join(f"- {x.summary}" for x in self.key_items))
        if self.retrieved_items:
            compiled.append(
                "Retrieved Working Memory:\n"
                + "\n".join(f"- [{x.channel.value}] {x.summary}" for x in self.retrieved_items)
            )
        if self.sensory_items:
            compiled.append(
                "Sensory Buffer:\n"
                + "\n".join(f"- {x.summary}" for x in self.sensory_items)
            )
        if self.tool_only_candidates:
            compiled.append("Tool-only memory candidates are available via memory_search tool.")
        if self.trace_summary:
            compiled.append("Older Execution Summary:\n" + self.trace_summary)
        if self.output_schema:
            compiled.append("Output Schema:\n" + self.output_schema)
        if self.tool_protocol:
            compiled.append("Tool Protocol:\n" + self.tool_protocol)
        if self.tool_schemas:
            compiled.append(
                "Available Tools:\n"
                + "\n".join(
                    f"- {tool['name']}: {tool.get('description', '')}"
                    for tool in self.tool_schemas
                )
            )
        if self.few_shots:
            compiled.append("Few Shots:\n" + "\n\n".join(self.few_shots))

        if compiled:
            messages.append({"role": "system", "content": "\n\n".join(compiled)})

        messages.extend(self.recent_dialogue)
        return messages


@dataclass
class ExecutionTrace:
    thought: str = ""
    action: str = ""
    observation: str = ""
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_output: Any = None
    timestamp: datetime = field(default_factory=utc_now)


@dataclass
class ExecutionResult:
    final_answer: str
    traces: List[ExecutionTrace] = field(default_factory=list)
    outcome: str = "success"
    feedback: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryDecision:
    candidate_id: str
    memory_type: MemoryType
    importance: float
    novelty: float
    consistency: float
    confidence: float
    scope: MemoryScope
    write_policy: WritePolicy
    inject_policy: InjectPolicy
    stability: float = 0.5
    reusability: float = 0.5
    ttl: str = ""
    rationale: str = ""


@dataclass
class RetrievalConfig:
    k_retrieve: int = 12
    k_context: int = 6
    enable_key_memory: bool = True
    enable_semantic: bool = True
    enable_episodic: bool = True
    enable_perceptual: bool = True
    enable_experience: bool = True


@dataclass
class PolicyState:
    write_threshold: float = 0.65
    key_promotion_threshold: float = 0.85
    duplicate_penalty: float = 0.15
    conflict_penalty: float = 0.20
    context_expand_factor: float = 1.0
    retrieval_expand_factor: float = 1.0
    retrieval_bias: Dict[str, float] = field(default_factory=dict)
    classifier_bias: Dict[str, float] = field(default_factory=dict)
    tool_only_confidence_threshold: float = 0.55
    force_inject_threshold: float = 0.85
