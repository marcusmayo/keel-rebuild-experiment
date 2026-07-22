#!/usr/bin/env python3
"""Phase 1 generator: write the exact seeded world.

Writes 20 portfolio YAML files into state/, a 15-row Jira CSV and a 7-row
backlog XLSX into imports/. Embeds the data appendix verbatim; invents nothing.
Deterministic and idempotent -- running twice yields identical files.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

# Allow running as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from meridian.config import STATE_DIR, IMPORTS_DIR, JIRA_CSV, BACKLOG_XLSX  # noqa: E402
from meridian.data_appendix import PORTFOLIO, JIRA_ROWS, BACKLOG_ROWS  # noqa: E402


def write_portfolio() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for item_id, title, status in PORTFOLIO:
        payload = {"id": item_id, "title": title, "status": status}
        path = STATE_DIR / f"{item_id}.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(payload, fh, sort_keys=True, default_flow_style=False)
    return len(PORTFOLIO)


def write_jira_csv() -> int:
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with JIRA_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ref", "title", "status"])
        for ref, title, status in JIRA_ROWS:
            writer.writerow([ref, title, status])
    return len(JIRA_ROWS)


def write_backlog_xlsx() -> int:
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "backlog"
    ws.append(["title", "status"])
    for title, status in BACKLOG_ROWS:
        ws.append([title, status])
    wb.save(BACKLOG_XLSX)
    return len(BACKLOG_ROWS)


def main() -> int:
    n_port = write_portfolio()
    n_jira = write_jira_csv()
    n_backlog = write_backlog_xlsx()
    print(f"Wrote {n_port} portfolio items -> {STATE_DIR}")
    print(f"Wrote Jira CSV with {n_jira} data rows -> {JIRA_CSV}")
    print(f"Wrote backlog XLSX with {n_backlog} data rows -> {BACKLOG_XLSX}")
    print("generate: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
