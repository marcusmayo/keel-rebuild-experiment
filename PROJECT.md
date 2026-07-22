# Meridian PPM

A small self-hosted portfolio reconciliation tool for Meridian Logistics. It
ingests two external exports (a Jira CSV and a backlog XLSX), compares them
against a human-readable portfolio (one YAML file per work item in `state/`),
sorts every source row into a named review bucket, asks an AI model to judge
only the genuinely ambiguous matches and to propose WSJF scores, and gives the
operator a TOTP-protected web console plus a four-sheet Excel export.

The operator decides; the tool never decides for them. **Propose, don't
mutate. No delete anywhere.**

## Layout

```
meridian/            shared package (pure, deterministic core + LLM client)
  config.py          paths + thresholds (HIGH=0.80, LOW=0.40)
  matching.py        overlap-coefficient title matching
  portfolio.py       read/update YAML work items (no delete)
  reconcile.py       Phase 3 bucketing engine (deterministic)
  semantic.py        Phase 4 SAME/DISTINCT judgment (LLM)
  scoring.py         Phase 4 WSJF factors + pure arithmetic
  export.py          four-sheet XLSX builder
  auth.py            TOTP secret + verification
  llm.py             OpenAI-compatible chat client
  data_appendix.py   the exact seeded world, verbatim
scripts/             CLI stages (generate/normalize/reconcile/semantic/score)
app.py               Flask operator console (port 8000)
templates/, static/  dark, dense, operator-grade UI
run_e2e.sh           whole pipeline + oracle
verify_e2e.py        the oracle (asserts every number in the brief)
```

Generated at runtime: `state/`, `imports/`, `proposals/`, `reports/`,
`logs/audit.log`, `.totp_secret`.

## Quick start

```bash
pip install -r requirements.txt
set -a; source .env; set +a       # LLM_BASE_URL, OPENROUTER_API_KEY, LLM_MODEL

bash run_e2e.sh                    # generate -> ... -> export -> oracle ALL PASS
bash run_e2e.sh --no-llm           # same, model skipped (verdict checks SKIP)

python3 scripts/setup_totp.py      # print the otpauth:// URL once
python3 app.py                     # operator console on http://localhost:8000
```

## The pipeline

1. **generate** -- write the exact seeded world: 20 portfolio YAML files, a
   15-row Jira CSV, a 7-row backlog XLSX.
2. **normalize** -- read-only mapping of each export into canonical proposal
   records (`ref, title, status, source`). Never writes to `state/`.
3. **reconcile** -- match by ref first, else by best title overlap; sort each
   of the 22 rows into exactly one bucket; write `reports/reconcile.json`.
   Byte-identical on identical input.
4. **semantic** -- send only the ambiguous rows to the model (SAME/DISTINCT +
   reason), annotate in place; bucket never changes. `--no-llm` skips it.
5. **score** -- model proposes WSJF factors (1-10 each); score computed by
   `WSJF = (business_value + time_criticality + risk_reduction) / job_size`.
   Always exactly recomputable from stored factors.
6. **export** -- one workbook, four sheets: Cross-Source (15), Source-Only (6),
   Unconfirmed (6), Semantic (1).

## Buckets (seeded-world counts)

changed 11 · gap 4 · conflict 2 · ambiguous 1 · duplicate 1 · completed 1 ·
done_gap 2 · (unconfirmed portfolio items: 6).
