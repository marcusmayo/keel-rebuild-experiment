#!/usr/bin/env bash
# Phase 6 end-to-end: generate -> normalize -> reconcile -> semantic ->
# one scoring call -> export, then run the oracle (verify_e2e.py).
#
# Usage:
#   bash run_e2e.sh            # full pipeline, model consulted
#   bash run_e2e.sh --no-llm   # skip the model; oracle marks verdicts SKIP
#
# From a clean clone this must end in oracle ALL PASS with no manual steps.
set -euo pipefail

cd "$(dirname "$0")"

NO_LLM=""
if [[ "${1:-}" == "--no-llm" ]]; then
  NO_LLM="--no-llm"
fi

# Load environment (.env) if present, so LLM_* vars are available.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PY="python3"

echo "==> [1/7] ensuring dependencies"
$PY - <<'PYEOF'
import importlib, subprocess, sys
missing = []
for mod, pkg in (("yaml","PyYAML"),("openpyxl","openpyxl"),
                 ("pyotp","pyotp"),("flask","Flask"),("requests","requests")):
    try:
        importlib.import_module(mod)
    except ImportError:
        missing.append(pkg)
if missing:
    subprocess.check_call([sys.executable,"-m","pip","install","-q",*missing])
print("deps OK")
PYEOF

echo "==> [2/7] generate (Phase 1)"
$PY scripts/generate.py

echo "==> [3/7] normalize (Phase 2)"
$PY scripts/normalize.py

echo "==> [4/7] reconcile (Phase 3)"
$PY scripts/reconcile.py

echo "==> [5/7] semantic pass (Phase 4) ${NO_LLM}"
$PY scripts/semantic.py ${NO_LLM}

echo "==> [6/7] one scoring call (Phase 4) ${NO_LLM}"
$PY scripts/score.py ML-001 ${NO_LLM}

echo "==> [7/7] export (Phase 5)"
$PY - <<'PYEOF'
import json
from meridian.config import RECONCILE_JSON, EXPORT_XLSX
from meridian.export import write_export
with RECONCILE_JSON.open() as fh:
    report = json.load(fh)
path = write_export(report, EXPORT_XLSX)
print(f"export written -> {path}")
PYEOF

echo "==> oracle (verify_e2e.py) ${NO_LLM}"
$PY verify_e2e.py ${NO_LLM}
