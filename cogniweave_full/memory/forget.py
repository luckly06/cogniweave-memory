from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import exp
from typing import Dict, List, Optional

from .models import MemoryRecord
from .utils import utc_now


class ForgetAction(str, Enum):
    KEEP = "keep"
    DEMOTE = "demote"
    SUMMARIZE_THEN_DELETE = "summarize_then_delete"
    ARCHIVE = "archive"
    DELETE = "delete"


@dataclass
class ForgetDecision:
    memory_id: str
    channel: str
    action: ForgetAction
    reason: str
    retention_score: float
    eviction_priority: float
    replacement_summary: Optional[str] = None
    demote_to_channel: Optional[str] = None


@dataclass
class RetentionProfile:
    channel: str
    max_items: int
    recency_half_life_days: int
    min_retention_score: float
    archive_threshold: float
    summarize_threshold: float
    delete_threshold: float
    allow_auto_delete: bool = True
    allow_archive: bool = True
    allow_summarize: bool = True


DEFAULT_RETENTION_PROFILES: Dict[str, RetentionProfile] = {
    "key": RetentionProfile("key", 5000, 3650, 0.20, 0.10, 0.05, 0.01, allow_auto_delete=False, allow_archive=False, allow_summarize=False),
    "semantic": RetentionProfile("semantic", 200000, 180, 0.25, 0.20, 0.15, 0.08),
    "episodic": RetentionProfile("episodic", 150000, 60, 0.22, 0.18, 0.14, 0.07),
    "perceptual": RetentionProfile("perceptual", 250000, 14, 0.18, 0.12, 0.10, 0.05),
    "experience": RetentionProfile("experience", 100000, 120, 0.28, 0.22, 0.18, 0.09),
}


class ForgetPolicy:
    def __init__(self, profiles: Dict[str, RetentionProfile]):
        self.profiles = profiles

    @staticmethod
    def _channel_name(record: MemoryRecord) -> str:
        value = getattr(record.memory_type, "value", record.memory_type)
        return str(value)

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, value))

    def _profile_for(self, record: MemoryRecord) -> RetentionProfile:
        return self.profiles[self._channel_name(record)]

    def _age_days(self, record: MemoryRecord, now: datetime) -> float:
        anchor = record.last_access_at or record.updated_at or record.created_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return max(0.0, (now - anchor).total_seconds() / 86400.0)

    def _reuse_signal(self, record: MemoryRecord) -> float:
        usage = 0.2 * record.access_count + 0.6 * record.hit_count + 1.0 * record.use_count
        usage_norm = min(1.0, usage / 10.0)
        modeled_reuse = self._clamp(record.reuse_score)
        return self._clamp(0.6 * usage_norm + 0.4 * modeled_reuse)

    def _recency_signal(self, record: MemoryRecord, now: datetime) -> float:
        profile = self._profile_for(record)
        age_days = self._age_days(record, now)
        half_life = max(1, profile.recency_half_life_days)
        decay_rate = max(0.1, record.decay_rate)
        return self._clamp(exp(-(age_days / half_life) * decay_rate))

    def _consistency_signal(self, record: MemoryRecord) -> float:
        consistency = self._clamp(record.consistency)
        conflict_ratio = float(record.metadata.get("conflict_ratio", 0.0) or 0.0)
        return self._clamp(consistency * (1.0 - conflict_ratio))

    def _ttl_expired(self, record: MemoryRecord, now: datetime) -> bool:
        if record.ttl_seconds is None:
            return False
        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now >= created_at + timedelta(seconds=int(record.ttl_seconds))

    def retention_score(self, record: MemoryRecord, now: datetime) -> float:
        if record.pinned:
            return 1.0
        if self._ttl_expired(record, now):
            return 0.0

        score = (
            0.25 * self._clamp(record.importance)
            + 0.15 * self._clamp(record.confidence)
            + 0.15 * self._clamp(record.novelty)
            + 0.20 * self._reuse_signal(record)
            + 0.15 * self._recency_signal(record, now)
            + 0.10 * self._consistency_signal(record)
        )
        return self._clamp(score)

    def eviction_priority(self, record: MemoryRecord, current_size: int, max_size: int, now: datetime) -> float:
        retention = self.retention_score(record, now)
        pressure = max(0.0, float(current_size) / float(max(1, max_size)))
        duplicate_penalty = float(record.metadata.get("duplicate_ratio", 0.0) or 0.0)
        priority = (1.0 - retention) * max(1.0, pressure) + duplicate_penalty * 0.25
        if self._ttl_expired(record, now):
            priority += 1.0
        return self._clamp(priority, 0.0, 10.0)

    def _default_summary(self, record: MemoryRecord) -> str:
        base = (record.summary or record.content or "").strip()
        return base if len(base) <= 220 else base[:217] + "..."

    def decide(self, record: MemoryRecord, current_size: int, now: datetime) -> ForgetDecision:
        channel = self._channel_name(record)
        profile = self.profiles[channel]
        retention = self.retention_score(record, now)
        eviction = self.eviction_priority(record, current_size, profile.max_items, now)

        if record.archived:
            return ForgetDecision(record.memory_id, channel, ForgetAction.KEEP, "record already archived", retention, eviction)

        if record.pinned:
            return ForgetDecision(record.memory_id, channel, ForgetAction.KEEP, "record is pinned", retention, eviction)

        if channel == "key":
            if float(record.metadata.get("demote_candidate", 0.0) or 0.0) > 0.5:
                return ForgetDecision(
                    record.memory_id,
                    channel,
                    ForgetAction.DEMOTE,
                    "key memory marked as demote candidate",
                    retention,
                    eviction,
                    demote_to_channel="semantic",
                )
            return ForgetDecision(record.memory_id, channel, ForgetAction.KEEP, "key memory is not auto-deleted", retention, eviction)

        over_capacity = current_size > profile.max_items
        ttl_expired = self._ttl_expired(record, now)
        duplicate_ratio = float(record.metadata.get("duplicate_ratio", 0.0) or 0.0)

        if ttl_expired and profile.allow_auto_delete:
            return ForgetDecision(record.memory_id, channel, ForgetAction.DELETE, "ttl expired", retention, eviction)

        if retention <= profile.delete_threshold and profile.allow_auto_delete:
            return ForgetDecision(record.memory_id, channel, ForgetAction.DELETE, "retention score below delete threshold", retention, eviction)

        if ((retention <= profile.summarize_threshold or duplicate_ratio >= 0.85 or over_capacity) and profile.allow_summarize):
            return ForgetDecision(
                record.memory_id,
                channel,
                ForgetAction.SUMMARIZE_THEN_DELETE,
                "low retention or duplicate fragment suitable for summary compaction",
                retention,
                eviction,
                replacement_summary=self._default_summary(record),
            )

        if retention <= profile.archive_threshold and profile.allow_archive:
            return ForgetDecision(record.memory_id, channel, ForgetAction.ARCHIVE, "retention score below archive threshold", retention, eviction)

        if over_capacity and retention < profile.min_retention_score and profile.allow_auto_delete:
            return ForgetDecision(record.memory_id, channel, ForgetAction.DELETE, "channel over capacity and retention below minimum", retention, eviction)

        return ForgetDecision(record.memory_id, channel, ForgetAction.KEEP, "record retained", retention, eviction)


