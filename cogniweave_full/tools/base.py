from __future__ import annotations

from typing import Any, Dict


class BaseTool:
    name: str = "tool"
    description: str = ""

    def run(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
        }
