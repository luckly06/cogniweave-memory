from __future__ import annotations

from ..base import BaseTool


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Run a simple Python arithmetic expression."

    def run(self, expression: str, **kwargs):
        return {"result": eval(expression, {"__builtins__": {}}, {})}
