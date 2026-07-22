"""Phase 1 -- generate the exact seeded world from the AGENTS.md data appendix.

Writes 20 portfolio YAML files into state/, one Jira CSV (15 data rows) and
one backlog XLSX (7 data rows) into imports/. This script embeds the data
appendix verbatim and invents nothing.
"""
import csv
import os

import yaml
from openpyxl import Workbook

from common import STATE_DIR, IMPORTS_DIR

PORTFOLIO = [
    ("ML-001", "Autonomous fleet routing optimization", "in_progress"),
    ("ML-002", "Driver scheduling engine", "in_progress"),
    ("ML-003", "Warehouse slotting analytics", "in_progress"),
    ("ML-004", "Cold chain temperature monitoring", "in_progress"),
    ("ML-005", "Ops latency dashboard rollout", "in_progress"),
    ("ML-006", "Customs paperwork automation", "in_progress"),
    ("ML-007", "Carrier rate benchmarking", "in_progress"),
    ("ML-008", "Dock door scheduling", "in_progress"),
    ("ML-009", "Fuel consumption reporting", "in_progress"),
    ("ML-010", "Returns processing portal", "in_progress"),
    ("ML-011", "Vendor onboarding checklist", "in_progress"),
    ("ML-012", "Route deviation alerts", "in_progress"),
    ("ML-013", "Pallet tracking tags", "in_progress"),
    ("ML-014", "Invoice dispute workflow", "in_progress"),
    ("ML-015", "Safety incident register", "in_progress"),
    ("ML-016", "Legacy TMS migration", "done"),
    ("ML-017", "Depot wifi upgrade", "done"),
    ("ML-018", "Contract renewal archive", "done"),
    ("ML-019", "Driver fatigue study", "in_progress"),
    ("ML-020", "Packaging waste audit", "in_progress"),
]

JIRA_ROWS = [
    ("ML-001", "Autonomous fleet routing optimization", "blocked"),
    ("ML-002", "Driver scheduling engine", "done"),
    ("ML-003", "Warehouse slotting analytics", "blocked"),
    ("ML-004", "Cold chain temperature monitoring", "done"),
    ("ML-005", "Ops latency dashboard rollout", "blocked"),
    ("ML-006", "Customs paperwork automation", "done"),
    ("ML-007", "Carrier rate benchmark refresh", "in_progress"),
    ("ML-008", "Dock door scheduling v2", "in_progress"),
    ("ML-016", "Legacy TMS migration", "in_progress"),
    ("ML-017", "Depot wifi upgrade", "in_progress"),
    ("ML-018", "Contract renewal archive", "done"),
    ("ML-021", "Telematics data lake", "done"),
    ("ML-022", "EDI partner certification", "done"),
    ("ML-023", "Yard congestion heatmap", "in_progress"),
    ("ML-024", "Reverse logistics pilot", "in_progress"),
]

BACKLOG_ROWS = [
    ("Route deviation alerts", "blocked"),
    ("Pallet tracking tags", "done"),
    ("Invoice dispute workflow", "blocked"),
    ("Ops latency dashboard", "in_progress"),
    ("Autonomous vehicle fleet navigation", "in_progress"),
    ("Quarterly fuel hedging review", "in_progress"),
    ("Trailer telematics retrofit", "in_progress"),
]


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(IMPORTS_DIR, exist_ok=True)

    for item_id, title, status in PORTFOLIO:
        path = os.path.join(STATE_DIR, f"{item_id}.yaml")
        with open(path, "w") as f:
            yaml.safe_dump({"id": item_id, "title": title, "status": status},
                           f, sort_keys=False)

    csv_path = os.path.join(IMPORTS_DIR, "jira_export.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ref", "title", "status"])
        w.writerows(JIRA_ROWS)

    xlsx_path = os.path.join(IMPORTS_DIR, "backlog_export.xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = "Backlog"
    ws.append(["title", "status"])
    for row in BACKLOG_ROWS:
        ws.append(list(row))
    wb.save(xlsx_path)

    print(f"Wrote {len(PORTFOLIO)} portfolio items to state/")
    print(f"Wrote {len(JIRA_ROWS)} Jira rows to {csv_path}")
    print(f"Wrote {len(BACKLOG_ROWS)} backlog rows to {xlsx_path}")


if __name__ == "__main__":
    main()
