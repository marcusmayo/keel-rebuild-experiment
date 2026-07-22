"""Read and update the portfolio: one YAML file per work item in state/.

The portfolio is intentionally a folder of human-readable YAML files (no
SQLite). Reads are used everywhere; the only write path is a guarded status
update used by the propose-then-confirm operator flow. There is NO delete.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .config import STATE_DIR


def _item_path(item_id: str) -> Path:
    return STATE_DIR / f"{item_id}.yaml"


def load_portfolio() -> List[Dict]:
    """Load all portfolio items sorted by id. Each dict has id/title/status."""
    items: List[Dict] = []
    if not STATE_DIR.exists():
        return items
    for path in sorted(STATE_DIR.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        items.append(
            {
                "id": str(data.get("id", path.stem)),
                "title": str(data.get("title", "")),
                "status": str(data.get("status", "")),
            }
        )
    items.sort(key=lambda it: it["id"])
    return items


def get_item(item_id: str) -> Optional[Dict]:
    """Return one portfolio item by id, or None if it does not exist."""
    path = _item_path(item_id)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {
        "id": str(data.get("id", item_id)),
        "title": str(data.get("title", "")),
        "status": str(data.get("status", "")),
    }


def write_item(item_id: str, title: str, status: str) -> None:
    """Write (create/overwrite) a single work item YAML. Never deletes."""
    path = _item_path(item_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"id": item_id, "title": title, "status": status}
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=True, default_flow_style=False)


def update_status(item_id: str, new_status: str) -> Dict:
    """Apply a status change to an existing item and return the updated item.

    Preserves id and title. Raises KeyError if the item does not exist. This
    is the only sanctioned mutation of the portfolio, invoked exclusively by
    the operator confirm step.
    """
    item = get_item(item_id)
    if item is None:
        raise KeyError(item_id)
    write_item(item_id, item["title"], new_status)
    return {"id": item_id, "title": item["title"], "status": new_status}
