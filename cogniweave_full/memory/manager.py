from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import Config
from ..core.llm import BaseLLM
from .consolidation import AsyncWriteBackQueue, CandidateExtractor, Consolidator, OfflineIngestionPipeline
from .context import ContextOrchestrator
from .enums import MemoryType, ModalityType
from .feedback import FeedbackCollector, FeedbackEvent, PolicyUpdater
from .forget import DEFAULT_RETENTION_PROFILES, ForgetManager, ForgetPolicy
from .forget_scheduler import ForgetScheduler
from .models import ExecutionResult, ExecutionTrace, MemoryRecord, RawInput
from .rag.fusion import FusionPolicy
from .rag.normalizer import Normalizer
from .rag.pipeline import MemoryRAGPipeline
from .rag.query_expansion import QueryExpansionService
from .rag.retrievers import EpisodicRetriever, ExperienceRetriever, PerceptualRetriever, SemanticRetriever
from .rag.scorers import EpisodicScorer, ExperienceScorer, PerceptualScorer, SemanticScorer
from .router import PostRunMemoryRouter, TaskModalityRouter
from .storage.hybrid_store import EpisodicHybridStore, ExperienceHybridStore, PerceptualHybridStore, SemanticHybridStore
from .storage.key_value_store import KeyMemoryStore
from .storage.neo4j_store import Neo4jGraphStore
from .storage.qdrant_store import QdrantVectorStore
from .storage.sqlite_store import SQLiteMemoryStore
from .types import EpisodicMemory, ExperienceMemory, KeyMemory, PerceptualMemory, SemanticMemory
from .utils import parse_json_object, safe_json_dumps, simple_keyword_summary, stable_uuid, tokenize, utc_now
from .working_memory import SensoryBuffer, WorkingMemoryBuffer


