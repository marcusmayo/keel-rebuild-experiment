"""Read and write the portfolio: one YAML file per work item in state/."""
from __future__ import annotations

from typing import Any

import yaml

from . import config


def load_portfolio() -> list[dict[str, Any]]:
    """Load every portfolio item, sorted by id for deterministic ordering."""
    items: list[dict[str, Any]] = []
    for path in sorted(config.STATE_DIR.glob("*.yaml")):
        with open(path) as fh:
            items.append(yaml.safe_load(fh))
    items.sort(key=lambda it: it["id"])
    return items


def load_portfolio_map() -> dict[str, dict[str, Any]]:
    """Map of portfolio id -> item."""
    return {it["id"]: it for it in load_portfolio()}


def save_item(item: dict[str, Any]) -> None:
    """Persist a single work item to state/<id>.yaml.

    Only used by the web app's confirm step after an operator explicitly
    confirms a status change. Writes/updates only; the record system is
    append/update only.
    """
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.STATE_DIR / f"{item['id']}.yaml"
    with open(path, "w") as fh:
        yaml.safe_dump(item, fh, sort_keys=False, default_flow_style=False, allow_unicode=True)
