import shutil
import sys
import tempfile

sys.path.insert(0, ".")

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


def main() -> None:
    base_dir = tempfile.mkdtemp(prefix="cogniweave_smoke_")
    try:
        config = Config(
            llm_provider="mock",
            enable_hyde=False,
            enable_mqe=False,
            enable_qdrant=False,
            enable_neo4j=False,
        )
        llm = LLMFactory.create(config=config)
        registry = ToolRegistry()
        manager = MemoryManager(llm=llm, tool_registry=registry, base_dir=base_dir, config=config)

        registry.register_tool(CalculatorTool())
        registry.register_tool(MemorySearchTool(manager))
        registry.register_tool(MemoryForgetTool(manager))
        registry.register_tool(MemoryLifecycleTool(manager))
        registry.register_tool(OfflineIngestionTool(manager))

        agent = MemoryAgent(
            name="smoke",
            llm=llm,
            memory_manager=manager,
            user_id="smoke_user",
            session_id="smoke_session",
            system_prompt="你是测试助手。",
        )

        first = agent.run("记住：以后回答先给结论。")
        second = agent.run("请计算 2+2，并给出结果。", react_mode=True)
        third = agent.run("我们前面约定了什么？")
        ingest_result = registry.get_tool("offline_ingest").run(
            source_id="smoke_doc",
            payload="这是离线导入的项目文档。系统支持多通道记忆与RAG融合。",
            source_type="log",
            memory_type="semantic",
            scope="global",
            rag_namespace="smoke",
        )
        manager.writeback.drain()

        print("FIRST", first[:160])
        print("SECOND", second[:160])
        print("THIRD", third[:160])
        print("INGEST", ingest_result)
        print("KEY", len(manager.key_store.list_records()))
        print("EPISODIC", len(manager.episodic_store.list_records()))
        print("EXPERIENCE", len(manager.experience_store.list_records()))
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
