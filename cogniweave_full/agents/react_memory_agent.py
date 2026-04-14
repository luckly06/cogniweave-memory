from __future__ import annotations

from typing import Optional

from ..core.config import Config
from ..core.llm import BaseLLM
from ..memory.manager import MemoryManager
from .memory_agent import MemoryAgent


class ReActMemoryAgent(MemoryAgent):
    def __init__(
        self,
        name: str,
        llm: BaseLLM,
        memory_manager: MemoryManager,
        user_id: str = "default_user",
        session_id: str = "default_session",
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        react_prompt = system_prompt or "You are a ReAct-style agent. Use JSON with thought, tool_calls, final_answer."
        super().__init__(name, llm, memory_manager, user_id, session_id, react_prompt, config)

    def run(self, input_text: str, **kwargs) -> str:
        kwargs["react_mode"] = True
        return super().run(input_text, **kwargs)
