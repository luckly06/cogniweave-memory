from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts._integration_common import build_config, env_flag, load_project_env, make_runtime_dir, require_modules


@unittest.skipUnless(
    env_flag("COGNIWEAVE_RUN_REAL_INTEGRATION", False),
    "Set COGNIWEAVE_RUN_REAL_INTEGRATION=true to run the real MiniMax/Qdrant/Neo4j integration suite.",
)
class FullStackIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_project_env()
        require_modules(["openai", "qdrant_client", "neo4j", "dotenv"])

        from cogniweave_full import (
            CalculatorTool,
            Config,
            LLMFactory,
            MemoryLifecycleTool,
            MemoryManager,
            MemorySearchTool,
            OfflineIngestionTool,
            ToolRegistry,
        )

        cls.runtime_dir = make_runtime_dir("cogniweave_full_stack_")
        cls.config = build_config(enable_qdrant=True, enable_neo4j=True, collection_prefix="full_stack")
        cls.llm = LLMFactory.create(config=cls.config)
        cls.registry = ToolRegistry()
        cls.manager = MemoryManager(
            llm=cls.llm,
            tool_registry=cls.registry,
            base_dir=str(cls.runtime_dir),
            config=cls.config,
        )

        cls.registry.register_tool(CalculatorTool())
        cls.registry.register_tool(MemorySearchTool(cls.manager))
        cls.registry.register_tool(MemoryLifecycleTool(cls.manager))
        cls.registry.register_tool(OfflineIngestionTool(cls.manager))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.manager.stop_background_services()
        cls.manager.writeback.close()
        cls.manager.semantic_store.graph_store.close()
        shutil.rmtree(cls.runtime_dir, ignore_errors=True)

    def test_01_minimax_preference_and_scope_fetch(self) -> None:
        result = self.manager.run_cycle(
            user_id="it_user",
            session_id="it_session",
            input_text="记住：以后给 Python 调试建议时先给结论，再列步骤。",
            history=[],
            system_prompt="你是联调测试助手。",
        )
        self.manager.writeback.drain()

        fetched = self.manager.key_store.fetch_for_injection(
            user_id="it_user",
            session_id="it_session",
            task_scope="Python 调试建议",
            policy_scope="coding",
        )

        self.assertTrue(result.final_answer.strip())
        self.assertGreaterEqual(len(fetched), 1)
        self.assertTrue(any(record.pinned for record in fetched))

    def test_02_tool_loop_and_writeback(self) -> None:
        result = self.manager.run_cycle(
            user_id="it_user",
            session_id="it_session",
            input_text="请计算 7+5，并给出简洁结果。",
            history=[],
            system_prompt="你是联调测试助手。",
            react_mode=True,
        )
        self.manager.writeback.drain()

        self.assertTrue(result.final_answer.strip())
        self.assertGreaterEqual(len(self.manager.episodic_store.list_records()), 1)
        self.assertGreaterEqual(len(self.manager.experience_store.list_records()), 1)

    def test_03_offline_ingest_rag_and_graph_link(self) -> None:
        self.manager.run_cycle(
            user_id="it_user",
            session_id="it_session",
            input_text="记住：以后做联调报告时先给结论。",
            history=[],
            system_prompt="你是联调测试助手。",
        )
        self.manager.run_cycle(
            user_id="it_user",
            session_id="it_session",
            input_text="请给我一段联调总结。",
            history=[],
            system_prompt="你是联调测试助手。",
        )
        docs = self.manager.offline_ingestion.ingest_payload(
            source_id="it_doc",
            payload="项目规范：回答应先给结论。多通道系统需要 semantic graph link 和 experience 模板。",
            source_type="document",
            rag_namespace="integration",
        )
        self.manager.writeback.drain()

        raw_input = self.manager._tool_raw_input("it_user", "it_session", "semantic graph link 是什么")
        task_context = self.manager.task_router.route(raw_input)
        task_context = self.manager._augment_task_context(task_context, "it_session")
        _, selected = self.manager.retrieval.run(
            user_id="it_user",
            session_id="it_session",
            query="semantic graph link 是什么",
            task_context=task_context,
            rag_namespace="integration",
            only_rag_data=True,
            enable_mqe=False,
            enable_hyde=False,
        )

        semantic_records = self.manager.semantic_store.list_records()
        linked_semantic = next(
            (record for record in semantic_records if record.metadata.get("related_memory_ids")),
            None,
        )

        self.assertGreaterEqual(len(docs), 1)
        self.assertGreaterEqual(len(selected), 1)
        self.assertIsNotNone(linked_semantic)
        neighbors = self.manager.semantic_store.graph_store.neighbors(linked_semantic.memory_id)
        self.assertTrue(neighbors)


if __name__ == "__main__":
    unittest.main()
