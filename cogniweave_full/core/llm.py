from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency at runtime
    OpenAI = None

from .config import Config
from .exceptions import LLMException


class BaseLLM:
    provider: str = "base"

    def invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        raise NotImplementedError

    def stream_invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterator[str]:
        yield self.invoke(messages, **kwargs)


class MockLLM(BaseLLM):
    provider = "mock"

    def invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        tool_messages = [m for m in messages if m["role"] == "tool"]
        if tool_messages:
            last_tool = tool_messages[-1]["content"]
            return json.dumps(
                {
                    "thought": "已获得工具结果，给出最终答案。",
                    "tool_calls": [],
                    "final_answer": f"基于工具结果：{last_tool}",
                },
                ensure_ascii=False,
            )
        if "Available Tools" in "\n".join(m["content"] for m in messages if m["role"] == "system"):
            expression = re.search(r"(\d+\s*[-+*/]\s*\d+)", user)
            if expression:
                return json.dumps(
                    {
                        "thought": "需要先调用 calculator 计算表达式。",
                        "tool_calls": [
                            {
                                "name": "calculator",
                                "arguments": {"expression": expression.group(1)},
                            }
                        ],
                        "final_answer": "",
                    },
                    ensure_ascii=False,
                )
        if "planner_json" in user:
            return json.dumps({"steps": ["理解问题", "检索相关记忆", "组织答案"]}, ensure_ascii=False)
        if "react_json" in user:
            return json.dumps(
                {
                    "thought": "当前信息足够，直接回答。",
                    "tool_calls": [],
                    "final_answer": "这是一个 mock 响应。",
                },
                ensure_ascii=False,
            )
        return "MockLLM response: " + user[:500]


class MiniMaxOpenAICompatLLM(BaseLLM):
    """
    这里严格按你的要求实现：
    - Base URL: https://api.minimaxi.com
    - Endpoint: /v1/chat/completions
    - Model: MiniMax-M2.7
    不使用 /anthropic
    """

    provider = "minimax_openai_compat"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.minimaxi.com",
        model: str = "MiniMax-M2.7",
        temperature: float = 0.2,
        max_completion_tokens: Optional[int] = 2048,
        timeout: int = 120,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self.timeout = timeout

        if OpenAI is None:
            raise LLMException("openai package is required for minimax_openai_compat")

        # OpenAI SDK 的 base_url 需要带 /v1，这里显式拼接，避免误接 /anthropic
        self._client = OpenAI(
            api_key=api_key,
            base_url=f"{self.base_url}/v1",
            timeout=timeout,
        )

    def _normalize_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        MiniMax 的兼容入口对 message role 和顺序更严格：
        - system 最好只保留 1 条并放在最前面
        - 当前框架里的 tool 消息是手工 observation，不是官方 tool-calls 协议
        """
        system_parts: List[str] = []
        normalized: List[Dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "user")).strip() or "user"
            content = str(message.get("content", ""))
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
                continue
            if role == "tool":
                normalized.append({"role": "user", "content": f"[Tool Result]\n{content}"})
                continue
            if role not in {"user", "assistant"}:
                normalized.append({"role": "user", "content": f"[{role}]\n{content}"})
                continue
            normalized.append({"role": role, "content": content})

        if system_parts:
            return [{"role": "system", "content": "\n\n".join(system_parts)}] + normalized
        return normalized

    def invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        normalized_messages = self._normalize_messages(messages)
        try:
            response = self._client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=normalized_messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_completion_tokens=kwargs.get(
                    "max_completion_tokens",
                    self.max_completion_tokens,
                ),
                stream=False,
            )
        except Exception as exc:
            raise LLMException(f"MiniMax invocation failed: {exc}") from exc

        message = response.choices[0].message
        return message.content or ""

    def stream_invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterator[str]:
        normalized_messages = self._normalize_messages(messages)
        try:
            stream = self._client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=normalized_messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_completion_tokens=kwargs.get(
                    "max_completion_tokens",
                    self.max_completion_tokens,
                ),
                stream=True,
            )
        except Exception as exc:
            raise LLMException(f"MiniMax streaming failed: {exc}") from exc

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and getattr(delta, "content", None):
                yield delta.content


class LLMFactory:
    @staticmethod
    def create(config: Optional[Config] = None, **overrides: Any) -> BaseLLM:
        config = config or Config.from_env()
        provider = overrides.get("provider", config.llm_provider)

        if provider == "mock":
            return MockLLM()

        if provider == "minimax_openai_compat":
            api_key = overrides.get("api_key") or os.getenv("MINIMAX_API_KEY", "")
            if not api_key:
                raise LLMException("MINIMAX_API_KEY is required for minimax_openai_compat")

            return MiniMaxOpenAICompatLLM(
                api_key=api_key,
                base_url=overrides.get("base_url", config.llm_base_url),
                model=overrides.get("model", config.llm_model),
                temperature=overrides.get("temperature", config.llm_temperature),
                max_completion_tokens=overrides.get(
                    "max_completion_tokens",
                    config.llm_max_completion_tokens,
                ),
                timeout=overrides.get("timeout", config.llm_timeout),
            )

        raise LLMException(f"Unsupported provider: {provider}")
