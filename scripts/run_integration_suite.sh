#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.integration.yml"
KEEP_SERVICES_UP="${KEEP_SERVICES_UP:-0}"
CONDA_SH="${CONDA_SH:-/home/dd/miniconda3/etc/profile.d/conda.sh}"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-cogniweave-minimax}"

cleanup() {
  if [[ "$KEEP_SERVICES_UP" == "1" ]]; then
    return
  fi
  cd "$PROJECT_ROOT"
  docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
}

wait_for_healthy() {
  local service="$1"
  local retries="${2:-30}"
  local delay="${3:-2}"
  local i url
  case "$service" in
    neo4j)
      url="http://127.0.0.1:7474"
      ;;
    qdrant)
      url="http://127.0.0.1:6333/collections"
      ;;
    *)
      echo "Unknown service for health wait: $service" >&2
      return 1
      ;;
  esac
  for i in $(seq 1 "$retries"); do
    if python3 - <<PY >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("$url", timeout=2).read(1)
PY
    then
      return 0
    fi
    sleep "$delay"
  done
  echo "Service $service did not become healthy in time." >&2
  return 1
}

if [[ ! -f "$CONDA_SH" ]]; then
  echo "conda.sh not found: $CONDA_SH" >&2
  exit 1
fi

trap cleanup EXIT

cd "$PROJECT_ROOT"

echo "[1/6] Starting integration services"
docker compose -f "$COMPOSE_FILE" up -d

echo "[2/6] Waiting for Neo4j"
wait_for_healthy neo4j

echo "[3/6] Waiting for Qdrant"
wait_for_healthy qdrant

echo "[4/6] Running single-component checks"
source "$CONDA_SH"
conda run -n "$CONDA_ENV_NAME" python "$PROJECT_ROOT/scripts/check_minimax.py"
conda run -n "$CONDA_ENV_NAME" python "$PROJECT_ROOT/scripts/check_qdrant.py"
conda run -n "$CONDA_ENV_NAME" python "$PROJECT_ROOT/scripts/check_neo4j.py"

echo "[5/6] Running real end-to-end integration tests"
COGNIWEAVE_RUN_REAL_INTEGRATION=true \
  conda run -n "$CONDA_ENV_NAME" python -m unittest "$PROJECT_ROOT/tests/integration/test_full_stack.py" -v

echo "[6/6] Integration suite completed"
