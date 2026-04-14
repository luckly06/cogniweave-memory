from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Tuple

from .models import ExecutionTrace, WorkingMemoryItem
from .utils import simple_keyword_summary


class WorkingMemoryBuffer:
    def __init__(self, max_turns: int = 8):
        self.max_turns = max_turns
        self._active_items: Dict[str, List[WorkingMemoryItem]] = defaultdict(list)
        self._recent_dialogue: Dict[str, Deque[Dict[str, str]]] = defaultdict(
            lambda: deque(maxlen=max_turns * 2)
        )
        self._traces: Dict[str, List[ExecutionTrace]] = defaultdict(list)
        self._lock = threading.RLock()

    def append_trace(self, session_id: str, trace: ExecutionTrace) -> None:
        with self._lock:
            self._traces[session_id].append(trace)
            if len(self._traces[session_id]) > self.max_turns * 8:
                self._traces[session_id] = self._traces[session_id][-self.max_turns * 8 :]

    def append_dialogue(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            self._recent_dialogue[session_id].append({"role": role, "content": content})

    def get_recent_dialogue(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        with self._lock:
            items = list(self._recent_dialogue[session_id])
        return items[-limit:]

    def write_active_items(self, session_id: str, items: List[WorkingMemoryItem]) -> None:
        with self._lock:
            self._active_items[session_id] = items

    def read_active_items(self, session_id: str) -> List[WorkingMemoryItem]:
        with self._lock:
            return list(self._active_items[session_id])

    def summarize_old_traces(self, session_id: str) -> str:
        with self._lock:
            traces = self._traces[session_id]
        text = "\n".join(
            filter(
                None,
                [
                    f"Thought:{t.thought}\nAction:{t.action}\nObservation:{t.observation}"
                    for t in traces[:-6]
                ],
            )
        )
        return simple_keyword_summary(text, limit=400)

    def get_traces(self, session_id: str) -> List[ExecutionTrace]:
        with self._lock:
            return list(self._traces[session_id])

    def clear_traces(self, session_id: str) -> None:
        with self._lock:
            self._traces.pop(session_id, None)


class SensoryBuffer:
    def __init__(self):
        self._items: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)
        self._lock = threading.RLock()

    def put(self, session_id: str, payload: Any, ttl_seconds: int = 60) -> None:
        expire_at = time.time() + ttl_seconds
        with self._lock:
            self._items[session_id].append((expire_at, payload))

    def get_all(self, session_id: str) -> List[Any]:
        now = time.time()
        with self._lock:
            fresh = [(exp, payload) for exp, payload in self._items[session_id] if exp > now]
            self._items[session_id] = fresh
            return [payload for _, payload in fresh]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._items.pop(session_id, None)
