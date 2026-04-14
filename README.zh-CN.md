# CogniWeave Memory

[English](README.md) | [中文](README.zh-CN.md)

`cogni-mem` 是 CogniWeave Memory 当前使用的 Python 包名。它是一个面向智能体的本地优先 Python 记忆框架，核心关注多通道记忆、检索增强工作流，以及带记忆写回能力的执行链路。

当前 `0.1.x` 系列是首个公开发布线。它基于内部架构阶段 `范式+记忆系统&RAG重构 v0.2` 整理而来，核心框架行为保持与该代码线一致，这一阶段主要补齐打包、依赖声明和文档入口。

## 说明文档

完整设计笔记、配图和泳道图说明见 [docs/note.md](docs/note.md)。
`v0.1.0` 的发布说明见 [docs/releases/v0.1.0.zh-CN.md](docs/releases/v0.1.0.zh-CN.md)。

## 框架包含内容

- 本地优先记忆运行时，默认组合 JSON、SQLite 和本地 Qdrant path 模式
- Key、Semantic、Episodic、Perceptual、Experience 等多通道记忆抽象
- Tool Registry 与记忆增强 Agent 执行链路
- 可选的 MiniMax OpenAI-compatible provider 集成
- 可选的 Neo4j 图增强能力

## 安装

基础安装：

```bash
pip install cogni-mem
```

安装 MiniMax provider 支持：

```bash
pip install "cogni-mem[minimax]"
```

安装 Neo4j 图能力支持：

```bash
pip install "cogni-mem[graph]"
```

从 GitHub tag 安装：

```bash
pip install "git+https://github.com/luckly06/cogniweave-memory.git@v0.1.0"
```

Gitee 可以继续作为原始来源仓库的镜像或发布通道。

## 快速开始

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

## 运行模型

- 默认本地运行模式：
  key memory 使用 JSON，metadata 使用 SQLite，vector memory 使用本地 Qdrant path 模式
- 可选远程服务：
  设置 `COGNIWEAVE_ENABLE_QDRANT=true` 连接远程 Qdrant
- 可选图增强能力：
  设置 `COGNIWEAVE_ENABLE_NEO4J=true` 并安装 `graph` extra

## 环境变量

配置样例见 [.env.example](.env.example)。关键变量包括：

- `COGNIWEAVE_LLM_PROVIDER`
- `MINIMAX_API_KEY`
- `MINIMAX_BASE_URL`
- `MINIMAX_MODEL`
- `COGNIWEAVE_ENABLE_QDRANT`
- `COGNIWEAVE_ENABLE_NEO4J`

## 验证

最小本地 smoke test：

```bash
python3 smoke_test.py
```

真实联调流程：

```bash
bash scripts/run_integration_suite.sh
```

完整说明见 [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)。

## 发布范围

这一版公开发布刻意不改框架核心实现行为。`0.1.0` 的工作范围主要是打包、依赖分层、文档整理和公开分发所需的发布元数据。

## 许可证

MIT License.
