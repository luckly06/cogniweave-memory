from __future__ import annotations

from enum import Enum


class ModalityType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    MULTIMODAL = "multimodal"
    TOOL_RESULT = "tool_result"
    ENV_EVENT = "environment_event"


class TaskType(str, Enum):
    KNOWLEDGE_QA = "knowledge_qa"
    DIALOGUE_CONTINUATION = "dialogue_continuation"
    PLANNING = "planning"
    CODING = "coding"
    IMAGE_UNDERSTANDING = "image_understanding"
    MULTIMODAL_REASONING = "multimodal_reasoning"


class MemoryType(str, Enum):
    KEY = "key"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PERCEPTUAL = "perceptual"
    EXPERIENCE = "experience"
    WORKING = "working"
    SENSORY = "sensory"
    DISCARD = "discard"


class WritePolicy(str, Enum):
    DROP = "drop"
    BUFFER = "buffer"
    SUMMARY = "summary"
    COMMIT = "commit"
    PROMOTE = "promote"
    DEMOTE = "demote"


class InjectPolicy(str, Enum):
    ALWAYS = "always"
    RETRIEVE = "retrieve"
    TOOL_ONLY = "tool_only"


class MemoryScope(str, Enum):
    USER = "user"
    SESSION = "session"
    TASK = "task"
    GLOBAL = "global"
