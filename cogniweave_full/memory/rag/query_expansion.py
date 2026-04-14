from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ...core.llm import BaseLLM
from ..models import TaskContext


@dataclass
class ExpansionConfig:
    enable_mqe: bool = False
    mqe_expansions: int = 2
    enable_hyde: bool = False


class QueryExpansionService:
    """
    这是按 CogniWeave 改写过的版本：
    - 不是照抄外部示例
    - 生成内容受 TaskContext 与 candidate channel 约束
    - HyDE 生成的是“检索说明段”，不是最终答案
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def _prompt_mqe(self, query: str, task_context: TaskContext, n: int) -> List[str]:
        try:
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "你是 CogniWeave 的查询扩展助手。"
                        "请围绕用户原问题，生成语义等价或互补的检索查询。"
                        "要考虑 task_type 与 memory channels。"
                        "输出中文，简短，每行一个，不要编号。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"原始查询：{query}\n"
                        f"task_type：{task_context.task_type.value}\n"
                        f"channels：{', '.join(ch.value for ch in task_context.candidate_channels)}\n"
                        f"请给出 {n} 个适用于该任务的不同检索表述。"
                    ),
                },
            ]
            text = self.llm.invoke(prompt)
            lines = [ln.strip("- \t") for ln in (text or "").splitlines()]
            outs = [ln for ln in lines if ln and ln != query]
            return outs[:n] or [query]
        except Exception:
            return [query]

    def _prompt_hyde(self, query: str, task_context: TaskContext) -> Optional[str]:
        try:
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "你是 CogniWeave 的检索说明生成器。"
                        "请根据用户问题，写一段适合多通道记忆检索的中性说明段。"
                        "不要写分析过程，不要写结论口吻，不要当成最终回答。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"问题：{query}\n"
                        f"task_type：{task_context.task_type.value}\n"
                        f"channels：{', '.join(ch.value for ch in task_context.candidate_channels)}\n"
                        "请直接写一段中等长度说明，包含关键术语、相关对象、可能涉及的规则、经验或事件线索。"
                    ),
                },
            ]
            return self.llm.invoke(prompt)
        except Exception:
            return None

    def build_expansions(self, query: str, task_context: TaskContext, config: ExpansionConfig) -> List[str]:
        expansions: List[str] = [query]

        if config.enable_mqe and config.mqe_expansions > 0:
            expansions.extend(self._prompt_mqe(query, task_context, config.mqe_expansions))

        if config.enable_hyde:
            hyde_text = self._prompt_hyde(query, task_context)
            if hyde_text:
                expansions.append(hyde_text)

        uniq: List[str] = []
        for e in expansions:
            if e and e not in uniq:
                uniq.append(e)

        return uniq