class MemoryManager:
    def __init__(self, llm: BaseLLM, tool_registry, base_dir: str = "./runtime", config: Optional[Config] = None):
        self.llm = llm
        self.tool_registry = tool_registry
        self.config = config or Config.from_env()
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.working_memory = WorkingMemoryBuffer(max_turns=self.config.working_memory_turns)
        self.sensory_buffer = SensoryBuffer()

        self.forget_policy = ForgetPolicy(DEFAULT_RETENTION_PROFILES)
        self.forget_manager = ForgetManager(store=self, policy=self.forget_policy)
        self.forget_scheduler = ForgetScheduler(self.forget_manager, interval_seconds=self.config.forget_interval_seconds)

        qdrant_prefix = self.config.qdrant_collection_prefix
        qdrant_local_dir = self.base_dir / "qdrant_local"

        self.key_store = KeyMemoryStore(self.base_dir / "key_memory.json")
        self.semantic_store = SemanticHybridStore(
            metadata_store=SQLiteMemoryStore(self.base_dir / "semantic.sqlite", MemoryType.SEMANTIC),
            vector_store=QdrantVectorStore(
                f"{qdrant_prefix}_semantic",
                local_path=None if self.config.enable_qdrant else str(qdrant_local_dir / "semantic"),
                url=self.config.qdrant_url if self.config.enable_qdrant else None,
                api_key=self.config.qdrant_api_key if self.config.enable_qdrant else None,
            ),
            graph_store=Neo4jGraphStore(
                uri=self.config.neo4j_uri,
                user=self.config.neo4j_user,
                password=self.config.neo4j_password,
                enabled=self.config.enable_neo4j,
            ),
        )
        self.episodic_store = EpisodicHybridStore(
            metadata_store=SQLiteMemoryStore(self.base_dir / "episodic.sqlite", MemoryType.EPISODIC),
            vector_store=QdrantVectorStore(
                f"{qdrant_prefix}_episodic",
                local_path=None if self.config.enable_qdrant else str(qdrant_local_dir / "episodic"),
                url=self.config.qdrant_url if self.config.enable_qdrant else None,
                api_key=self.config.qdrant_api_key if self.config.enable_qdrant else None,
            ),
        )
        self.perceptual_store = PerceptualHybridStore(
            metadata_store=SQLiteMemoryStore(self.base_dir / "perceptual.sqlite", MemoryType.PERCEPTUAL),
            vector_store=QdrantVectorStore(
                f"{qdrant_prefix}_perceptual",
                local_path=None if self.config.enable_qdrant else str(qdrant_local_dir / "perceptual"),
                url=self.config.qdrant_url if self.config.enable_qdrant else None,
                api_key=self.config.qdrant_api_key if self.config.enable_qdrant else None,
            ),
        )
        self.experience_store = ExperienceHybridStore(
            metadata_store=SQLiteMemoryStore(self.base_dir / "experience.sqlite", MemoryType.EXPERIENCE),
            vector_store=QdrantVectorStore(
                f"{qdrant_prefix}_experience",
                local_path=None if self.config.enable_qdrant else str(qdrant_local_dir / "experience"),
                url=self.config.qdrant_url if self.config.enable_qdrant else None,
                api_key=self.config.qdrant_api_key if self.config.enable_qdrant else None,
            ),
        )

        self.key_memory = KeyMemory(self.key_store)
        self.semantic_memory = SemanticMemory(self.semantic_store)
        self.episodic_memory = EpisodicMemory(self.episodic_store)
        self.perceptual_memory = PerceptualMemory(self.perceptual_store)
        self.experience_memory = ExperienceMemory(self.experience_store)

        self.fusion_policy = FusionPolicy()
        self.normalizer = Normalizer()
        self.query_expander = QueryExpansionService(self.llm)
        self.retrieval = MemoryRAGPipeline(
            key_memory=self.key_memory,
            retrievers={
                MemoryType.SEMANTIC: SemanticRetriever(self.semantic_store),
                MemoryType.EPISODIC: EpisodicRetriever(self.episodic_store),
                MemoryType.PERCEPTUAL: PerceptualRetriever(self.perceptual_store),
                MemoryType.EXPERIENCE: ExperienceRetriever(self.experience_store),
            },
            scorers={
                MemoryType.SEMANTIC: SemanticScorer(),
                MemoryType.EPISODIC: EpisodicScorer(),
                MemoryType.PERCEPTUAL: PerceptualScorer(),
                MemoryType.EXPERIENCE: ExperienceScorer(),
            },
            fusion_policy=self.fusion_policy,
            normalizer=self.normalizer,
            query_expander=self.query_expander,
            forget_manager=self.forget_manager,
        )

        self.task_router = TaskModalityRouter()
        self.post_run_router = PostRunMemoryRouter()
        self.context_orchestrator = ContextOrchestrator(forget_manager=self.forget_manager)
        self.candidate_extractor = CandidateExtractor()
        self.consolidator = Consolidator()
        self.writeback = AsyncWriteBackQueue(self)
        self.offline_ingestion = OfflineIngestionPipeline(self)
        self.feedback_collector = FeedbackCollector()
        self.policy_updater = PolicyUpdater()

    def _tool_raw_input(self, user_id: str, session_id: str, query: str) -> RawInput:
        return RawInput(
            user_id=user_id,
            session_id=session_id,
            turn_id=f"tool::{session_id}::{utc_now().timestamp()}",
            modality=ModalityType.TEXT,
            content=query,
            timestamp=utc_now(),
        )

    def _tool_schemas(self) -> List[Dict[str, Any]]:
        if not self.tool_registry:
            return []
        return list(self.tool_registry.list_schemas())

    def _normalize_tool_calls(self, payload: Dict[str, Any] | None) -> List[Dict[str, Any]]:
        if not payload:
            return []
        tool_calls = payload.get("tool_calls") or []
        if isinstance(tool_calls, dict):
            tool_calls = [tool_calls]

        normalized: List[Dict[str, Any]] = []
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            name = str(call.get("name", "")).strip()
            arguments = call.get("arguments", {})
            if isinstance(arguments, str):
                parsed = parse_json_object(arguments)
                arguments = parsed if parsed is not None else {"input": arguments}
            if not isinstance(arguments, dict):
                arguments = {}
            if name:
                normalized.append({"name": name, "arguments": arguments})
        return normalized

    def _sensory_context_items(self, raw_input: RawInput) -> List[dict]:
        if raw_input.modality not in {ModalityType.IMAGE, ModalityType.MULTIMODAL}:
            return []
        items = self.sensory_buffer.get_all(raw_input.session_id)
        out = []
        for idx, item in enumerate(items):
            payload = dict(item)
            payload.setdefault("candidate_id", stable_uuid(raw_input.session_id, raw_input.turn_id, "sensory", idx))
            payload.setdefault(
                "summary",
                simple_keyword_summary(
                    f"{payload.get('modality', raw_input.modality.value)} input: {payload.get('input', '')}",
                    180,
                ),
            )
            payload.setdefault("importance", 0.52)
            payload.setdefault("confidence", 0.45)
            out.append(payload)
        return out

    def _augment_task_context(self, task_context, session_id: str):
        state = self.policy_updater.state
        task_context.metadata["retrieval_expand_factor"] = state.retrieval_expand_factor
        task_context.metadata["context_expand_factor"] = state.context_expand_factor
        task_context.metadata["write_threshold"] = state.write_threshold
        task_context.metadata["key_promotion_threshold"] = state.key_promotion_threshold
        task_context.metadata["classifier_bias"] = dict(state.classifier_bias)
        task_context.metadata["tool_only_confidence_threshold"] = state.tool_only_confidence_threshold
        task_context.metadata["force_inject_threshold"] = state.force_inject_threshold
        trace_summary = self.working_memory.summarize_old_traces(session_id)
        if trace_summary:
            task_context.metadata["trace_summary"] = trace_summary
        return task_context

    def _promote_sensory_candidates(
        self,
        raw_input: RawInput,
        final_answer: str,
        sensory_items: List[dict],
    ) -> List[dict]:
        if raw_input.modality not in {ModalityType.IMAGE, ModalityType.MULTIMODAL}:
            return []
        answer_hint = final_answer or ""
        if not answer_hint:
            return []

        promoted = []
        for item in sensory_items:
            combined = f"{item.get('input', '')}\n{answer_hint}".strip()
            summary = simple_keyword_summary(combined, 180)
            tokens = [token for token in tokenize(combined) if len(token) > 1][:12]
            objects = tokens[:4]
            regions = [
                marker
                for marker in ["left", "right", "top", "bottom", "center", "左侧", "右侧", "上方", "下方", "中间"]
                if marker in combined.lower() or marker in combined
            ]
            promoted.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "input": item.get("input", ""),
                    "summary": summary,
                    "modality": item.get("modality", raw_input.modality.value),
                    "importance": max(0.6, float(item.get("importance", 0.5))),
                    "confidence": 0.72,
                    "stability": 0.68,
                    "ttl_seconds": 7 * 24 * 3600,
                    "objects": objects,
                    "regions": regions,
                    "visual_clues": tokens[4:8],
                }
            )
        return promoted

    def _append_unique(self, values: List[str], value: str) -> None:
        if value and value not in values:
            values.append(value)

    def _add_relation(self, record: MemoryRecord, related_id: str, relation_key: str = "related_memory_ids") -> None:
        related = record.metadata.setdefault(relation_key, [])
        if related_id not in related:
            related.append(related_id)

    def _apply_pending_links(self, records: List[MemoryRecord]) -> None:
        grouped: Dict[MemoryType, List[MemoryRecord]] = {}
        for record in records:
            grouped.setdefault(record.memory_type, []).append(record)

        for semantic in grouped.get(MemoryType.SEMANTIC, []):
            for key in grouped.get(MemoryType.KEY, []):
                self._add_relation(semantic, key.memory_id)
                self._add_relation(key, semantic.memory_id)
                self._append_unique(semantic.metadata.setdefault("linked_key_ids", []), key.memory_id)
                self._append_unique(key.child_memory_ids, semantic.memory_id)

        episodic_records = grouped.get(MemoryType.EPISODIC, [])
        for experience in grouped.get(MemoryType.EXPERIENCE, []):
            for episodic in episodic_records[:1]:
                experience.parent_memory_id = experience.parent_memory_id or episodic.memory_id
                self._add_relation(experience, episodic.memory_id, "related_episodic_ids")
                self._add_relation(episodic, experience.memory_id)
                self._append_unique(episodic.child_memory_ids, experience.memory_id)

        semantic_records = grouped.get(MemoryType.SEMANTIC, [])
        for perceptual in grouped.get(MemoryType.PERCEPTUAL, []):
            for semantic in semantic_records[:2]:
                perceptual.parent_memory_id = perceptual.parent_memory_id or semantic.memory_id
                self._add_relation(perceptual, semantic.memory_id, "related_semantic_ids")
                self._add_relation(semantic, perceptual.memory_id)
                self._append_unique(semantic.child_memory_ids, perceptual.memory_id)

    def _resolve_related_ids(self, values: Any) -> List[str]:
        if not values:
            return []
        if isinstance(values, str):
            values = [values]
        related_ids: List[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            memory_id = value.replace("memory://", "")
            if memory_id and memory_id not in related_ids:
                related_ids.append(memory_id)
        return related_ids

    def _apply_cross_memory_links(self, record: MemoryRecord) -> None:
        candidate_ids: List[str] = []
        for key in (
            "related_memory_ids",
            "supporting_memory_ids",
            "linked_key_ids",
            "related_semantic_ids",
            "related_episodic_ids",
            "source_memory_ids",
        ):
            candidate_ids.extend(self._resolve_related_ids(record.metadata.get(key)))
        candidate_ids.extend(self._resolve_related_ids(record.source_refs))
        candidate_ids.extend(self._resolve_related_ids(record.graph_refs))

        resolved: List[str] = []
        for related_id in candidate_ids:
            if related_id == record.memory_id or related_id in resolved:
                continue
            _, related_record = self.get_record_with_channel(related_id)
            if related_record is None:
                continue
            resolved.append(related_id)
            self._add_relation(record, related_id)
            self._append_unique(related_record.child_memory_ids, record.memory_id)
            self._add_relation(related_record, record.memory_id)
            if record.parent_memory_id is None and record.memory_type == MemoryType.EXPERIENCE and related_record.memory_type == MemoryType.EPISODIC:
                record.parent_memory_id = related_id
            if record.parent_memory_id is None and record.memory_type == MemoryType.PERCEPTUAL and related_record.memory_type == MemoryType.SEMANTIC:
                record.parent_memory_id = related_id
            self.update_record(related_record)

        if resolved and record.memory_type == MemoryType.SEMANTIC and self.semantic_store.graph_store:
            for related_id in resolved:
                self.semantic_store.graph_store.link(record.memory_id, related_id)

    def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        thought: str,
        user_id: str,
        session_id: str,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        for call in tool_calls:
            tool_name = call["name"]
            arguments = call["arguments"]
            tool = self.tool_registry.get_tool(tool_name) if self.tool_registry else None
            if tool is None:
                observation = {"error": f"tool not found: {tool_name}"}
            else:
                try:
                    observation = tool.run(
                        **arguments,
                        user_id=user_id,
                        session_id=session_id,
                    )
                except Exception as exc:
                    observation = {"error": f"{type(exc).__name__}: {exc}"}

            trace = ExecutionTrace(
                thought=thought,
                action=f"call_tool:{tool_name}",
                observation=safe_json_dumps(observation),
                tool_name=tool_name,
                tool_input=arguments,
                tool_output=observation,
            )
            self.working_memory.append_trace(session_id, trace)
            messages.append(
                {
                    "role": "tool",
                    "content": json.dumps(
                        {
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "observation": observation,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        return messages

    def _execution_summary(self, traces: List[ExecutionTrace], final_answer: str) -> Tuple[str, str, float]:
        tool_errors = [trace for trace in traces if '"error"' in (trace.observation or "")]
        if tool_errors and not final_answer:
            return "failed", "工具调用失败，未产出有效回答。", 0.0
        if tool_errors:
            return "partial_success", "存在工具错误，但系统仍给出了回答。", 0.5
        if not (final_answer or "").strip():
            return "failed", "模型未返回有效回答。", 0.0
        if traces:
            return "success", "工具链执行完成并返回结果。", 1.0
        return "success", "直接推理完成。", 0.9

    def _channel_to_store(self) -> Dict[str, object]:
        return {
            "key": self.key_store,
            "semantic": self.semantic_store,
            "episodic": self.episodic_store,
            "perceptual": self.perceptual_store,
            "experience": self.experience_store,
        }

    def get_store_by_channel(self, channel: str):
        mapping = self._channel_to_store()
        if channel not in mapping:
            raise KeyError(f"unknown memory channel: {channel}")
        return mapping[channel]

    def get_record_with_channel(self, memory_id: str) -> Tuple[Optional[str], Optional[MemoryRecord]]:
        for channel, store in self._channel_to_store().items():
            record = store.get(memory_id)
            if record is not None:
                return channel, record
        return None, None

    def update_record(self, record: MemoryRecord) -> None:
        channel = getattr(record.memory_type, "value", record.memory_type)
        self.get_store_by_channel(str(channel)).upsert(record)

    def delete_memory(self, channel: str, memory_id: str) -> None:
        self.get_store_by_channel(channel).delete(memory_id)

    def archive_memory(self, channel: str, memory_id: str) -> None:
        self.get_store_by_channel(channel).archive(memory_id)

    def demote_memory(self, memory_id: str, from_channel: str, to_channel: str) -> None:
        source_store = self.get_store_by_channel(from_channel)
        target_store = self.get_store_by_channel(to_channel)
        record = source_store.get(memory_id)
        if not record:
            return
        record.memory_type = MemoryType(to_channel)
        record.updated_at = utc_now()
        target_store.upsert(record)
        source_store.delete(memory_id)

    def create_summary_replacement(self, source_record: MemoryRecord, summary: str, target_channel: Optional[str] = None):
        target_channel = target_channel or getattr(source_record.memory_type, "value", source_record.memory_type)
        target_store = self.get_store_by_channel(str(target_channel))
        new_record = MemoryRecord(
            memory_id=stable_uuid("summary", source_record.memory_id, target_channel, summary),
            memory_type=MemoryType(str(target_channel)),
            scope=source_record.scope,
            content=summary,
            summary=summary,
            graph_refs=list(source_record.graph_refs),
            source_refs=list(source_record.source_refs),
            tags=list(source_record.tags),
            importance=max(0.3, source_record.importance * 0.6),
            confidence=source_record.confidence,
            novelty=max(0.2, source_record.novelty * 0.5),
            consistency=source_record.consistency,
            reuse_score=max(0.2, source_record.reuse_score * 0.5),
            parent_memory_id=source_record.memory_id,
            metadata={**source_record.metadata, "is_summary_replacement": True},
        )
        target_store.upsert(new_record)
        return new_record

    def write_record(self, record: MemoryRecord) -> None:
        self._apply_cross_memory_links(record)
        self.get_store_by_channel(record.memory_type.value).upsert(record)

    def start_background_services(self) -> None:
        if self.config.enable_forget:
            self.forget_scheduler.start()

    def stop_background_services(self) -> None:
        self.forget_scheduler.stop()

    def run_cycle(
        self,
        user_id: str,
        session_id: str,
        input_text: str,
        history: list[dict],
        system_prompt: str = "",
        modality: ModalityType = ModalityType.TEXT,
        few_shots: Optional[list[str]] = None,
        max_steps: int = 4,
        react_mode: bool = False,
    ) -> ExecutionResult:
        self.writeback.drain()
        raw_input = RawInput(
            user_id=user_id,
            session_id=session_id,
            turn_id=f"{session_id}::{utc_now().timestamp()}",
            modality=modality,
            content=input_text,
            timestamp=utc_now(),
        )

        self.sensory_buffer.put(session_id, {"input": input_text, "modality": modality.value}, ttl_seconds=60)
        task_context = self.task_router.route(raw_input)
        task_context = self._augment_task_context(task_context, session_id)
        sensory_items = self._sensory_context_items(raw_input)

        key_items, selected = self.retrieval.run(
            user_id=user_id,
            session_id=session_id,
            query=input_text,
            task_context=task_context,
            rag_namespace=None,
            only_rag_data=False,
            enable_mqe=self.config.enable_mqe,
            mqe_expansions=self.config.mqe_expansions,
            enable_hyde=self.config.enable_hyde,
            candidate_pool_multiplier=self.config.candidate_pool_multiplier,
        )

        active_context = self.context_orchestrator.build_context(
            system_prompt=system_prompt,
            task_goal=input_text,
            task_context=task_context,
            key_items=key_items,
            selected=selected,
            sensory_items=sensory_items,
            recent_dialogue=history[-10:],
            few_shots=few_shots or [],
            tool_schemas=self._tool_schemas(),
        )

        self.working_memory.write_active_items(
            session_id,
            active_context.key_items + active_context.retrieved_items + active_context.sensory_items,
        )
        self.working_memory.append_dialogue(session_id, "user", input_text)

        messages = active_context.to_messages()
        messages.append({"role": "user", "content": input_text})
        if react_mode or self._tool_schemas():
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Return JSON only with fields thought, tool_calls, final_answer. "
                        "tool_calls is a list of {name, arguments}. If no tool is needed, return an empty tool_calls list."
                    ),
                }
            )

        traces_before = len(self.working_memory.get_traces(session_id))
        final_answer = ""
        llm_response = ""
        for _ in range(max_steps):
            llm_response = self.llm.invoke(messages)
            payload = parse_json_object(llm_response)
            thought = payload.get("thought", "") if payload else ""
            tool_calls = self._normalize_tool_calls(payload)

            if tool_calls and self.tool_registry:
                self.working_memory.append_trace(
                    session_id,
                    ExecutionTrace(
                        thought=thought,
                        action="plan_tool_calls",
                        observation=safe_json_dumps(tool_calls),
                    ),
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "thought": thought,
                                "tool_calls": tool_calls,
                                "final_answer": "",
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
                messages.extend(
                    self._execute_tool_calls(
                        tool_calls=tool_calls,
                        thought=thought,
                        user_id=user_id,
                        session_id=session_id,
                    )
                )
                continue

            final_answer = (payload or {}).get("final_answer", "").strip() if payload else ""
            if not final_answer:
                final_answer = llm_response
            if thought:
                self.working_memory.append_trace(
                    session_id,
                    ExecutionTrace(
                        thought=thought,
                        action="finalize",
                        observation=final_answer[:400],
                    ),
                )
            break

        if not final_answer:
            final_answer = llm_response
        self.working_memory.append_dialogue(session_id, "assistant", final_answer)

        traces = self.working_memory.get_traces(session_id)[traces_before:]
        promoted_sensory = self._promote_sensory_candidates(raw_input, final_answer, sensory_items)
        outcome, feedback_text, feedback_score = self._execution_summary(traces, final_answer)

        execution_result = ExecutionResult(
            final_answer=final_answer,
            traces=traces,
            outcome=outcome,
            feedback=feedback_text,
            metadata={
                "task_type": task_context.task_type.value,
                "used_channels": [item.channel.value for item in active_context.retrieved_items],
                "tool_count": len([trace for trace in traces if trace.tool_name]),
            },
        )

        extracted = self.candidate_extractor.extract(
            input_text=input_text,
            final_answer=final_answer,
            traces=[trace.__dict__ for trace in traces],
            task_context=task_context,
            execution_result=execution_result,
            active_context=active_context,
            sensory_candidates=promoted_sensory,
            feedback=execution_result.feedback,
        )
        decisions = self.post_run_router.decide(
            raw_input=raw_input,
            task_context=task_context,
            active_context=active_context,
            execution_result=execution_result,
            extracted_candidates=extracted,
        )

        records_to_write: List[MemoryRecord] = []
        for candidate, decision in zip(extracted, decisions):
            if decision.write_policy.value in {"commit", "summary"}:
                record = self.consolidator.to_record(
                    candidate=candidate,
                    user_id=user_id,
                    session_id=session_id,
                    task_id=raw_input.turn_id,
                    memory_type=decision.memory_type,
                    scope=decision.scope,
                )
                records_to_write.append(record)

        self._apply_pending_links(records_to_write)
        for record in records_to_write:
            self.writeback.submit(record)

        self.feedback_collector.add_event(
            FeedbackEvent(
                task_type=task_context.task_type,
                used_channels=[item.channel for item in active_context.retrieved_items],
                success=outcome == "success",
                score=feedback_score,
            )
        )
        self.policy_updater.apply(
            self.feedback_collector.recent_events(),
            fusion_policy=self.fusion_policy,
            forget_policy=self.forget_policy,
        )
        self.sensory_buffer.clear(session_id)

        return execution_result
