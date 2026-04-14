from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class Config:
    # LLM
    llm_provider: str = "minimax_openai_compat"
    llm_model: str = "MiniMax-M2.7"
    llm_base_url: str = "https://api.minimaxi.com"
    llm_temperature: float = 0.2
    llm_max_completion_tokens: int = 2048
    llm_timeout: int = 120

    # Runtime
    debug: bool = False
    max_history_length: int = 50
    working_memory_turns: int = 8
    default_k_retrieve: int = 12
    default_k_context: int = 6
    summary_char_limit: int = 320

    # RAG expansion
    enable_mqe: bool = True
    mqe_expansions: int = 2
    enable_hyde: bool = True
    candidate_pool_multiplier: int = 4

    # Storage toggles
    enable_qdrant: bool = False
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_prefix: str = "cogniweave"

    enable_neo4j: bool = False
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "secretgraph"

    # Forget
    enable_forget: bool = False
    forget_interval_seconds: int = 1800

    # Fixed version markers
    python_version: str = "3.11"
    openai_sdk_version: str = "2.30.0"
    qdrant_server_version: str = "1.17.1"
    qdrant_client_version: str = "1.17.1"
    neo4j_server_version: str = "5.26.24"
    neo4j_driver_version: str = "6.1.0"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm_provider=os.getenv("COGNIWEAVE_LLM_PROVIDER", "minimax_openai_compat"),
            llm_model=os.getenv("MINIMAX_MODEL", "MiniMax-M2.7"),
            llm_base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com"),
            llm_temperature=float(os.getenv("COGNIWEAVE_LLM_TEMPERATURE", "0.2")),
            llm_max_completion_tokens=int(os.getenv("COGNIWEAVE_LLM_MAX_COMPLETION_TOKENS", "2048")),
            llm_timeout=int(os.getenv("COGNIWEAVE_LLM_TIMEOUT", "120")),
            debug=os.getenv("COGNIWEAVE_DEBUG", "false").lower() == "true",
            max_history_length=int(os.getenv("COGNIWEAVE_MAX_HISTORY", "50")),
            working_memory_turns=int(os.getenv("COGNIWEAVE_WORKING_TURNS", "8")),
            default_k_retrieve=int(os.getenv("COGNIWEAVE_K_RETRIEVE", "12")),
            default_k_context=int(os.getenv("COGNIWEAVE_K_CONTEXT", "6")),
            summary_char_limit=int(os.getenv("COGNIWEAVE_SUMMARY_CHAR_LIMIT", "320")),
            enable_mqe=os.getenv("COGNIWEAVE_ENABLE_MQE", "true").lower() == "true",
            mqe_expansions=int(os.getenv("COGNIWEAVE_MQE_EXPANSIONS", "2")),
            enable_hyde=os.getenv("COGNIWEAVE_ENABLE_HYDE", "true").lower() == "true",
            candidate_pool_multiplier=int(os.getenv("COGNIWEAVE_CANDIDATE_POOL_MULTIPLIER", "4")),
            enable_qdrant=os.getenv("COGNIWEAVE_ENABLE_QDRANT", "false").lower() == "true",
            qdrant_url=os.getenv("COGNIWEAVE_QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("COGNIWEAVE_QDRANT_API_KEY", ""),
            qdrant_collection_prefix=os.getenv("COGNIWEAVE_QDRANT_COLLECTION_PREFIX", "cogniweave"),
            enable_neo4j=os.getenv("COGNIWEAVE_ENABLE_NEO4J", "false").lower() == "true",
            neo4j_uri=os.getenv("COGNIWEAVE_NEO4J_URI", "neo4j://localhost:7687"),
            neo4j_user=os.getenv("COGNIWEAVE_NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("COGNIWEAVE_NEO4J_PASSWORD", "secretgraph"),
            enable_forget=os.getenv("COGNIWEAVE_ENABLE_FORGET", "false").lower() == "true",
            forget_interval_seconds=int(os.getenv("COGNIWEAVE_FORGET_INTERVAL_SECONDS", "1800")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
