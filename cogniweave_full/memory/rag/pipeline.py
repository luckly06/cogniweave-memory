from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..base import BaseRAGPipeline
from ..enums import MemoryType
from ..models import CandidateSet, MemoryRecord, RetrievalConfig, ScoredCandidate, TaskContext
from ..utils import normalize_text, tokenize
from .query_expansion import ExpansionConfig, QueryExpansionService


class MemoryRAGPipeline(BaseRAGPipeline):
    def __init__(
        self,
        key_memory,
        retrievers,
        scorers,
        fusion_policy,
        normalizer,
        query_expander: QueryExpansionService,
        forget_manager=None,
    ):
        self.key_memory = key_memory
        self.retrievers = retrievers
        self.scorers = scorers
        self.fusion_policy = fusion_policy
        self.normalizer = normalizer
        self.query_expander = query_expander
        self.forget_manager = forget_manager

    def _annotate_candidates(self, aggregated: Dict[MemoryType, Dict[str, ScoredCandidate]]) -> None:
        signature_counts: Dict[str, int] = {}
        channel_groups: Dict[tuple[MemoryType, str], List[ScoredCandidate]] = {}

        for channel, items in aggregated.items():
            for item in items.values():
                signature = normalize_text(item.record.summary or item.record.content)
                if not signature:
                    continue
                signature_counts[signature] = signature_counts.get(signature, 0) + 1
                coarse = " ".join(sorted(set(tokenize(signature)))[:12])
                channel_groups.setdefault((channel, coarse), []).append(item)

        for items in aggregated.values():
            for item in items.values():
                signature = normalize_text(item.record.summary or item.record.content)
                duplicate_count = signature_counts.get(signature, 1)
                item.record.metadata["duplicate_ratio"] = max(0.0, (duplicate_count - 1) / duplicate_count)

        for grouped_items in channel_groups.values():
            if len(grouped_items) <= 1:
                continue
            conflict_ratio = len(grouped_items[1:]) / len(grouped_items)
            for item in grouped_items:
                item.record.metadata["conflict_flag"] = True
                item.record.metadata["conflict_ratio"] = conflict_ratio
                item.record.metadata["conflict_candidates"] = [
                    other.record.memory_id for other in grouped_items if other.record.memory_id != item.record.memory_id
                ]

    def compute_dynamic_k(self, task_context: TaskContext, default_k_retrieve: int = 12, default_k_context: int = 6) -> RetrievalConfig:
        retrieval_expand = float(task_context.metadata.get("retrieval_expand_factor", 1.0) or 1.0)
        context_expand = float(task_context.metadata.get("context_expand_factor", 1.0) or 1.0)
        k_retrieve = max(
            6,
            min(
                30,
                int(
                    (
                        default_k_retrieve
                        + task_context.task_complexity * 10
                        + task_context.ambiguity * 6
                        - task_context.retrieval_cost * 3
                    )
                    * retrieval_expand
                ),
            ),
        )
        k_context = max(
            4,
            min(
                max(4, task_context.context_slots),
                int(
                    (
                        default_k_context
                        + task_context.task_complexity * 3
                        + (task_context.token_budget / 4000.0)
                    )
                    * context_expand
                ),
            ),
        )
        return RetrievalConfig(k_retrieve=k_retrieve, k_context=k_context)

    def _build_filters(
        self,
        rag_namespace: Optional[str],
        only_rag_data: bool,
    ) -> Dict[str, object]:
        filters: Dict[str, object] = {}
        if rag_namespace:
            filters["rag_namespace"] = rag_namespace
        if only_rag_data:
            filters["only_rag_data"] = True
        return filters

    def run(
        self,
        user_id: str,
        session_id: str,
        query: str,
        task_context: TaskContext,
        config: Optional[RetrievalConfig] = None,
        rag_namespace: Optional[str] = None,
        only_rag_data: bool = False,
        enable_mqe: bool = False,
        mqe_expansions: int = 2,
        enable_hyde: bool = False,
        candidate_pool_multiplier: int = 4,
    ) -> Tuple[List[MemoryRecord], List[ScoredCandidate]]:
        config = config or self.compute_dynamic_k(task_context)
        key_items = self.key_memory.fetch_for_injection(
            user_id=user_id,
            session_id=session_id,
            task_type=task_context.task_type.value,
            task_scope=query,
            policy_scope=task_context.task_type.value,
        )

        expansions = self.query_expander.build_expansions(
            query=query,
            task_context=task_context,
            config=ExpansionConfig(
                enable_mqe=enable_mqe,
                mqe_expansions=mqe_expansions,
                enable_hyde=enable_hyde,
            ),
        )

        pool = max(config.k_context * candidate_pool_multiplier, 20)
        per = max(1, pool // max(1, len(expansions)))
        filters = self._build_filters(rag_namespace=rag_namespace, only_rag_data=only_rag_data)

        aggregated: Dict[MemoryType, Dict[str, ScoredCandidate]] = {
            MemoryType.SEMANTIC: {},
            MemoryType.EPISODIC: {},
            MemoryType.PERCEPTUAL: {},
            MemoryType.EXPERIENCE: {},
        }

        for expansion in expansions:
            candidate_sets: Dict[MemoryType, CandidateSet] = {}
            for channel in task_context.candidate_channels:
                if channel == MemoryType.KEY:
                    continue
                retriever = self.retrievers.get(channel)
                if not retriever:
                    continue
                candidate_sets[channel] = retriever.retrieve(
                    query=expansion,
                    task_context=task_context,
                    top_k=per,
                    filters=filters,
                )

            if self.forget_manager:
                for candidate_set in candidate_sets.values():
                    for record in candidate_set.items:
                        self.forget_manager.touch(record.memory_id, used_in_context=False)

            for channel, candidate_set in candidate_sets.items():
                scored = self.scorers[channel].score(
                    query=expansion,
                    candidates=candidate_set,
                    task_context=task_context,
                )
                for item in scored:
                    existing = aggregated[channel].get(item.record.memory_id)
                    if existing is None or item.raw_score > existing.raw_score:
                        item.record.metadata.setdefault("matched_expansions", [])
                        item.record.metadata["matched_expansions"].append(expansion)
                        aggregated[channel][item.record.memory_id] = item

        normalized = self.normalizer.normalize(
            {
                channel: list(items.values())
                for channel, items in aggregated.items()
                if items
            }
        )
        self._annotate_candidates(aggregated)
        selected = self.fusion_policy.fuse(
            normalized=normalized,
            key_items=key_items,
            task_context=task_context,
            k_context=config.k_context,
        )
        return key_items, selected
