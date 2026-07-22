#!/usr/bin/env python3
"""The oracle: assert every number in the brief and print PASS/FAIL per check.

Usage:
    python3 verify_e2e.py            # full run (expects semantic verdicts)
    python3 verify_e2e.py --no-llm   # semantic verdict checks marked SKIP

Exit code is 0 only when there are zero FAILs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meridian.config import (
    STATE_DIR,
    IMPORTS_DIR,
    JIRA_CSV,
    BACKLOG_XLSX,
    JIRA_PROPOSALS,
    BACKLOG_PROPOSALS,
    RECONCILE_JSON,
    SCORES_JSON,
    EXPORT_XLSX,
)
from meridian.scoring import compute_wsjf

RESULTS = []  # list of (status, message) where status in {PASS, FAIL, SKIP}


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    RESULTS.append((status, name, detail))


def skip(name: str, detail: str = "") -> None:
    RESULTS.append(("SKIP", name, detail))


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    # --- Phase 1: seeded world ---
    yaml_files = sorted(STATE_DIR.glob("*.yaml"))
    check("Phase1: state/ holds exactly 20 items", len(yaml_files) == 20,
          f"found {len(yaml_files)}")
    csv_files = list(IMPORTS_DIR.glob("*.csv"))
    xlsx_files = list(IMPORTS_DIR.glob("*.xlsx"))
    check("Phase1: imports/ holds exactly one CSV", len(csv_files) == 1,
          f"found {len(csv_files)}")
    check("Phase1: imports/ holds exactly one XLSX", len(xlsx_files) == 1,
          f"found {len(xlsx_files)}")

    # CSV row count (15 data rows).
    import csv as _csv
    with JIRA_CSV.open("r", encoding="utf-8", newline="") as fh:
        jira_rows = list(_csv.DictReader(fh))
    check("Phase1: Jira CSV has 15 data rows", len(jira_rows) == 15,
          f"found {len(jira_rows)}")

    from openpyxl import load_workbook
    wb = load_workbook(BACKLOG_XLSX, read_only=True)
    ws = wb.active
    backlog_data = [r for i, r in enumerate(ws.iter_rows(values_only=True))
                    if i > 0 and r is not None and any(c is not None for c in r)]
    wb.close()
    check("Phase1: backlog XLSX has 7 data rows", len(backlog_data) == 7,
          f"found {len(backlog_data)}")

    # --- Phase 2: normalization ---
    jira_prop = load_json(JIRA_PROPOSALS)
    backlog_prop = load_json(BACKLOG_PROPOSALS)
    check("Phase2: Jira normalizer emits exactly 15 proposals",
          len(jira_prop) == 15, f"found {len(jira_prop)}")
    check("Phase2: backlog normalizer emits exactly 7 proposals",
          len(backlog_prop) == 7, f"found {len(backlog_prop)}")
    check("Phase2: refs preserved for jira rows",
          all(p["ref"] for p in jira_prop),
          "some jira ref empty")
    check("Phase2: backlog rows carry empty ref",
          all(p["ref"] == "" for p in backlog_prop),
          "some backlog ref non-empty")
    check("Phase2: state/ still holds exactly 20 items (read-only ingestion)",
          len(sorted(STATE_DIR.glob('*.yaml'))) == 20)

    # --- Phase 3: reconciliation ---
    report = load_json(RECONCILE_JSON)
    counts = report["summary"]["buckets"]
    expected = {"changed": 11, "gap": 4, "conflict": 2, "ambiguous": 1,
                "duplicate": 1, "completed": 1, "done_gap": 2}
    for bucket, exp in expected.items():
        got = counts.get(bucket, 0)
        check(f"Phase3: bucket {bucket} == {exp}", got == exp, f"got {got}")
    check("Phase3: total rows == 22", report["summary"]["total"] == 22,
          f"got {report['summary']['total']}")

    # Ambiguous row identity.
    amb = [r for r in report["rows"] if r["bucket"] == "ambiguous"]
    amb_ok = (len(amb) == 1
              and amb[0]["title"] == "Autonomous vehicle fleet navigation"
              and amb[0]["target"] == "ML-001"
              and 0.40 < amb[0]["score"] < 0.80)
    check("Phase3: ambiguous row is 'Autonomous vehicle fleet navigation' "
          "-> ML-001, 0.40<score<0.80", amb_ok,
          str(amb[0]) if amb else "no ambiguous row")

    # Duplicate row identity.
    dup = [r for r in report["rows"] if r["bucket"] == "duplicate"]
    dup_ok = (len(dup) == 1
              and dup[0]["title"] == "Ops latency dashboard"
              and dup[0]["target"] == "ML-005")
    check("Phase3: duplicate row is 'Ops latency dashboard' -> ML-005",
          dup_ok, str(dup[0]) if dup else "no duplicate row")

    # Unconfirmed set.
    unconf = report["summary"]["unconfirmed"]
    exp_unconf = ["ML-009", "ML-010", "ML-011", "ML-015", "ML-019", "ML-020"]
    check("Phase3: unconfirmed == 6 exact items {009,010,011,015,019,020}",
          sorted(unconf) == exp_unconf, str(unconf))

    # Determinism: reconciler produces byte-identical output on re-run. Note
    # re-running reconcile strips semantic annotations, so we snapshot the
    # current (annotated) report, run reconcile twice, compare bytes, then
    # restore the snapshot for the remaining checks.
    before = RECONCILE_JSON.read_bytes()
    proc_a = subprocess.run([sys.executable, "scripts/reconcile.py"],
                            capture_output=True, text=True)
    run_a = RECONCILE_JSON.read_bytes()
    proc_b = subprocess.run([sys.executable, "scripts/reconcile.py"],
                            capture_output=True, text=True)
    run_b = RECONCILE_JSON.read_bytes()
    check("Phase3: reconcile.json is byte-identical across runs",
          run_a == run_b and proc_a.returncode == 0 and proc_b.returncode == 0)
    # Restore the (possibly semantic-annotated) report for later checks.
    RECONCILE_JSON.write_bytes(before)
    report = load_json(RECONCILE_JSON)

    # --- Phase 4: semantic + scoring ---
    amb = [r for r in report["rows"] if r["bucket"] == "ambiguous"]
    if args.no_llm:
        skip("Phase4: ambiguous row carries a SAME/DISTINCT verdict",
             "--no-llm: semantic verdict skipped")
        skip("Phase4: verdict reason is non-empty", "--no-llm")
        check("Phase4: ambiguous row bucket still 'ambiguous'",
              len(amb) == 1 and amb[0]["bucket"] == "ambiguous")
        check("Phase4: no other row was annotated with a verdict",
              all("semantic" not in r for r in report["rows"]
                  if r["bucket"] != "ambiguous"))
    else:
        v_ok = (len(amb) == 1 and "semantic" in amb[0]
                and amb[0]["semantic"].get("verdict") in {"SAME", "DISTINCT"})
        check("Phase4: ambiguous row carries a SAME/DISTINCT verdict", v_ok,
              str(amb[0].get("semantic")) if amb else "no ambiguous row")
        r_ok = (len(amb) == 1 and "semantic" in amb[0]
                and bool(amb[0]["semantic"].get("reason")))
        check("Phase4: verdict reason is non-empty", r_ok)
        check("Phase4: ambiguous row bucket still 'ambiguous'",
              len(amb) == 1 and amb[0]["bucket"] == "ambiguous")
        check("Phase4: no other row was annotated with a verdict",
              all("semantic" not in r for r in report["rows"]
                  if r["bucket"] != "ambiguous"))

    # Scoring: recompute from stored factors reproduces stored value exactly.
    if SCORES_JSON.exists():
        scores = load_json(SCORES_JSON)
        recompute_ok = all(
            compute_wsjf(s["factors"]) == s["wsjf"] for s in scores
        ) and len(scores) >= 1
        check("Phase4: every stored score recomputes exactly from its factors",
              recompute_ok, f"{len(scores)} score(s)")
    else:
        check("Phase4: scores.json exists with at least one score", False,
              "scores.json missing")

    # --- Phase 5 / export: four sheets, exact counts ---
    if EXPORT_XLSX.exists():
        wb = load_workbook(EXPORT_XLSX)
        names = wb.sheetnames
        check("Phase5: export has exactly four sheets",
              names == ["Cross-Source", "Source-Only", "Unconfirmed",
                        "Semantic"], str(names))
        sheet_counts = {ws.title: ws.max_row - 1 for ws in wb.worksheets}
        check("Phase5: Cross-Source has 15 rows",
              sheet_counts.get("Cross-Source") == 15,
              str(sheet_counts.get("Cross-Source")))
        check("Phase5: Source-Only has 6 rows",
              sheet_counts.get("Source-Only") == 6,
              str(sheet_counts.get("Source-Only")))
        check("Phase5: Unconfirmed has 6 rows",
              sheet_counts.get("Unconfirmed") == 6,
              str(sheet_counts.get("Unconfirmed")))
        check("Phase5: Semantic has 1 row",
              sheet_counts.get("Semantic") == 1,
              str(sheet_counts.get("Semantic")))
    else:
        check("Phase5: export workbook exists", False, "export missing")

    # --- Product rule: no delete affordance in the codebase ---
    grep = subprocess.run(
        ["grep", "-rniE", r"\.(unlink|remove)\(|shutil\.rmtree|os\.rmdir|"
         r"methods=\[[^]]*DELETE",
         "--include=*.py", "--include=*.html", "."],
        capture_output=True, text=True,
    )
    hits = [ln for ln in grep.stdout.splitlines() if "/.git/" not in ln]
    check("Product rule: no delete code path (unlink/remove/rmtree/DELETE)",
          len(hits) == 0, "; ".join(hits[:3]))

    # --- Print report ---
    print("=" * 70)
    print("MERIDIAN PPM ORACLE" + ("  (--no-llm)" if args.no_llm else ""))
    print("=" * 70)
    n_pass = n_fail = n_skip = 0
    for status, name, detail in RESULTS:
        if status == "PASS":
            n_pass += 1
        elif status == "FAIL":
            n_fail += 1
        else:
            n_skip += 1
        line = f"[{status}] {name}"
        if detail and status != "PASS":
            line += f"  -- {detail}"
        print(line)
    print("-" * 70)
    print(f"{n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    if n_fail == 0:
        print("ALL PASS")
        return 0
    print("ORACLE FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
