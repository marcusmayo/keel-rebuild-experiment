#!/usr/bin/env python3
"""Phase 2: Normalize Jira CSV and Backlog XLSX into canonical proposal records."""
import os
import csv
import json
from openpyxl import load_workbook

PROPOSALS_DIR = "proposals"
IMPORTS_DIR = "imports"


def normalize_jira():
    """Read jira_export.csv, write one proposal JSON per row."""
    jira_path = os.path.join(IMPORTS_DIR, "jira_export.csv")
    proposals = []
    with open(jira_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            proposals.append({
                "ref": row.get("ref", "").strip(),
                "title": row.get("title", "").strip(),
                "status": row.get("status", "").strip(),
                "source": "jira",
            })
    return proposals


def normalize_backlog():
    """Read backlog_export.xlsx, write one proposal JSON per row."""
    backlog_path = os.path.join(IMPORTS_DIR, "backlog_export.xlsx")
    wb = load_workbook(backlog_path)
    ws = wb.active
    proposals = []
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    for row in ws.iter_rows(min_row=2, values_only=True):
        record = dict(zip(headers, row))
        proposals.append({
            "ref": "",
            "title": record.get("title", "").strip(),
            "status": record.get("status", "").strip(),
            "source": "backlog",
        })
    return proposals


def normalize():
    os.makedirs(PROPOSALS_DIR, exist_ok=True)

    jira_proposals = normalize_jira()
    backlog_proposals = normalize_backlog()

    for i, p in enumerate(jira_proposals):
        path = os.path.join(PROPOSALS_DIR, f"jira_{i:03d}.json")
        with open(path, "w") as f:
            json.dump(p, f, indent=2)

    for i, p in enumerate(backlog_proposals):
        path = os.path.join(PROPOSALS_DIR, f"backlog_{i:03d}.json")
        with open(path, "w") as f:
            json.dump(p, f, indent=2)

    print(f"Normalized {len(jira_proposals)} Jira proposals and {len(backlog_proposals)} backlog proposals into {PROPOSALS_DIR}/")


if __name__ == "__main__":
    normalize()