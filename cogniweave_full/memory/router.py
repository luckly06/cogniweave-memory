from __future__ import annotations

import hashlib
from typing import List

from .enums import InjectPolicy, MemoryScope, MemoryType, ModalityType, TaskType, WritePolicy
from .models import ActiveContext, ExecutionResult, MemoryDecision, RawInput, TaskContext
from .utils import estimate_ambiguity, estimate_complexity, normalize_text


class TaskModalityRouter:
    def route(self, raw_input: RawInput) -> TaskContext:
        text = "" if raw_input.content is None else str(raw_input.content)
        complexity = estimate_complexity(text)
        ambiguity = estimate_ambiguity(text)
        token_budget = int(raw_input.metadata.get("token_budget", 4000))
        context_slots = int(raw_input.metadata.get("context_slots", 8))
        modality = raw_input.modality

        text_norm = normalize_text(text)
        if modality == ModalityType.IMAGE:
            task_type = TaskType.IMAGE_UNDERSTANDING
            channels = [MemoryType.KEY, MemoryType.PERCEPTUAL, MemoryType.EPISODIC]
        elif modality == ModalityType.MULTIMODAL:
            task_type = TaskType.MULTIMODAL_REASONING
            channels = [
                MemoryType.KEY,
                MemoryType.SEMANTIC,
                MemoryType.EPISODIC,
                MemoryType.PERCEPTUAL,
                MemoryType.EXPERIENCE,
            ]
        elif any(k in text_norm for k in ["plan", "规划", "步骤", "roadmap"]):
            task_type = TaskType.PLANNING
            channels = [MemoryType.KEY, MemoryType.SEMANTIC, MemoryType.EPISODIC, MemoryType.EXPERIENCE]
        elif any(k in text_norm for k in ["code", "python", "bug", "debug", "函数", "代码", "调试"]):
            task_type = TaskType.CODING
            channels = [MemoryType.KEY, MemoryType.SEMANTIC, MemoryType.EXPERIENCE, MemoryType.EPISODIC]
        elif any(k in text_norm for k in ["继续", "remember", "我们刚才", "刚刚", "前面"]):
            task_type = TaskType.DIALOGUE_CONTINUATION
            channels = [MemoryType.KEY, MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.EXPERIENCE]
        else:
            task_type = TaskType.KNOWLEDGE_QA
            channels = [MemoryType.KEY, MemoryType.SEMANTIC, MemoryType.EPISODIC, MemoryType.EXPERIENCE]

        if "image" in text_norm or "图像" in text_norm:
            if MemoryType.PERCEPTUAL not in channels:
                channels.append(MemoryType.PERCEPTUAL)

        return TaskContext(
            task_type=task_type,
            task_complexity=complexity,
            token_budget=token_budget,
            context_slots=context_slots,
            candidate_channels=channels,
            modality_type=modality,
            ambiguity=ambiguity,
            retrieval_cost=min(1.0, 0.2 + complexity * 0.5),
            metadata={"query_hash": hashlib.md5(text.encode("utf-8")).hexdigest()},
        )


