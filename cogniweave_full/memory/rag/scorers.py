from __future__ import annotations

from typing import List

from ..base import BaseScorer
from ..enums import MemoryType
from ..models import CandidateSet, ScoredCandidate, TaskContext
from ..utils import cosine_similarity, deterministic_embedding, jaccard_similarity


class SemanticScorer(BaseScorer):
    memory_type = MemoryType.SEMANTIC

    def score(self, query: str, candidates: CandidateSet, task_context: TaskContext) -> List[ScoredCandidate]:
        qvec = deterministic_embedding(query)
        qtokens = query.split()
        results: List[ScoredCandidate] = []
        for record in candidates.items:
            sim = cosine_similarity(qvec, record.embedding or [])
            graph = jaccard_similarity(record.graph_refs + record.tags, qtokens)
            imp = max(record.importance, 0.1)
            score = (0.7 * sim + 0.3 * graph) * (0.8 + 0.4 * imp)
            results.append(
                ScoredCandidate(
                    record=record,
                    channel=self.memory_type,
                    raw_score=score,
                    score_breakdown={"sim": sim, "graph": graph, "imp": imp},
                )
            )
        results.sort(key=lambda x: x.raw_score, reverse=True)
        return results


class EpisodicScorer(BaseScorer):
    memory_type = MemoryType.EPISODIC

    def score(self, query: str, candidates: CandidateSet, task_context: TaskContext) -> List[ScoredCandidate]:
        qvec = deterministic_embedding(query)
        results: List[ScoredCandidate] = []
        for record in candidates.items:
            sim = max(cosine_similarity(qvec, record.embedding or []), 1e-6)
            rec = max(record.recency, 1e-6)
            imp = max(record.importance, 1e-6)
            score = (sim ** 0.4) * (rec ** 0.4) * (imp ** 0.2)
            results.append(
                ScoredCandidate(
                    record=record,
                    channel=self.memory_type,
                    raw_score=score,
                    score_breakdown={"sim": sim, "rec": rec, "imp": imp},
                )
            )
        results.sort(key=lambda x: x.raw_score, reverse=True)
        return results


class PerceptualScorer(BaseScorer):
    memory_type = MemoryType.PERCEPTUAL

    def score(self, query: str, candidates: CandidateSet, task_context: TaskContext) -> List[ScoredCandidate]:
        qvec = deterministic_embedding(query)
        results: List[ScoredCandidate] = []
        for record in candidates.items:
            sim = max(cosine_similarity(qvec, record.embedding or []), 1e-6)
            rec = max(record.recency, 1e-6)
            imp = max(record.importance, 1e-6)
            score = (sim ** 0.6) * (rec ** 0.2) * (imp ** 0.2)
            results.append(
                ScoredCandidate(
                    record=record,
                    channel=self.memory_type,
                    raw_score=score,
                    score_breakdown={"sim": sim, "rec": rec, "imp": imp},
                )
            )
        results.sort(key=lambda x: x.raw_score, reverse=True)
        return results


class ExperienceScorer(BaseScorer):
    memory_type = MemoryType.EXPERIENCE

    def score(self, query: str, candidates: CandidateSet, task_context: TaskContext) -> List[ScoredCandidate]:
        qvec = deterministic_embedding(query)
        results: List[ScoredCandidate] = []
        for record in candidates.items:
            task_sim = max(cosine_similarity(qvec, record.embedding or []), 1e-6)
            outcome_score = max(record.confidence, 0.1)
            reuse_score = max(record.reuse_score, 0.1)
            rec = max(record.recency, 0.1)
            score = (task_sim ** 0.5) * (outcome_score ** 0.3) * (reuse_score ** 0.2) * (rec ** 0.1)
            results.append(
                ScoredCandidate(
                    record=record,
                    channel=self.memory_type,
                    raw_score=score,
                    score_breakdown={
                        "task_sim": task_sim,
                        "outcome_score": outcome_score,
                        "reuse_score": reuse_score,
                        "rec": rec,
                    },
                )
            )
        results.sort(key=lambda x: x.raw_score, reverse=True)
        return results
