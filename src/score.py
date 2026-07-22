"""Phase 4 -- WSJF scoring.

Asks the model to propose WSJF factors (business_value, time_criticality,
risk_reduction, job_size, each 1-10) for a chosen item, then computes
WSJF = (business_value + time_criticality + risk_reduction) / job_size in
plain arithmetic and stores factors and score together. With --no-llm, uses
deterministic default factors and makes no network call.
"""
from __future__ import annotations

import json
import re
import sys

from . import config
from .llm import chat

FACTORS = ["business_value", "time_criticality", "risk_reduction", "job_size"]
DEFAULT_FACTORS = {k: 5 for k in FACTORS}

_FACTOR_RUN_RE = re.compile(r"(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)")


def compute_wsjf(factors: dict) -> float:
    return (factors["business_value"] + factors["time_criticality"]
            + factors["risk_reduction"]) / factors["job_size"]


def _parse_factors(text: str) -> dict | None:
    m = _FACTOR_RUN_RE.search(text)
    if not m:
        return None
    nums = [max(1, min(10, int(x))) for x in m.groups()]
    return {FACTORS[i]: nums[i] for i in range(4)}


def _propose_factors(item_id: str) -> dict:
    prompt = (
        f"Propose WSJF factors for the work item with id {item_id}.\n"
        "Respond with exactly four integers from 1 to 10, in this order, "
        "comma-separated:\n"
        "business_value, time_criticality, risk_reduction, job_size\n"
        "Reply with only the four numbers and nothing else."
    )
    try:
        content = chat([{"role": "user", "content": prompt}], max_tokens=1024, temperature=0.0)
    except Exception as exc:  # noqa: BLE001 - deterministic fallback
        print(f"[score] model unavailable ({exc.__class__.__name__}); using defaults.")
        return dict(DEFAULT_FACTORS)
    factors = _parse_factors(content)
    if factors is None:
        print(f"[score] could not parse factors from: {content!r}; using defaults.")
        return dict(DEFAULT_FACTORS)
    return factors


def score_item(item_id: str, no_llm: bool = False) -> dict:
    if no_llm:
        factors = dict(DEFAULT_FACTORS)
    else:
        factors = _propose_factors(item_id)
    wsjf = compute_wsjf(factors)
    record = {"item": item_id, "factors": factors, "wsjf": wsjf}
    config.SCORES_DIR.mkdir(parents=True, exist_ok=True)
    (config.SCORES_DIR / f"{item_id}.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )
    return record


def _parse_args(argv: list[str]) -> tuple[str, bool]:
    item_id = "ML-009"
    no_llm = False
    for i, arg in enumerate(argv):
        if arg == "--item":
            item_id = argv[i + 1]
        elif arg == "--no-llm":
            no_llm = True
    return item_id, no_llm


if __name__ == "__main__":
    item_id, no_llm = _parse_args(sys.argv[1:])
    rec = score_item(item_id, no_llm=no_llm)
    print(f"Scored {rec['item']}: factors={rec['factors']} wsjf={rec['wsjf']:.6f} (no-llm={no_llm})")
