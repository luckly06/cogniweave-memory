import os
from dotenv import load_dotenv

from cogniweave_full import (
    CalculatorTool,
    Config,
    LLMFactory,
    MemoryAgent,
    MemoryManager,
    MemoryForgetTool,
    MemoryLifecycleTool,
    MemorySearchTool,
    OfflineIngestionTool,
    ReActMemoryAgent,
    ToolRegistry,
)


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    config = Config.from_env()
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

    manager.start_background_services()

    agent = MemoryAgent(
        "assistant",
        llm,
        manager,
        user_id="demo_user",
        session_id="demo_session",
        system_prompt="你是一个具备多通道记忆能力的智能体。回答尽量先给结论再解释。",
    )

    print(agent.run("记住：以后回答先给结论。"))
    print(agent.run("我们前面约定了什么？"))

    react_agent = ReActMemoryAgent(
        "react",
        llm,
        manager,
        user_id="demo_user",
        session_id="demo_session",
    )
    print(react_agent.run("请用 react_json 方式回答。"))

    manager.stop_background_services()


if __name__ == "__main__":
    main()
