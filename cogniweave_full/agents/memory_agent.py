from __future__ import annotations

from typing import Optional

from ..core.agent import Agent
from ..core.config import Config
from ..core.llm import BaseLLM
from ..core.message import Message
from ..memory.enums import ModalityType
from ..memory.manager import MemoryManager


class MemoryAgent(Agent):
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
        super().__init__(name, llm, system_prompt, config)
        self.memory = memory_manager
        self.user_id = user_id
        self.session_id = session_id

    def run(self, input_text: str, modality: ModalityType = ModalityType.TEXT, **kwargs) -> str:
        result = self.memory.run_cycle(
            user_id=self.user_id,
            session_id=self.session_id,
            input_text=input_text,
            history=[m.to_dict() for m in self.get_history()],
            system_prompt=self.system_prompt,
            modality=modality,
            few_shots=kwargs.get("few_shots"),
            max_steps=kwargs.get("max_steps", 4),
            react_mode=kwargs.get("react_mode", False),
        )
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(result.final_answer, "assistant", metadata={"outcome": result.outcome}))
        return result.final_answer
