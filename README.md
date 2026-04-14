# CogniWeave Memory

`cogniweave-layered-impl` is the current Python package name for CogniWeave Memory, a local-first Python framework for layered multi-channel memory, retrieval-augmented workflows, and agent execution with memory writeback.

This `0.1.x` release line is the first public packaging line. It is based on the internal architecture milestone `范式+记忆系统&RAG重构 v0.2`, while keeping the framework's core behavior aligned with that code line and focusing this release on packaging, dependency declaration, and documentation.

## Notes

For full design notes, diagrams, and the swimlane flow, see [docs/note.md](docs/note.md).

## What Is Included

- Local-first memory runtime with JSON, SQLite, and local Qdrant path mode
- Multi-channel memory abstractions for key, semantic, episodic, perceptual, and experience memory
- Tool registry and memory-aware agent loop
- Optional MiniMax OpenAI-compatible provider integration
- Optional Neo4j graph linkage

## Installation

Base install:

```bash
pip install cogniweave-layered-impl
```

Install with MiniMax provider support:

```bash
pip install "cogniweave-layered-impl[minimax]"
```

Install with Neo4j graph support:

```bash
pip install "cogniweave-layered-impl[graph]"
```

Install from the GitHub repository tag:

```bash
pip install "git+https://github.com/luckly06/cogniweave-memory.git@v0.1.0"
```

Gitee can remain as a mirror or release distribution channel for the original source repository.

## Quick Start

```python
from cogniweave_full import (
    CalculatorTool,
    Config,
    LLMFactory,
    MemoryAgent,
    MemoryForgetTool,
    MemoryLifecycleTool,
    MemoryManager,
    MemorySearchTool,
    OfflineIngestionTool,
    ToolRegistry,
)

config = Config(
    llm_provider="mock",
    enable_hyde=False,
    enable_mqe=False,
    enable_qdrant=False,
    enable_neo4j=False,
)

llm = LLMFactory.create(config=config)
registry = ToolRegistry()
manager = MemoryManager(
    llm=llm,
    tool_registry=registry,
    base_dir="./runtime_demo",
    config=config,
)

registry.register_tool(CalculatorTool())
registry.register_tool(MemorySearchTool(manager))
registry.register_tool(MemoryForgetTool(manager))
registry.register_tool(MemoryLifecycleTool(manager))
registry.register_tool(OfflineIngestionTool(manager))

agent = MemoryAgent(
    name="assistant",
    llm=llm,
    memory_manager=manager,
    user_id="demo_user",
    session_id="demo_session",
    system_prompt="You are a memory-aware assistant.",
)

print(agent.run("Remember that future answers should start with the conclusion."))
print(agent.run("What did we agree on earlier?"))
```

## Runtime Model

- Default local runtime:
  key memory uses JSON, metadata uses SQLite, vector memory uses local Qdrant path mode
- Optional remote services:
  set `COGNIWEAVE_ENABLE_QDRANT=true` to connect to a remote Qdrant service
- Optional graph enhancement:
  set `COGNIWEAVE_ENABLE_NEO4J=true` and install the `graph` extra

## Environment

See [.env.example](.env.example) for configuration. Important variables:

- `COGNIWEAVE_LLM_PROVIDER`
- `MINIMAX_API_KEY`
- `MINIMAX_BASE_URL`
- `MINIMAX_MODEL`
- `COGNIWEAVE_ENABLE_QDRANT`
- `COGNIWEAVE_ENABLE_NEO4J`

## Validation

Minimal local smoke test:

```bash
python3 smoke_test.py
```

Real integration workflow:

```bash
bash scripts/run_integration_suite.sh
```

See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for full details.

## Release Scope

This package release intentionally avoids changing the framework's core implementation behavior. The `0.1.0` work is limited to packaging, dependency layering, documentation, and release metadata needed for public distribution.

## License

MIT License.
