"""Phase 6 -- the oracle. Asserts every number in the AGENTS.md brief
and prints PASS/FAIL per check, ending in ALL PASS or FAILURES.

Usage: python3 verify_e2e.py [--no-llm]
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile

from openpyxl import load_workbook

from common import (EXPORTS_DIR, IMPORTS_DIR, PROPOSALS_DIR, ROOT,
                    SCORES_PATH, STATE_DIR, load_portfolio)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def skip(name, detail=""):
    print(f"[SKIP] {name}" + (f" -- {detail}" if detail else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    # ---- Phase 1: seeded world
    portfolio = load_portfolio()
    check("state/ holds exactly 20 items", len(portfolio) == 20,
          f"found {len(portfolio)}")
    check("portfolio ids ML-001..ML-020",
          sorted(portfolio) == [f"ML-{i:03d}" for i in range(1, 21)])

    with open(os.path.join(IMPORTS_DIR, "jira_export.csv")) as f:
        jira_rows = list(csv.DictReader(f))
    check("imports CSV has exactly 15 data rows", len(jira_rows) == 15,
          f"found {len(jira_rows)}")

    wb = load_workbook(os.path.join(IMPORTS_DIR, "backlog_export.xlsx"),
                       read_only=True)
    n = sum(1 for r in list(wb.active.iter_rows(values_only=True))[1:]
            if r and any(c is not None for c in r))
    wb.close()
    check("imports XLSX has exactly 7 data rows", n == 7, f"found {n}")

    # ---- Phase 2: normalization
    with open(os.path.join(PROPOSALS_DIR, "jira.json")) as f:
        pj = json.load(f)
    with open(os.path.join(PROPOSALS_DIR, "backlog.json")) as f:
        pb = json.load(f)
    check("jira normalizer emitted exactly 15 proposals", len(pj) == 15)
    check("backlog normalizer emitted exactly 7 proposals", len(pb) == 7)
    check("refs preserved where present; empty ref otherwise",
          all(p["ref"] for p in pj) and all(p["ref"] == "" for p in pb))

    # ---- Phase 3: reconciliation
    with open(os.path.join(ROOT, "reconcile.json")) as f:
        rec = json.load(f)
    b = rec["summary"]["buckets"]
    expected = {"changed": 11, "gap": 4, "conflict": 2, "ambiguous": 1,
                "duplicate": 1, "completed": 1, "done_gap": 2}
    check("bucket counts match the brief", b == expected,
          f"got {b}")
    check("total rows = 22", rec["summary"]["total"] == 22)

    amb = [r for r in rec["rows"] if r["bucket"] == "ambiguous"]
    check("exactly one ambiguous row", len(amb) == 1)
    if amb:
        a = amb[0]
        check("ambiguous row is 'Autonomous vehicle fleet navigation'",
              a["title"] == "Autonomous vehicle fleet navigation")
        check("ambiguous best match is ML-001", a["match"] == "ML-001")
        check("ambiguous score strictly between 0.40 and 0.80",
              0.40 <= a["score"] < 0.80, f"score={a['score']}")

    dup = [r for r in rec["rows"] if r["bucket"] == "duplicate"]
    check("duplicate row is 'Ops latency dashboard' targeting ML-005",
          len(dup) == 1 and dup[0]["title"] == "Ops latency dashboard"
          and dup[0]["match"] == "ML-005")

    unc = rec["summary"]["unconfirmed"]
    check("unconfirmed = ML-009,010,011,015,019,020",
          unc == ["ML-009", "ML-010", "ML-011", "ML-015", "ML-019",
                  "ML-020"], f"got {unc}")

    with tempfile.TemporaryDirectory() as td:
        p1, p2 = os.path.join(td, "r1.json"), os.path.join(td, "r2.json")
        subprocess.run([sys.executable, "reconcile.py", "--out", p1],
                       check=True, cwd=ROOT, capture_output=True)
        subprocess.run([sys.executable, "reconcile.py", "--out", p2],
                       check=True, cwd=ROOT, capture_output=True)
        check("reconciliation twice -> byte-identical output",
              open(p1, "rb").read() == open(p2, "rb").read())

    # ---- Phase 4: semantic + scoring
    if args.no_llm:
        skip("semantic verdict is SAME/DISTINCT with reason",
             "no-llm mode")
    else:
        ok = bool(amb) and amb[0].get("verdict") in ("SAME", "DISTINCT") \
            and bool(amb[0].get("reason"))
        check("ambiguous row carries verdict SAME/DISTINCT + non-empty reason",
              ok, f"verdict={amb[0].get('verdict') if amb else None}")
    check("ambiguous row bucket still 'ambiguous'",
          bool(amb) and amb[0]["bucket"] == "ambiguous")

    with open(SCORES_PATH) as f:
        scores = json.load(f)
    check("scores.json holds at least one scored item", len(scores) >= 1)
    recompute_ok = True
    for sid, s in scores.items():
        f_ = s["factors"]
        calc = (f_["business_value"] + f_["time_criticality"]
                + f_["risk_reduction"]) / f_["job_size"]
        if abs(calc - s["wsjf"]) > 1e-12:
            recompute_ok = False
    check("every stored score recomputes exactly from its factors",
          recompute_ok)

    # ---- Phase 5: export workbook
    path = os.path.join(EXPORTS_DIR, "reconciliation_export.xlsx")
    check("export workbook exists", os.path.exists(path))
    if os.path.exists(path):
        try:
            wb = load_workbook(path)
            names = wb.sheetnames
            check("export has exactly the four sheets in order",
                  names == ["Cross-Source", "Source-Only", "Unconfirmed",
                            "Semantic"], f"got {names}")
            counts = {ws.title: ws.max_row - 1 for ws in wb.worksheets}
            check("sheet row counts 15/6/6/1",
                  counts == {"Cross-Source": 15, "Source-Only": 6,
                             "Unconfirmed": 6, "Semantic": 1},
                  f"got {counts}")
        except Exception as e:  # noqa: BLE001
            check("export opens with openpyxl without errors", False, str(e))

    # ---- summary
    failed = RESULTS.count(False)
    print()
    if failed:
        print(f"FAILURES: {failed} check(s) failed")
        sys.exit(1)
    print(f"ALL PASS ({len(RESULTS)} checks)")


if __name__ == "__main__":
    main()
