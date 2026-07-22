"""Phase 1 -- Foundation and the seeded world.

Writes the exact portfolio and exports from the data appendix in AGENTS.md.
The data is embedded verbatim; the generator invents nothing.
"""
from __future__ import annotations

import csv

from openpyxl import Workbook

from . import config
from .portfolio import save_item

# Portfolio: state/, one YAML per item. Fields: id, title, status.
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

# Jira CSV: imports/, columns ref,title,status. 15 data rows.
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

# Backlog XLSX: imports/, columns title,status. 7 data rows, no refs.
BACKLOG_ROWS = [
    ("Route deviation alerts", "blocked"),
    ("Pallet tracking tags", "done"),
    ("Invoice dispute workflow", "blocked"),
    ("Ops latency dashboard", "in_progress"),
    ("Autonomous vehicle fleet navigation", "in_progress"),
    ("Quarterly fuel hedging review", "in_progress"),
    ("Trailer telematics retrofit", "in_progress"),
]

JIRA_CSV = config.IMPORTS_DIR / "jira_export.csv"
BACKLOG_XLSX = config.IMPORTS_DIR / "backlog_export.xlsx"


def generate() -> dict:
    """Write the seeded portfolio and the two exports."""
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.IMPORTS_DIR.mkdir(parents=True, exist_ok=True)

    for item_id, title, status in PORTFOLIO:
        save_item({"id": item_id, "title": title, "status": status})

    with open(JIRA_CSV, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ref", "title", "status"])
        for ref, title, status in JIRA_ROWS:
            writer.writerow([ref, title, status])

    wb = Workbook()
    ws = wb.active
    ws.title = "Backlog"
    ws.append(["title", "status"])
    for title, status in BACKLOG_ROWS:
        ws.append([title, status])
    wb.save(BACKLOG_XLSX)

    return {
        "portfolio_items": len(PORTFOLIO),
        "jira_rows": len(JIRA_ROWS),
        "backlog_rows": len(BACKLOG_ROWS),
    }


if __name__ == "__main__":
    result = generate()
    print(f"Generated {result['portfolio_items']} portfolio items, "
          f"{result['jira_rows']} Jira rows, {result['backlog_rows']} backlog rows.")
