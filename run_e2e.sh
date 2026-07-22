#!/usr/bin/env bash
# Phase 6: End-to-end — run the full pipeline and verify with the oracle.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

NO_LLM=""
if [[ "${1:-}" == "--no-llm" ]]; then
    NO_LLM="--no-llm"
    echo "Running in --no-llm mode (deterministic, no network calls)"
fi

echo "=== Phase 1: Generate ==="
python3 generate.py

echo ""
echo "=== Phase 2: Normalize ==="
python3 normalize.py

echo ""
echo "=== Phase 3: Reconcile ==="
python3 reconcile.py

echo ""
echo "=== Phase 4: Semantic & Scoring ==="
python3 semantic.py $NO_LLM

echo ""
echo "=== Phase 5: Export ==="
python3 export.py

echo ""
echo "=== Phase 6: Oracle ==="
python3 verify_e2e.py $NO_LLM

echo ""
echo "E2E pipeline complete."