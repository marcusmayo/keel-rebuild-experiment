#!/usr/bin/env python3
"""Phase 6: Oracle — verify every number from the brief."""

import json
import os
import sys
import yaml
from openpyxl import load_workbook

BASE = os.path.dirname(os.path.abspath(__file__))

PASS = 0
FAIL = 0
SKIP = 0

def check(name, condition, detail=""):
    global PASS, FAIL, SKIP
    if condition is None:
        SKIP += 1
        print(f"  SKIP  {name} — {detail}")
        return
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} — {detail}")


def main():
    global PASS, FAIL, SKIP
    no_llm = "--no-llm" in sys.argv

    print("=" * 60)
    print("Meridian PPM — End-to-End Oracle")
    print("=" * 60)

    # --- Phase 1: Generator ---
    print("\n[Phase 1] Generator")
    state_dir = os.path.join(BASE, "state")
    imports_dir = os.path.join(BASE, "imports")

    check("state/ exists", os.path.isdir(state_dir))
    state_files = sorted([f for f in os.listdir(state_dir) if f.endswith(".yaml") or f.endswith(".yml")])
    check("state has exactly 20 YAML files", len(state_files) == 20, f"found {len(state_files)}")

    check("imports/ exists", os.path.isdir(imports_dir))
    jira_path = os.path.join(imports_dir, "jira_export.csv")
    backlog_path = os.path.join(imports_dir, "backlog_export.xlsx")
    check("jira_export.csv exists", os.path.exists(jira_path))
    check("backlog_export.xlsx exists", os.path.exists(backlog_path))

    # Count CSV data rows (excluding header)
    with open(jira_path) as f:
        lines = f.readlines()
    jira_data_rows = len(lines) - 1  # minus header
    check("Jira CSV has 15 data rows", jira_data_rows == 15, f"found {jira_data_rows}")

    wb = load_workbook(backlog_path, read_only=True)
    ws = wb.active
    backlog_rows = sum(1 for _ in ws.iter_rows()) - 1  # minus header
    wb.close()
    check("Backlog XLSX has 7 data rows", backlog_rows == 7, f"found {backlog_rows}")

    # Verify portfolio content
    with open(os.path.join(state_dir, "ML-001.yaml")) as f:
        ml001 = yaml.safe_load(f)
    check("ML-001 title matches", ml001["title"] == "Autonomous fleet routing optimization")

    # --- Phase 2: Normalization ---
    print("\n[Phase 2] Normalization")
    proposals_dir = os.path.join(BASE, "proposals")

    jira_prop_path = os.path.join(proposals_dir, "jira_proposals.json")
    check("jira_proposals.json exists", os.path.exists(jira_prop_path))
    with open(jira_prop_path) as f:
        jira_props = json.load(f)
    check("Jira proposals count = 15", len(jira_props) == 15, f"found {len(jira_props)}")

    backlog_prop_path = os.path.join(proposals_dir, "backlog_proposals.json")
    check("backlog_proposals.json exists", os.path.exists(backlog_prop_path))
    with open(backlog_prop_path) as f:
        backlog_props = json.load(f)
    check("Backlog proposals count = 7", len(backlog_props) == 7, f"found {len(backlog_props)}")

    # Check refs
    jira_no_ref = [p for p in jira_props if not p["ref"]]
    check("No Jira proposal missing ref", len(jira_no_ref) == 0, f"found {len(jira_no_ref)}")
    backlog_with_ref = [p for p in backlog_props if p["ref"]]
    check("All Backlog proposals have empty ref", len(backlog_with_ref) == 0, f"found {len(backlog_with_ref)}")

    # --- Phase 3: Reconciliation ---
    print("\n[Phase 3] Reconciliation")
    recon_path = os.path.join(BASE, "reconcile.json")
    check("reconcile.json exists", os.path.exists(recon_path))
    with open(recon_path) as f:
        recon = json.load(f)

    summary = recon["summary"]
    buckets = summary["buckets"]
    results = recon["results"]

    check("Total proposals = 22", len(results) == 22, f"found {len(results)}")
    check("changed = 11", buckets.get("changed") == 11, f"found {buckets.get('changed')}")
    check("gap = 4", buckets.get("gap") == 4, f"found {buckets.get('gap')}")
    check("conflict = 2", buckets.get("conflict") == 2, f"found {buckets.get('conflict')}")
    check("ambiguous = 1", buckets.get("ambiguous") == 1, f"found {buckets.get('ambiguous')}")
    check("duplicate = 1", buckets.get("duplicate") == 1, f"found {buckets.get('duplicate')}")
    check("completed = 1", buckets.get("completed") == 1, f"found {buckets.get('completed')}")
    check("done_gap = 2", buckets.get("done_gap") == 2, f"found {buckets.get('done_gap')}")

    # Check ambiguous row
    amb = [r for r in results if r["bucket"] == "ambiguous"]
    check("Ambiguous row exists", len(amb) == 1)
    if amb:
        a = amb[0]
        check("Ambiguous title is 'Autonomous vehicle fleet navigation'",
              a["title"] == "Autonomous vehicle fleet navigation",
              f"got '{a['title']}'")
        check("Ambiguous target is ML-001",
              a["match_target"] == "ML-001",
              f"got '{a['match_target']}'")
        score = a["match_score"]
        check("Ambiguous score between 0.40 and 0.80",
              0.40 < score < 0.80,
              f"score={score}")

    # Check duplicate
    dup = [r for r in results if r["bucket"] == "duplicate"]
    check("Duplicate row exists", len(dup) == 1)
    if dup:
        d = dup[0]
        check("Duplicate title is 'Ops latency dashboard'",
              d["title"] == "Ops latency dashboard",
              f"got '{d['title']}'")
        check("Duplicate target is ML-005",
              d["match_target"] == "ML-005",
              f"got '{d['match_target']}'")

    # Check unconfirmed
    unconfirmed = summary.get("unconfirmed", [])
    expected_unconfirmed = ["ML-009", "ML-010", "ML-011", "ML-015", "ML-019", "ML-020"]
    check("Unconfirmed count = 6", len(unconfirmed) == 6, f"found {len(unconfirmed)}")
    check("Unconfirmed list exact",
          sorted(unconfirmed) == expected_unconfirmed,
          f"got {sorted(unconfirmed)}")

    # --- Phase 4: Semantic judgment ---
    print("\n[Phase 4] Semantic & Scoring")
    if amb:
        a = amb[0]
        verdict = a.get("semantic_verdict")
        reason = a.get("semantic_reason", "")

        if no_llm:
            check("Semantic verdict present (--no-llm)", verdict == "SKIPPED", f"got '{verdict}'")
            check("Semantic reason is non-empty", len(reason) > 0, f"reason='{reason}'")
            check("Bucket still 'ambiguous' after semantic pass", a["bucket"] == "ambiguous")
        else:
            check("Semantic verdict is SAME or DISTINCT",
                  verdict in ("SAME", "DISTINCT"),
                  f"got '{verdict}'")
            check("Semantic reason is non-empty", len(reason) > 0, f"reason='{reason}'")
            check("Bucket still 'ambiguous' after semantic pass", a["bucket"] == "ambiguous")

    # Check scoring
    score_path = os.path.join(BASE, "scores", "ML-001.json")
    if os.path.exists(score_path):
        with open(score_path) as f:
            score_data = json.load(f)
        factors = score_data["factors"]
        stored_score = score_data["wsjf_score"]
        recomputed = round(
            (factors["business_value"] + factors["time_criticality"] + factors["risk_reduction"])
            / factors["job_size"], 4
        )
        check("WSJF score recomputes exactly from stored factors",
              recomputed == stored_score,
              f"stored={stored_score}, recomputed={recomputed}")
    else:
        check("Scoring file exists", False, "scores/ML-001.json not found")

    # --- Phase 5: Export verification ---
    print("\n[Phase 5] Export")
    export_path = os.path.join(BASE, "exports", "meridian_reconciliation.xlsx")
    # We check the export endpoint was tested by verifying export file exists
    if os.path.exists(export_path):
        wb = load_workbook(export_path)
        sheets = wb.sheetnames
        check("Export has Cross-Source sheet", "Cross-Source" in sheets)
        check("Export has Source-Only sheet", "Source-Only" in sheets)
        check("Export has Unconfirmed sheet", "Unconfirmed" in sheets)
        check("Export has Semantic sheet", "Semantic" in sheets)

        cross_source = wb["Cross-Source"]
        cs_rows = sum(1 for _ in cross_source.iter_rows()) - 1
        check("Cross-Source has 15 rows", cs_rows == 15, f"found {cs_rows}")

        source_only = wb["Source-Only"]
        so_rows = sum(1 for _ in source_only.iter_rows()) - 1
        check("Source-Only has 6 rows (gap + done_gap)", so_rows == 6, f"found {so_rows}")

        unconf_sheet = wb["Unconfirmed"]
        uc_rows = sum(1 for _ in unconf_sheet.iter_rows()) - 1
        check("Unconfirmed has 6 rows", uc_rows == 6, f"found {uc_rows}")

        semantic_sheet = wb["Semantic"]
        sem_rows = sum(1 for _ in semantic_sheet.iter_rows()) - 1
        check("Semantic has 1 row", sem_rows == 1, f"found {sem_rows}")

        wb.close()

    # --- Summary ---
    print("\n" + "=" * 60)
    total = PASS + FAIL + SKIP
    print(f"Results: {PASS} PASS, {FAIL} FAIL, {SKIP} SKIP (of {total} checks)")
    if FAIL == 0:
        print("ALL PASS" + (" (with skips)" if SKIP > 0 else ""))
    else:
        print("SOME CHECKS FAILED")
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())