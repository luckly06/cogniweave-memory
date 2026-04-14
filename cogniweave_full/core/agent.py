from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .config import Config
from .llm import BaseLLM
from .message import Message


class Agent(ABC):
    def __init__(
        self,
        name: str,
        llm: BaseLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt or ""
        self.config = config or Config.from_env()
        self._history: list[Message] = []

    @abstractmethod
    def run(self, input_text: str, **kwargs: object) -> str:
        ...

    def add_message(self, message: Message) -> None:
        self._history.append(message)
        self._history = self._history[-self.config.max_history_length :]

    def get_history(self) -> list[Message]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()
