from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence

WORD_RE = re.compile(r"[\w一-鿿]+", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[。！？.!?])\s+")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_text(text: str) -> str:
    text = text or ""
    return re.sub(r"\s+", " ", text.strip().lower())


def tokenize(text: str) -> List[str]:
    return WORD_RE.findall(normalize_text(text))


def deterministic_embedding(text: str, dims: int = 64) -> List[float]:
    vec = [0.0] * dims
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(dims):
            vec[i] += digest[i % len(digest)] / 255.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n))) or 1.0
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n))) or 1.0
    return dot / (na * nb)


def jaccard_similarity(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def recency_score(ts: datetime | None, half_life_days: int = 30) -> float:
    if not ts:
        return 0.5
    delta_days = max((utc_now() - ts).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (delta_days / max(half_life_days, 1))


def estimate_complexity(text: str) -> float:
    tokens = tokenize(text)
    if not tokens:
        return 0.1
    uniq_ratio = len(set(tokens)) / max(len(tokens), 1)
    markers = {"plan", "design", "debug", "compare", "image", "tool", "research", "代码", "设计", "规划", "调试"}
    signal = sum(1 for t in tokens if t in markers)
    return min(1.0, 0.2 + len(tokens) / 120.0 + uniq_ratio * 0.3 + signal * 0.05)


def estimate_ambiguity(text: str) -> float:
    text_norm = normalize_text(text)
    markers = ["maybe", "something", "某个", "差不多", "大概", "那个", "它", "这玩意"]
    score = sum(1 for m in markers if m in text_norm) / max(len(markers), 1)
    pronouns = len(re.findall(r"\b(it|this|that|they|he|she)\b", text_norm))
    return min(1.0, score + pronouns * 0.05)


def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = [p.strip() for p in SENTENCE_RE.split(text) if p.strip()]
    return parts or [text.strip()]


def truncate(text: str, limit: int = 320) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def simple_keyword_summary(text: str, limit: int = 320) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(text) <= limit:
        return text
    counts = Counter(tokenize(text))
    scored = []
    for sent in sentences:
        score = sum(counts[t] for t in tokenize(sent))
        scored.append((score, sent))
    scored.sort(key=lambda x: x[0], reverse=True)
    summary = ""
    for _, sent in scored:
        candidate = (summary + " " + sent).strip()
        if len(candidate) > limit:
            break
        summary = candidate
    return truncate(summary or sentences[0], limit=limit)


def robust_zscore(values: List[float]) -> List[float]:
    if not values:
        return []
    vals = sorted(values)
    median = vals[len(vals) // 2]
    q1 = vals[len(vals) // 4]
    q3 = vals[(len(vals) * 3) // 4]
    iqr = (q3 - q1) or 1.0
    return [(v - median) / iqr for v in values]


def safe_json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def parse_json_object(text: str) -> Dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None

    candidate = text[start : end + 1]
    try:
        value = json.loads(candidate)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def stable_uuid(*parts: Any) -> str:
    seed = "::".join(str(part) for part in parts)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
