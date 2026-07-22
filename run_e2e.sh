#!/usr/bin/env bash
# Phase 6 -- one command, whole pipeline + oracle.
# Usage: bash run_e2e.sh [--no-llm]
set -euo pipefail
cd "$(dirname "$0")"

NO_LLM=""
if [[ "${1:-}" == "--no-llm" ]]; then
  NO_LLM="--no-llm"
fi

# Load .env into the environment for the LLM touchpoints.
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

echo "==> dependencies"
pip install -q -r requirements.txt

echo "==> phase 1: generate seeded world"
python3 generate_seed.py

echo "==> phase 2: normalize"
python3 normalize_jira.py
python3 normalize_backlog.py

echo "==> phase 3: reconcile"
python3 reconcile.py

echo "==> phase 4: semantic pass ${NO_LLM:+(no-llm)}"
python3 semantic.py $NO_LLM

echo "==> phase 4: scoring ${NO_LLM:+(no-llm)}"
python3 score.py --item ML-009 $NO_LLM

echo "==> export"
python3 export.py

echo "==> totp setup"
python3 setup_totp.py

echo "==> oracle"
python3 verify_e2e.py $NO_LLM