class ForgetManager:
    def __init__(self, store, policy: ForgetPolicy):
        self.store = store
        self.policy = policy

    def touch(self, memory_id: str, used_in_context: bool = False) -> None:
        channel, record = self.store.get_record_with_channel(memory_id)
        if not channel or not record:
            return
        now = utc_now()
        record.last_access_at = now
        record.access_count += 1
        if used_in_context:
            record.use_count += 1
        else:
            record.hit_count += 1
        record.updated_at = now
        self.store.update_record(record)

    def explicit_forget(self, memory_id: str) -> bool:
        channel, record = self.store.get_record_with_channel(memory_id)
        if not channel or not record:
            return False
        self.store.delete_memory(channel, memory_id)
        return True

    def _apply_decision(self, record: MemoryRecord, decision: ForgetDecision) -> None:
        if decision.action == ForgetAction.KEEP:
            return
        if decision.action == ForgetAction.DELETE:
            self.store.delete_memory(decision.channel, decision.memory_id)
            return
        if decision.action == ForgetAction.ARCHIVE:
            self.store.archive_memory(decision.channel, decision.memory_id)
            return
        if decision.action == ForgetAction.DEMOTE:
            self.store.demote_memory(decision.memory_id, decision.channel, decision.demote_to_channel or "semantic")
            return
        if decision.action == ForgetAction.SUMMARIZE_THEN_DELETE:
            summary = decision.replacement_summary or record.summary or record.content[:220]
            self.store.create_summary_replacement(
                source_record=record,
                summary=summary,
                target_channel="semantic" if decision.channel in {"episodic", "perceptual"} else decision.channel,
            )
            self.store.delete_memory(decision.channel, decision.memory_id)

    def run_channel_cycle(self, channel: str, dry_run: bool = False):
        store = self.store.get_store_by_channel(channel)
        records = store.list_records(include_archived=False)
        current_size = len(records)
        now = utc_now()

        decisions = [self.policy.decide(record=record, current_size=current_size, now=now) for record in records]
        decisions.sort(key=lambda item: item.eviction_priority, reverse=True)

        if not dry_run:
            record_map = {record.memory_id: record for record in records}
            for decision in decisions:
                record = record_map.get(decision.memory_id)
                if record is not None:
                    self._apply_decision(record, decision)

        return decisions

    def run_full_cycle(self, dry_run: bool = False):
        result = {}
        for channel in self.policy.profiles.keys():
            result[channel] = self.run_channel_cycle(channel=channel, dry_run=dry_run)
        return result
