from __future__ import annotations

import argparse

from _integration_common import load_project_env, print_section, require_modules


def main() -> None:
    parser = argparse.ArgumentParser(description="Check MiniMax OpenAI-compatible connectivity.")
    parser.add_argument("--env-file", default="", help="Optional env file path.")
    parser.add_argument("--prompt", default="请用一句话回答：MiniMax 联调已连接。", help="Prompt sent to MiniMax.")
    args = parser.parse_args()

    env_path = load_project_env(args.env_file or None)
    require_modules(["openai"])

    from cogniweave_full import Config, LLMFactory

    print_section("Env")
    print(f"Loaded env: {env_path}")

    config = Config.from_env()
    llm = LLMFactory.create(config=config)
    response = llm.invoke(
        [
            {"role": "system", "content": "你是联调检查助手。请简洁回答。"},
            {"role": "user", "content": args.prompt},
        ]
    )

    print_section("Request")
    print(f"provider={config.llm_provider}")
    print(f"model={config.llm_model}")
    print(f"base_url={config.llm_base_url}")
    print_section("Response")
    print(response.strip())


if __name__ == "__main__":
    main()
