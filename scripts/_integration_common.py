from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def ensure_project_root() -> Path:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return PROJECT_ROOT


def load_project_env(env_file: str | None = None) -> Path:
    ensure_project_root()
    env_path = Path(env_file).expanduser() if env_file else PROJECT_ROOT / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:
        if env_path.exists():
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    return env_path


def require_modules(module_names: Sequence[str]) -> None:
    missing = []
    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)
    if missing:
        raise RuntimeError(
            "Missing Python modules: "
            + ", ".join(missing)
            + ". Install dependencies with `pip install -r requirements.txt` or create the conda env first."
        )


def unique_suffix() -> str:
    return str(int(time.time() * 1000))


def make_runtime_dir(prefix: str = "cogniweave_it_") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def assert_or_raise(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_config(
    *,
    enable_qdrant: bool = False,
    enable_neo4j: bool = False,
    collection_prefix: str = "cogniweave_it",
):
    ensure_project_root()
    from cogniweave_full import Config

    base = Config.from_env()
    base.enable_qdrant = enable_qdrant
    base.enable_neo4j = enable_neo4j
    base.enable_hyde = False
    base.enable_mqe = False
    base.enable_forget = False
    base.candidate_pool_multiplier = 2
    base.qdrant_collection_prefix = f"{collection_prefix}_{unique_suffix()}"
    return base
