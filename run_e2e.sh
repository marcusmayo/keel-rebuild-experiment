#!/usr/bin/env bash
# Phase 6: End-to-end pipeline — generate, normalize, reconcile, semantic, export
set -e

NO_LLM_FLAG=""
if [[ "$*" == *"--no-llm"* ]]; then
    NO_LLM_FLAG="--no-llm"
fi

echo "============================================"
echo " Meridian PPM — End-to-End Pipeline"
echo "============================================"

# Phase 1: Generate seeded world
echo ""
echo "► Phase 1: Generating seeded world..."
python3 generate.py

# Phase 2: Normalize exports
echo ""
echo "► Phase 2: Normalizing exports..."
python3 normalize.py

# Phase 3: Reconcile
echo ""
echo "► Phase 3: Reconciling..."
python3 reconcile.py

# Run reconciliation twice to verify byte-identical output
cp reconcile.json reconcile.json.1
python3 reconcile.py
if diff reconcile.json reconcile.json.1 > /dev/null 2>&1; then
    echo "  ✓ Reconciliation is deterministic (byte-identical)"
else
    echo "  ✗ Reconciliation is NOT deterministic!"
    exit 1
fi
rm reconcile.json.1

# Phase 4: Semantic judgment + scoring
echo ""
echo "► Phase 4: Semantic judgment & scoring..."
python3 semantic.py $NO_LLM_FLAG ML-001

# Phase 5: Export
echo ""
echo "► Phase 5: Generating Excel export..."
python3 -c "
import sys
sys.path.insert(0, '.')
from app import app
from io import BytesIO
from openpyxl import load_workbook

with app.test_client() as client:
    # Simulate a session-authenticated export
    with client.session_transaction() as sess:
        sess['authenticated'] = True
    resp = client.get('/export')
    with open('meridian_reconciliation.xlsx', 'wb') as f:
        f.write(resp.data)
print('  ✓ Export saved to meridian_reconciliation.xlsx')
"

# Phase 6: Verify
echo ""
echo "► Phase 6: Running oracle..."
python3 verify_e2e.py $NO_LLM_FLAG

echo ""
echo "============================================"
echo " End-to-end pipeline complete."
echo "============================================"