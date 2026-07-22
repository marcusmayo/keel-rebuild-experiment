#!/usr/bin/env bash
# Meridian PPM -- one-command end-to-end pipeline + oracle.
# Usage: bash run_e2e.sh           (uses the LLM model for semantic + scoring)
#        bash run_e2e.sh --no-llm  (skips the model; semantic verdict checks skipped)
set -euo pipefail

cd "$(dirname "$0")"

NO_LLM=0
if [[ "${1:-}" == "--no-llm" ]]; then
  NO_LLM=1
fi

# Load environment (LLM_BASE_URL, OPENROUTER_API_KEY, LLM_MODEL) from .env if present.
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

echo "=== Meridian PPM end-to-end (no-llm=$NO_LLM) ==="

# Ensure dependencies are present.
pip install -q -r requirements.txt 2>/dev/null || true

# Clean-slate the generated workspace (not secrets/, which holds the TOTP key).
echo "--- resetting workspace ---"
rm -rf state imports proposals reconcile.json scores exports logs
mkdir -p state imports proposals scores exports logs

# Phase 1 -- Foundation and the seeded world.
echo "--- Phase 1: generate ---"
python -m src.generate

# Phase 2 -- Normalization (read-only).
echo "--- Phase 2: normalize ---"
python -m src.normalize_jira
python -m src.normalize_backlog

# Phase 3 -- Reconciliation.
echo "--- Phase 3: reconcile ---"
python -m src.reconcile

# Phase 4 -- Semantic judgment and scoring.
echo "--- Phase 4: semantic + scoring ---"
if [[ "$NO_LLM" == "1" ]]; then
  python -m src.semantic --no-llm
  python -m src.score --item ML-009 --no-llm
else
  python -m src.semantic
  python -m src.score --item ML-009
fi

# Phase 5 -- Export the four-sheet workbook.
echo "--- Phase 5: export ---"
python -m src.export

# Phase 6 -- Oracle.
echo "--- Phase 6: oracle ---"
if [[ "$NO_LLM" == "1" ]]; then
  python verify_e2e.py --no-llm
else
  python verify_e2e.py
fi
