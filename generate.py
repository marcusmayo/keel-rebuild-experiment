#!/usr/bin/env python3
"""Phase 1: Generate the seeded world — 20 portfolio YAMLs, 1 Jira CSV, 1 Backlog XLSX."""

import os
import csv
import yaml
from openpyxl import Workbook

BASE = os.path.dirname(os.path.abspath(__file__))

# --- Data appendix (verbatim from AGENTS.md) ---

PORTFOLIO = [
    ("ML-001", "Autonomous fleet routing optimization",   "in_progress"),
    ("ML-002", "Driver scheduling engine",                "in_progress"),
    ("ML-003", "Warehouse slotting analytics",            "in_progress"),
    ("ML-004", "Cold chain temperature monitoring",       "in_progress"),
    ("ML-005", "Ops latency dashboard rollout",           "in_progress"),
    ("ML-006", "Customs paperwork automation",            "in_progress"),
    ("ML-007", "Carrier rate benchmarking",               "in_progress"),
    ("ML-008", "Dock door scheduling",                    "in_progress"),
    ("ML-009", "Fuel consumption reporting",              "in_progress"),
    ("ML-010", "Returns processing portal",               "in_progress"),
    ("ML-011", "Vendor onboarding checklist",             "in_progress"),
    ("ML-012", "Route deviation alerts",                  "in_progress"),
    ("ML-013", "Pallet tracking tags",                    "in_progress"),
    ("ML-014", "Invoice dispute workflow",                "in_progress"),
    ("ML-015", "Safety incident register",                "in_progress"),
    ("ML-016", "Legacy TMS migration",                    "done"),
    ("ML-017", "Depot wifi upgrade",                      "done"),
    ("ML-018", "Contract renewal archive",                "done"),
    ("ML-019", "Driver fatigue study",                    "in_progress"),
    ("ML-020", "Packaging waste audit",                   "in_progress"),
]

JIRA = [
    ("ML-001", "Autonomous fleet routing optimization",   "blocked"),
    ("ML-002", "Driver scheduling engine",                "done"),
    ("ML-003", "Warehouse slotting analytics",            "blocked"),
    ("ML-004", "Cold chain temperature monitoring",       "done"),
    ("ML-005", "Ops latency dashboard rollout",           "blocked"),
    ("ML-006", "Customs paperwork automation",            "done"),
    ("ML-007", "Carrier rate benchmark refresh",          "in_progress"),
    ("ML-008", "Dock door scheduling v2",                 "in_progress"),
    ("ML-016", "Legacy TMS migration",                    "in_progress"),
    ("ML-017", "Depot wifi upgrade",                      "in_progress"),
    ("ML-018", "Contract renewal archive",                "done"),
    ("ML-021", "Telematics data lake",                    "done"),
    ("ML-022", "EDI partner certification",               "done"),
    ("ML-023", "Yard congestion heatmap",                 "in_progress"),
    ("ML-024", "Reverse logistics pilot",                 "in_progress"),
]

BACKLOG = [
    ("Route deviation alerts",                  "blocked"),
    ("Pallet tracking tags",                    "done"),
    ("Invoice dispute workflow",                "blocked"),
    ("Ops latency dashboard",                   "in_progress"),
    ("Autonomous vehicle fleet navigation",     "in_progress"),
    ("Quarterly fuel hedging review",           "in_progress"),
    ("Trailer telematics retrofit",             "in_progress"),
]


def main():
    # --- Portfolio YAMLs ---
    state_dir = os.path.join(BASE, "state")
    os.makedirs(state_dir, exist_ok=True)
    for item_id, title, status in PORTFOLIO:
        path = os.path.join(state_dir, f"{item_id}.yaml")
        with open(path, "w") as f:
            yaml.dump({"id": item_id, "title": title, "status": status}, f)
    print(f"Wrote {len(PORTFOLIO)} portfolio items to state/")

    # --- Jira CSV ---
    imports_dir = os.path.join(BASE, "imports")
    os.makedirs(imports_dir, exist_ok=True)
    jira_path = os.path.join(imports_dir, "jira_export.csv")
    with open(jira_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ref", "title", "status"])
        for row in JIRA:
            writer.writerow(row)
    print(f"Wrote {len(JIRA)} Jira rows to imports/jira_export.csv")

    # --- Backlog XLSX ---
    backlog_path = os.path.join(imports_dir, "backlog_export.xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = "Backlog"
    ws.append(["title", "status"])
    for row in BACKLOG:
        ws.append(list(row))
    wb.save(backlog_path)
    print(f"Wrote {len(BACKLOG)} Backlog rows to imports/backlog_export.xlsx")


if __name__ == "__main__":
    main()
