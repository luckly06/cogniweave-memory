from __future__ import annotations

import queue
import threading
import uuid
from typing import Dict, List, Optional

from .enums import MemoryScope, MemoryType, TaskType
from .models import MemoryRecord
from .rag.document import DocumentIngestionService
from .utils import simple_keyword_summary, stable_uuid, tokenize, utc_now


class CandidateExtractor:
    STOPWORDS = {
        "the", "and", "for", "with", "this", "that", "then", "from", "into",
        "用户", "系统", "需要", "可以", "当前", "本轮", "一个", "进行", "使用", "回答",
    }

    def _build_candidate(self, content: str, **kwargs) -> dict:
        return {
            "candidate_id": str(uuid.uuid4()),
            "content": content,
            "summary": kwargs.get("summary", simple_keyword_summary(content, 240)),
            "importance": float(kwargs.get("importance", 0.5)),
            "novelty": float(kwargs.get("novelty", 0.5)),
            "consistency": float(kwargs.get("consistency", 0.5)),
            "confidence": float(kwargs.get("confidence", 0.5)),
            "reusability": float(kwargs.get("reusability", 0.5)),
            "stability": float(kwargs.get("stability", 0.5)),
            "source": kwargs.get("source", "unknown"),
            "memory_type": kwargs.get("memory_type"),
            "sticky": bool(kwargs.get("sticky", False)),
            "inject_policy_hint": kwargs.get("inject_policy_hint", ""),
            "rationale": kwargs.get("rationale", ""),
            "tags": list(kwargs.get("tags", [])),
            "graph_refs": list(kwargs.get("graph_refs", [])),
            "source_refs": list(kwargs.get("source_refs", [])),
            "metadata": dict(kwargs.get("metadata", {})),
            "ttl_seconds": kwargs.get("ttl_seconds"),
            "pinned": bool(kwargs.get("pinned", False)),
        }

    def _merge_unique(self, *groups) -> List[str]:
        values: List[str] = []
        for group in groups:
            if not group:
                continue
            if isinstance(group, str):
                group = [group]
            for item in group:
                if item and item not in values:
                    values.append(item)
        return values

    def _salient_terms(self, *texts: str, limit: int = 8) -> List[str]:
        terms: List[str] = []
        for text in texts:
            for token in tokenize(text or ""):
                if len(token) <= 1 or token.isdigit() or token in self.STOPWORDS:
                    continue
                if token not in terms:
                    terms.append(token)
                if len(terms) >= limit:
                    return terms
        return terms

    def _collect_active_support(self, active_context) -> Dict[str, object]:
        support = {
            "supporting_memory_ids": [],
            "supporting_summaries": [],
            "linked_key_ids": [],
            "related_semantic_ids": [],
            "related_episodic_ids": [],
            "related_experience_ids": [],
            "related_perceptual_ids": [],
            "source_memory_ids": [],
            "key_fact_summaries": [],
            "sensory_summaries": [],
            "tool_only_memory_ids": [],
            "used_channels": [],
            "task_scope_terms": [],
        }
        if not active_context:
            return support

        for item in getattr(active_context, "key_items", []):
            support["supporting_memory_ids"] = self._merge_unique(support["supporting_memory_ids"], item.memory_id)
            support["linked_key_ids"] = self._merge_unique(support["linked_key_ids"], item.memory_id)
            support["source_memory_ids"] = self._merge_unique(support["source_memory_ids"], item.memory_id)
            support["supporting_summaries"] = self._merge_unique(support["supporting_summaries"], item.summary)
            support["key_fact_summaries"] = self._merge_unique(support["key_fact_summaries"], item.summary)
            support["used_channels"] = self._merge_unique(support["used_channels"], item.channel.value)

        for item in getattr(active_context, "retrieved_items", []):
            support["supporting_memory_ids"] = self._merge_unique(support["supporting_memory_ids"], item.memory_id)
            support["source_memory_ids"] = self._merge_unique(support["source_memory_ids"], item.memory_id)
            support["supporting_summaries"] = self._merge_unique(support["supporting_summaries"], item.summary)
            support["used_channels"] = self._merge_unique(support["used_channels"], item.channel.value)
            if item.channel == MemoryType.SEMANTIC:
                support["related_semantic_ids"] = self._merge_unique(support["related_semantic_ids"], item.memory_id)
            elif item.channel == MemoryType.EPISODIC:
                support["related_episodic_ids"] = self._merge_unique(support["related_episodic_ids"], item.memory_id)
            elif item.channel == MemoryType.EXPERIENCE:
                support["related_experience_ids"] = self._merge_unique(support["related_experience_ids"], item.memory_id)
            elif item.channel == MemoryType.PERCEPTUAL:
                support["related_perceptual_ids"] = self._merge_unique(support["related_perceptual_ids"], item.memory_id)

        for item in getattr(active_context, "sensory_items", []):
            support["sensory_summaries"] = self._merge_unique(support["sensory_summaries"], item.summary)
            support["used_channels"] = self._merge_unique(support["used_channels"], item.channel.value)

        for item in getattr(active_context, "tool_only_candidates", []):
            support["tool_only_memory_ids"] = self._merge_unique(support["tool_only_memory_ids"], item.memory_id)

        support["task_scope_terms"] = self._salient_terms(
            getattr(active_context, "current_task_goal", ""),
            " ".join(support["supporting_summaries"]),
        )
        return support

    def _regions_from_text(self, text: str) -> List[str]:
        markers = ["left", "right", "top", "bottom", "center", "左侧", "右侧", "上方", "下方", "中间"]
        text_norm = (text or "").lower()
        return [marker for marker in markers if marker in text_norm or marker in (text or "")]

    def extract(
        self,
        input_text: str,
        final_answer: str,
        traces: List[dict] | None = None,
        task_context=None,
        execution_result=None,
        active_context=None,
        sensory_candidates: List[dict] | None = None,
        feedback: str = "",
    ) -> List[dict]:
        candidates: List[dict] = []
        traces = traces or []
        sensory_candidates = sensory_candidates or []
        task_type = getattr(task_context, "task_type", TaskType.KNOWLEDGE_QA)
        outcome = getattr(execution_result, "outcome", "success")
        used_channels = getattr(execution_result, "metadata", {}).get("used_channels", [])
        combined_answer = (final_answer or "").strip()
        normalized_input = (input_text or "").strip()
        support = self._collect_active_support(active_context)
        task_scope_terms = self._salient_terms(normalized_input, combined_answer, limit=10) or support["task_scope_terms"]
        policy_scope = [task_type.value, "all"]

        if any(marker in normalized_input for marker in ["记住", "以后", "偏好", "默认", "不要", "总是"]):
            candidates.append(
                self._build_candidate(
                    normalized_input,
                    importance=0.95,
                    novelty=0.75,
                    consistency=0.85,
                    confidence=0.9,
                    reusability=0.95,
                    stability=0.95,
                    sticky=True,
                    source="user_preference",
                    memory_type=MemoryType.KEY.value,
                    pinned=True,
                    tags=["preference", "policy"],
                    inject_policy_hint="always",
                    metadata={
                        "task_scope_terms": task_scope_terms,
                        "policy_scope": policy_scope,
                        "scope_hint": MemoryScope.USER.value,
                        "supporting_memory_ids": support["supporting_memory_ids"],
                        "linked_key_ids": support["linked_key_ids"],
                    },
                )
            )

        if combined_answer and task_type in {
            TaskType.KNOWLEDGE_QA,
            TaskType.MULTIMODAL_REASONING,
            TaskType.IMAGE_UNDERSTANDING,
            TaskType.PLANNING,
            TaskType.CODING,
        }:
            entity_links = self._salient_terms(
                combined_answer,
                " ".join(support["supporting_summaries"]),
                limit=10,
            )
            candidates.append(
                self._build_candidate(
                    combined_answer,
                    importance=0.72,
                    novelty=0.58,
                    consistency=0.72,
                    confidence=0.76,
                    reusability=0.68,
                    stability=0.7,
                    source="assistant_knowledge",
                    memory_type=MemoryType.SEMANTIC.value,
                    tags=["answer", task_type.value],
                    graph_refs=[f"entity::{term}" for term in entity_links[:6]],
                    source_refs=[f"memory://{memory_id}" for memory_id in support["source_memory_ids"][:6]],
                    metadata={
                        "used_channels": used_channels,
                        "supporting_memory_ids": support["supporting_memory_ids"],
                        "linked_key_ids": support["linked_key_ids"],
                        "source_memory_ids": support["source_memory_ids"],
                        "task_scope_terms": task_scope_terms,
                        "policy_scope": policy_scope,
                        "entity_links": entity_links,
                        "supporting_summaries": support["supporting_summaries"][:6],
                    },
                )
            )

        if normalized_input or combined_answer:
            episodic_text = simple_keyword_summary(
                f"任务输入：{normalized_input}\n执行结果：{outcome}\n最终回答：{combined_answer}",
                240,
            )
            candidates.append(
                self._build_candidate(
                    episodic_text,
                    importance=0.66,
                    novelty=0.52,
                    consistency=0.75,
                    confidence=0.73,
                    reusability=0.55,
                    stability=0.62,
                    source="event",
                    memory_type=MemoryType.EPISODIC.value,
                    tags=["session_event", task_type.value],
                    source_refs=[f"memory://{memory_id}" for memory_id in support["supporting_memory_ids"][:6]],
                    metadata={
                        "timeline": {
                            "task_type": task_type.value,
                            "outcome": outcome,
                        },
                        "supporting_memory_ids": support["supporting_memory_ids"],
                        "supporting_summaries": support["supporting_summaries"][:5],
                        "scope_hint": MemoryScope.SESSION.value,
                    },
                )
            )

        if traces:
            tool_names = [trace.get("tool_name", "") for trace in traces if trace.get("tool_name")]
            lessons = [
                trace.get("observation", "")
                for trace in traces
                if trace.get("observation")
            ]
            action_path = tool_names or ["direct_reasoning"]
            problem_pattern = simple_keyword_summary(normalized_input or getattr(active_context, "current_task_goal", ""), 120)
            context_signature = simple_keyword_summary(
                "\n".join(support["supporting_summaries"][:4]) or getattr(active_context, "trace_summary", ""),
                160,
            )
            lesson_learned = simple_keyword_summary(" | ".join(lessons) or combined_answer, 180)
            experience_text = simple_keyword_summary(
                (
                    f"task_type={task_type.value}\n"
                    f"actions={' -> '.join(action_path)}\n"
                    f"outcome={outcome}\n"
                    f"lessons={lesson_learned}"
                ),
                260,
            )
            candidates.append(
                self._build_candidate(
                    experience_text,
                    importance=0.78,
                    novelty=0.6,
                    consistency=0.8,
                    confidence=0.78,
                    reusability=0.82,
                    stability=0.78,
                    source="execution_trace",
                    memory_type=MemoryType.EXPERIENCE.value,
                    tags=["experience", task_type.value],
                    source_refs=[f"memory://{memory_id}" for memory_id in support["supporting_memory_ids"][:6]],
                    metadata={
                        "tool_names": tool_names,
                        "outcome": outcome,
                        "problem_pattern": problem_pattern,
                        "context_signature": context_signature,
                        "action_path": action_path,
                        "lesson_learned": lesson_learned,
                        "reuse_score": 0.82,
                        "related_episodic_ids": support["related_episodic_ids"],
                        "supporting_memory_ids": support["supporting_memory_ids"],
                        "scope_hint": MemoryScope.TASK.value,
                    },
                )
            )

        for sensory in sensory_candidates:
            summary = sensory.get("summary") or sensory.get("input") or ""
            if not summary:
                continue
            perceptual_terms = self._salient_terms(summary, combined_answer, limit=8)
            candidates.append(
                self._build_candidate(
                    summary,
                    importance=float(sensory.get("importance", 0.58)),
                    novelty=0.6,
                    consistency=float(sensory.get("confidence", 0.65)),
                    confidence=float(sensory.get("confidence", 0.65)),
                    reusability=0.56,
                    stability=float(sensory.get("stability", 0.65)),
                    source="perception",
                    memory_type=MemoryType.PERCEPTUAL.value,
                    ttl_seconds=int(sensory.get("ttl_seconds", 7 * 24 * 3600)),
                    tags=["sensory_promotion"],
                    source_refs=[f"memory://{memory_id}" for memory_id in support["related_semantic_ids"][:4]],
                    metadata={
                        "origin_modality": sensory.get("modality"),
                        "objects": sensory.get("objects") or perceptual_terms[:4],
                        "regions": sensory.get("regions") or self._regions_from_text(summary),
                        "visual_clues": sensory.get("visual_clues") or perceptual_terms[4:8],
                        "supporting_memory_ids": support["supporting_memory_ids"],
                        "related_semantic_ids": support["related_semantic_ids"],
                        "scope_hint": MemoryScope.SESSION.value,
                    },
                )
            )

        if feedback:
            candidates.append(
                self._build_candidate(
                    feedback,
                    importance=0.64,
                    novelty=0.55,
                    consistency=0.7,
                    confidence=0.7,
                    reusability=0.72,
                    stability=0.6,
                    source="feedback",
                    memory_type=MemoryType.EXPERIENCE.value,
                    tags=["feedback"],
                    metadata={
                        "problem_pattern": simple_keyword_summary(normalized_input, 120),
                        "context_signature": simple_keyword_summary(combined_answer, 120),
                        "action_path": [trace.get("tool_name", "") for trace in traces if trace.get("tool_name")] or ["direct_reasoning"],
                        "outcome": outcome,
                        "lesson_learned": simple_keyword_summary(feedback, 180),
                        "reuse_score": 0.72,
                        "related_episodic_ids": support["related_episodic_ids"],
                        "supporting_memory_ids": support["supporting_memory_ids"],
                    },
                )
            )

        return candidates


