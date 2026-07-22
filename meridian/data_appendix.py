"""The exact seeded world from the AGENTS.md data appendix, verbatim.

This module is the single source of truth for the generator. It invents
nothing; the numbers here are the numbers in the brief.
"""
from __future__ import annotations

from typing import List, Tuple

# Portfolio: (id, title, status) -- 20 items.
PORTFOLIO: List[Tuple[str, str, str]] = [
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

# Jira CSV: (ref, title, status) -- 15 data rows.
JIRA_ROWS: List[Tuple[str, str, str]] = [
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

# Backlog XLSX: (title, status) -- 7 data rows, no refs.
BACKLOG_ROWS: List[Tuple[str, str]] = [
    ("Route deviation alerts", "blocked"),
    ("Pallet tracking tags", "done"),
    ("Invoice dispute workflow", "blocked"),
    ("Ops latency dashboard", "in_progress"),
    ("Autonomous vehicle fleet navigation", "in_progress"),
    ("Quarterly fuel hedging review", "in_progress"),
    ("Trailer telematics retrofit", "in_progress"),
]
