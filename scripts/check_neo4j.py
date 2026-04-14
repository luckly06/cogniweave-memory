from __future__ import annotations

import argparse

from _integration_common import assert_or_raise, build_config, load_project_env, print_section, require_modules, unique_suffix


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Neo4j link/neighbors connectivity.")
    parser.add_argument("--env-file", default="", help="Optional env file path.")
    args = parser.parse_args()

    env_path = load_project_env(args.env_file or None)
    require_modules(["neo4j"])

    from cogniweave_full.memory.storage.neo4j_store import Neo4jGraphStore

    config = build_config(enable_qdrant=False, enable_neo4j=True, collection_prefix="neo4j_check")
    graph = Neo4jGraphStore(
        uri=config.neo4j_uri,
        user=config.neo4j_user,
        password=config.neo4j_password,
        enabled=True,
    )

    source_id = f"neo4j-check-source-{unique_suffix()}"
    target_id = f"neo4j-check-target-{unique_suffix()}"
    graph.link(source_id, target_id)
    neighbors = graph.neighbors(source_id)
    graph.close()

    print_section("Env")
    print(f"Loaded env: {env_path}")
    print_section("Result")
    print(f"source_id={source_id}")
    print(f"neighbors={neighbors}")

    assert_or_raise(target_id in neighbors, "Neo4j did not return the expected linked target.")


if __name__ == "__main__":
    main()