class Consolidator:
    STOPWORDS = CandidateExtractor.STOPWORDS

    def _merge_unique(self, *groups) -> List[str]:
        values: List[str] = []
        for group in groups:
            if not group:
                continue
            if isinstance(group, str):
                group = [group]
            for item in group:
                if item and item not in values:
                    values.append(item)
        return values

    def _salient_terms(self, *texts: str, limit: int = 10) -> List[str]:
        terms: List[str] = []
        for text in texts:
            for token in tokenize(text or ""):
                if len(token) <= 1 or token.isdigit() or token in self.STOPWORDS:
                    continue
                if token not in terms:
                    terms.append(token)
                if len(terms) >= limit:
                    return terms
        return terms

    def _base_record(
        self,
        candidate: dict,
        user_id: str,
        session_id: str,
        task_id: str,
        memory_type: MemoryType,
        scope: MemoryScope,
        content: str,
        summary: str,
        tags: List[str],
        graph_refs: List[str],
        source_refs: List[str],
        metadata: Dict[str, object],
    ) -> MemoryRecord:
        record_id = stable_uuid(
            memory_type.value,
            user_id,
            session_id,
            task_id,
            candidate.get("candidate_id"),
            summary or content[:120],
        )
        return MemoryRecord(
            memory_id=record_id,
            memory_type=memory_type,
            scope=scope,
            content=content,
            summary=summary,
            graph_refs=graph_refs,
            source_refs=source_refs,
            tags=tags,
            importance=float(candidate.get("importance", 0.5)),
            confidence=float(candidate.get("confidence", 0.5)),
            novelty=float(candidate.get("novelty", 0.5)),
            consistency=float(candidate.get("consistency", 0.5)),
            reuse_score=float(candidate.get("reusability", candidate.get("metadata", {}).get("reuse_score", 0.5))),
            pinned=bool(candidate.get("pinned", False)),
            ttl_seconds=candidate.get("ttl_seconds"),
            metadata=metadata,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

    def _base_metadata(self, candidate: dict, user_id: str, session_id: str, task_id: str) -> Dict[str, object]:
        return {
            "user_id": user_id,
            "session_id": session_id,
            "task_id": task_id,
            "source": candidate.get("source", "unknown"),
            "is_rag_data": candidate.get("is_rag_data", False),
            "rag_namespace": candidate.get("rag_namespace"),
            **candidate.get("metadata", {}),
        }

    def _build_key_record(self, candidate, user_id, session_id, task_id, scope):
        content = candidate["content"]
        summary = candidate.get("summary") or simple_keyword_summary(content, 220)
        metadata = self._base_metadata(candidate, user_id, session_id, task_id)
        metadata["inject_policy"] = "always"
        metadata["task_scope_terms"] = metadata.get("task_scope_terms") or self._salient_terms(content, limit=8)
        metadata["policy_scope"] = metadata.get("policy_scope") or ["all"]
        tags = self._merge_unique(candidate.get("tags"), ["key_memory"], metadata.get("task_scope_terms", [])[:4])
        return self._base_record(
            candidate,
            user_id,
            session_id,
            task_id,
            MemoryType.KEY,
            scope,
            content,
            summary,
            tags,
            list(candidate.get("graph_refs", [])),
            list(candidate.get("source_refs", [])),
            metadata,
        )

    def _build_semantic_record(self, candidate, user_id, session_id, task_id, scope):
        content = candidate["content"]
        summary = candidate.get("summary") or simple_keyword_summary(content, 240)
        metadata = self._base_metadata(candidate, user_id, session_id, task_id)
        entity_links = metadata.get("entity_links") or self._salient_terms(content, summary, limit=10)
        metadata["entity_links"] = entity_links
        metadata["knowledge_kind"] = metadata.get("knowledge_kind") or "fact_or_rule"
        graph_refs = self._merge_unique(candidate.get("graph_refs"), [f"entity::{term}" for term in entity_links[:8]])
        source_refs = self._merge_unique(candidate.get("source_refs"))
        tags = self._merge_unique(candidate.get("tags"), entity_links[:6], ["semantic_memory"])
        return self._base_record(
            candidate,
            user_id,
            session_id,
            task_id,
            MemoryType.SEMANTIC,
            scope,
            content,
            summary,
            tags,
            graph_refs,
            source_refs,
            metadata,
        )

    def _build_episodic_record(self, candidate, user_id, session_id, task_id, scope):
        content = candidate["content"]
        summary = candidate.get("summary") or simple_keyword_summary(content, 220)
        metadata = self._base_metadata(candidate, user_id, session_id, task_id)
        metadata["timeline"] = {
            **dict(metadata.get("timeline", {})),
            "session_id": session_id,
            "task_id": task_id,
            "stored_at": utc_now().isoformat(),
        }
        tags = self._merge_unique(candidate.get("tags"), ["episodic_summary", metadata["timeline"].get("outcome", "")])
        return self._base_record(
            candidate,
            user_id,
            session_id,
            task_id,
            MemoryType.EPISODIC,
            scope,
            content,
            summary,
            tags,
            list(candidate.get("graph_refs", [])),
            self._merge_unique(candidate.get("source_refs")),
            metadata,
        )

    def _build_perceptual_record(self, candidate, user_id, session_id, task_id, scope):
        content = candidate["content"]
        summary = candidate.get("summary") or simple_keyword_summary(content, 220)
        metadata = self._base_metadata(candidate, user_id, session_id, task_id)
        objects = metadata.get("objects") or self._salient_terms(content, limit=4)
        regions = metadata.get("regions") or [
            marker for marker in ["left", "right", "top", "bottom", "center", "左侧", "右侧", "上方", "下方", "中间"]
            if marker in content.lower() or marker in content
        ]
        metadata["objects"] = objects
        metadata["regions"] = regions
        metadata["visual_clues"] = metadata.get("visual_clues") or self._salient_terms(content, summary, limit=8)[4:8]
        tags = self._merge_unique(candidate.get("tags"), objects[:4], regions[:4], ["perceptual_memory"])
        return self._base_record(
            candidate,
            user_id,
            session_id,
            task_id,
            MemoryType.PERCEPTUAL,
            scope,
            content,
            summary,
            tags,
            list(candidate.get("graph_refs", [])),
            self._merge_unique(candidate.get("source_refs")),
            metadata,
        )

    def _build_experience_record(self, candidate, user_id, session_id, task_id, scope):
        metadata = self._base_metadata(candidate, user_id, session_id, task_id)
        problem_pattern = metadata.get("problem_pattern") or simple_keyword_summary(candidate["content"], 120)
        context_signature = metadata.get("context_signature") or simple_keyword_summary(" ".join(metadata.get("supporting_summaries", [])), 140)
        action_path = metadata.get("action_path") or ["direct_reasoning"]
        outcome = metadata.get("outcome") or metadata.get("timeline", {}).get("outcome", "unknown")
        lesson_learned = metadata.get("lesson_learned") or simple_keyword_summary(candidate["content"], 160)
        reuse_score = float(metadata.get("reuse_score", candidate.get("reusability", 0.5)))
        metadata.update(
            {
                "problem_pattern": problem_pattern,
                "context_signature": context_signature,
                "action_path": list(action_path),
                "outcome": outcome,
                "lesson_learned": lesson_learned,
                "reuse_score": reuse_score,
            }
        )
        content = (
            f"problem_pattern={problem_pattern}\n"
            f"context_signature={context_signature}\n"
            f"action_path={' -> '.join(action_path)}\n"
            f"outcome={outcome}\n"
            f"lesson_learned={lesson_learned}"
        )
        summary = simple_keyword_summary(content, 240)
        tags = self._merge_unique(candidate.get("tags"), ["experience_memory", outcome], self._salient_terms(problem_pattern, lesson_learned, limit=6))
        return self._base_record(
            candidate,
            user_id,
            session_id,
            task_id,
            MemoryType.EXPERIENCE,
            scope,
            content,
            summary,
            tags,
            list(candidate.get("graph_refs", [])),
            self._merge_unique(candidate.get("source_refs")),
            metadata,
        )

    def to_record(
        self,
        candidate: dict,
        user_id: str,
        session_id: str,
        task_id: str,
        memory_type: MemoryType,
        scope: MemoryScope,
    ) -> MemoryRecord:
        if memory_type == MemoryType.KEY:
            return self._build_key_record(candidate, user_id, session_id, task_id, scope)
        if memory_type == MemoryType.SEMANTIC:
            return self._build_semantic_record(candidate, user_id, session_id, task_id, scope)
        if memory_type == MemoryType.EPISODIC:
            return self._build_episodic_record(candidate, user_id, session_id, task_id, scope)
        if memory_type == MemoryType.PERCEPTUAL:
            return self._build_perceptual_record(candidate, user_id, session_id, task_id, scope)
        if memory_type == MemoryType.EXPERIENCE:
            return self._build_experience_record(candidate, user_id, session_id, task_id, scope)
        return self._build_semantic_record(candidate, user_id, session_id, task_id, scope)


class AsyncWriteBackQueue:
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        self._queue: queue.Queue = queue.Queue()
        self._running = True
        self._worker = threading.Thread(target=self._loop, daemon=True, name="AsyncWriteBackQueue")
        self._worker.start()

    def submit(self, record: MemoryRecord) -> None:
        self._queue.put(record)

    def drain(self) -> None:
        self._queue.join()

    def _loop(self) -> None:
        while self._running:
            record = self._queue.get()
            if record is None:
                break
            self.memory_manager.write_record(record)
            self._queue.task_done()

    def close(self) -> None:
        self._running = False
        self._queue.put(None)
        self._worker.join(timeout=2.0)


class OfflineIngestionPipeline:
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        self.document_ingestor = DocumentIngestionService()

    def ingest_text_document(
        self,
        source_id: str,
        text: str,
        rag_namespace: Optional[str] = None,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        ) -> List[MemoryRecord]:
        payloads = self.document_ingestor.make_document_payloads(source_id=source_id, text=text)
        records: List[MemoryRecord] = []
        for payload in payloads:
            record = MemoryRecord(
                memory_id=payload["chunk_id"],
                memory_type=memory_type,
                scope=MemoryScope.GLOBAL,
                content=payload["content"],
                summary=payload["summary"],
                metadata={
                    "source_id": source_id,
                    "source_type": payload["source_type"],
                    "is_rag_data": True,
                    "rag_namespace": rag_namespace,
                    "data_source": "rag_pipeline",
                },
            )
            self.memory_manager.write_record(record)
            records.append(record)
        return records

    def ingest_payload(
        self,
        source_id: str,
        payload: str,
        source_type: str = "document",
        rag_namespace: Optional[str] = None,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        scope: MemoryScope = MemoryScope.GLOBAL,
        tags: Optional[List[str]] = None,
    ) -> List[MemoryRecord]:
        payloads = self.document_ingestor.make_document_payloads(source_id=source_id, text=payload, source_type=source_type)
        records: List[MemoryRecord] = []
        for item in payloads:
            record = MemoryRecord(
                memory_id=item["chunk_id"],
                memory_type=memory_type,
                scope=scope,
                content=item["content"],
                summary=item["summary"],
                tags=list(tags or []) + [source_type],
                metadata={
                    "source_id": source_id,
                    "source_type": source_type,
                    "is_rag_data": True,
                    "rag_namespace": rag_namespace,
                    "data_source": "offline_ingestion",
                },
            )
            self.memory_manager.write_record(record)
            records.append(record)
        return records
