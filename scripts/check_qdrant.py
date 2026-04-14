from __future__ import annotations

import argparse
import uuid

from _integration_common import assert_or_raise, build_config, load_project_env, print_section, require_modules


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Qdrant upsert/search connectivity.")
    parser.add_argument("--env-file", default="", help="Optional env file path.")
    args = parser.parse_args()

    env_path = load_project_env(args.env_file or None)
    require_modules(["qdrant_client"])

    from cogniweave_full.memory.enums import MemoryScope, MemoryType
    from cogniweave_full.memory.models import MemoryRecord
    from cogniweave_full.memory.storage.qdrant_store import QdrantVectorStore
    from cogniweave_full.memory.utils import deterministic_embedding

    config = build_config(enable_qdrant=True, enable_neo4j=False, collection_prefix="qdrant_check")
    store = QdrantVectorStore(
        collection_name=f"{config.qdrant_collection_prefix}_semantic_check",
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
    )

    alpha = MemoryRecord(
        memory_id=str(uuid.uuid4()),
        memory_type=MemoryType.SEMANTIC,
        scope=MemoryScope.GLOBAL,
        content="Python 调试方案：先复现，再缩小范围，最后修复。",
        summary="Python 调试方案",
        embedding=deterministic_embedding("Python 调试方案"),
    )
    beta = MemoryRecord(
        memory_id=str(uuid.uuid4()),
        memory_type=MemoryType.SEMANTIC,
        scope=MemoryScope.GLOBAL,
        content="做饭菜单：先备料，再下锅。",
        summary="做饭菜单",
        embedding=deterministic_embedding("做饭菜单"),
    )

    store.upsert(alpha)
    store.upsert(beta)
    hit_ids = store.search(deterministic_embedding("Python 调试"), top_k=2)

    print_section("Env")
    print(f"Loaded env: {env_path}")
    print_section("Result")
    print(f"collection={store.collection_name}")
    print(f"hit_ids={hit_ids}")

    assert_or_raise(hit_ids, "Qdrant search returned no hits.")
    assert_or_raise(hit_ids[0] == alpha.memory_id, "Qdrant top-1 hit did not match the expected semantic record.")


if __name__ == "__main__":
    main()