class PostRunMemoryRouter:
    def decide(
        self,
        raw_input: RawInput,
        task_context: TaskContext,
        active_context: ActiveContext,
        execution_result: ExecutionResult,
        extracted_candidates: List[dict],
    ) -> List[MemoryDecision]:
        decisions: List[MemoryDecision] = []
        write_threshold = float(task_context.metadata.get("write_threshold", 0.65))
        key_promotion_threshold = float(task_context.metadata.get("key_promotion_threshold", 0.85))
        tool_only_threshold = float(task_context.metadata.get("tool_only_confidence_threshold", 0.55))
        force_inject_threshold = float(task_context.metadata.get("force_inject_threshold", 0.85))
        for candidate in extracted_candidates:
            importance = float(candidate.get("importance", 0.5))
            novelty = float(candidate.get("novelty", 0.5))
            consistency = float(candidate.get("consistency", 0.5))
            confidence = float(candidate.get("confidence", 0.5))
            reusability = float(candidate.get("reusability", 0.5))
            stability = float(candidate.get("stability", 0.5))
            text = normalize_text(candidate.get("content", ""))

            declared_memory_type = candidate.get("memory_type")
            memory_type = (
                MemoryType(declared_memory_type)
                if declared_memory_type
                else self._classify(text, task_context, candidate)
            )

            total_value = (
                0.24 * importance
                + 0.20 * novelty
                + 0.16 * consistency
                + 0.15 * confidence
                + 0.15 * reusability
                + 0.10 * stability
            )

            if total_value < max(0.30, write_threshold - 0.30):
                write_policy = WritePolicy.DROP
            elif total_value < max(0.45, write_threshold - 0.10):
                write_policy = WritePolicy.BUFFER
            elif total_value < write_threshold:
                write_policy = WritePolicy.SUMMARY
            else:
                write_policy = WritePolicy.COMMIT

            if memory_type == MemoryType.DISCARD:
                write_policy = WritePolicy.DROP

            inject_policy = InjectPolicy.ALWAYS if memory_type == MemoryType.KEY else InjectPolicy.RETRIEVE
            if candidate.get("inject_policy_hint") == InjectPolicy.TOOL_ONLY.value:
                inject_policy = InjectPolicy.TOOL_ONLY
            elif candidate.get("inject_policy_hint") == InjectPolicy.ALWAYS.value:
                inject_policy = InjectPolicy.ALWAYS
            elif memory_type in {MemoryType.PERCEPTUAL, MemoryType.EPISODIC, MemoryType.SEMANTIC} and confidence < tool_only_threshold:
                inject_policy = InjectPolicy.TOOL_ONLY
            if candidate.get("sticky"):
                write_policy = WritePolicy.COMMIT
                inject_policy = InjectPolicy.ALWAYS
            if total_value >= force_inject_threshold and candidate.get("metadata", {}).get("supporting_memory_ids"):
                inject_policy = InjectPolicy.ALWAYS
            if memory_type == MemoryType.SEMANTIC and total_value >= key_promotion_threshold and candidate.get("source") == "user_preference":
                memory_type = MemoryType.KEY
                inject_policy = InjectPolicy.ALWAYS
                write_policy = WritePolicy.COMMIT

            decisions.append(
                MemoryDecision(
                    candidate_id=candidate["candidate_id"],
                    memory_type=memory_type,
                    importance=importance,
                    novelty=novelty,
                    consistency=consistency,
                    confidence=confidence,
                    scope=self._scope_for(memory_type, candidate),
                    write_policy=write_policy,
                    inject_policy=inject_policy,
                    stability=stability,
                    reusability=reusability,
                    ttl="long" if memory_type in {MemoryType.KEY, MemoryType.SEMANTIC, MemoryType.EXPERIENCE} else "mid",
                    rationale=candidate.get("rationale", ""),
                )
            )
        return decisions

    def _classify(self, text: str, task_context: TaskContext, candidate: dict) -> MemoryType:
        classifier_bias = task_context.metadata.get("classifier_bias", {})
        scores = {
            MemoryType.KEY: float(classifier_bias.get(MemoryType.KEY.value, 0.0)),
            MemoryType.SEMANTIC: float(classifier_bias.get(MemoryType.SEMANTIC.value, 0.0)),
            MemoryType.EPISODIC: float(classifier_bias.get(MemoryType.EPISODIC.value, 0.0)),
            MemoryType.PERCEPTUAL: float(classifier_bias.get(MemoryType.PERCEPTUAL.value, 0.0)),
            MemoryType.EXPERIENCE: float(classifier_bias.get(MemoryType.EXPERIENCE.value, 0.0)),
        }
        if any(k in text for k in ["以后", "偏好", "总是", "不要", "规则", "默认"]) or candidate.get("sticky"):
            scores[MemoryType.KEY] += 0.45
        if candidate.get("source") == "perception" or any(k in text for k in ["图像", "视觉", "布局", "颜色", "scene", "object"]):
            scores[MemoryType.PERCEPTUAL] += 0.38
        if any(k in text for k in ["经验", "成功", "失败", "lesson", "strategy", "修复", "reuse"]):
            scores[MemoryType.EXPERIENCE] += 0.36
        if candidate.get("source") == "event" or any(k in text for k in ["今天", "这次", "刚刚", "任务", "会话", "过程"]):
            scores[MemoryType.EPISODIC] += 0.34
        if candidate.get("metadata", {}).get("entity_links"):
            scores[MemoryType.SEMANTIC] += 0.28
        if candidate.get("metadata", {}).get("objects") or candidate.get("metadata", {}).get("regions"):
            scores[MemoryType.PERCEPTUAL] += 0.22
        if candidate.get("metadata", {}).get("action_path"):
            scores[MemoryType.EXPERIENCE] += 0.24
        if candidate.get("metadata", {}).get("timeline"):
            scores[MemoryType.EPISODIC] += 0.22
        if len(text) < 6:
            return MemoryType.DISCARD
        best_type = max(scores, key=scores.get)
        if scores[best_type] <= 0.05:
            return MemoryType.SEMANTIC
        return best_type

    def _scope_for(self, memory_type: MemoryType, candidate: dict) -> MemoryScope:
        scope_hint = candidate.get("metadata", {}).get("scope_hint")
        if scope_hint:
            try:
                return MemoryScope(scope_hint)
            except Exception:
                pass
        if memory_type == MemoryType.KEY:
            return MemoryScope.USER
        if memory_type == MemoryType.EPISODIC:
            return MemoryScope.SESSION
        if memory_type == MemoryType.PERCEPTUAL:
            return MemoryScope.SESSION
        if memory_type == MemoryType.EXPERIENCE:
            return MemoryScope.TASK
        return MemoryScope.GLOBAL
