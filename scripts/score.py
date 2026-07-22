#!/usr/bin/env python3
"""Phase 4 CLI: propose and store a WSJF score for one work item.

Asks the model for the four WSJF factors (unless --no-llm), computes the score
by pure arithmetic, and appends the record to reports/scores.json. Any stored
score is exactly recomputable from its stored factors.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meridian.config import SCORES_JSON, ensure_dirs  # noqa: E402
from meridian.portfolio import get_item  # noqa: E402
from meridian.scoring import score_item, compute_wsjf  # noqa: E402


def load_scores() -> List[Dict]:
    if SCORES_JSON.exists():
        with SCORES_JSON.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    return []


def save_scores(scores: List[Dict]) -> None:
    with SCORES_JSON.open("w", encoding="utf-8") as fh:
        json.dump(scores, fh, indent=2, sort_keys=True)
        fh.write("\n")


def upsert(scores: List[Dict], record: Dict) -> List[Dict]:
    """Replace an existing score for the same id, else append. Stable order."""
    out = [s for s in scores if s.get("id") != record["id"]]
    out.append(record)
    out.sort(key=lambda s: s.get("id", ""))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Propose and store a WSJF score.")
    parser.add_argument("item_id", help="Portfolio item id, e.g. ML-001")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip the model; use deterministic factors.")
    args = parser.parse_args()

    ensure_dirs()
    item = get_item(args.item_id)
    if item is None:
        print(f"score: no such item {args.item_id}", file=sys.stderr)
        return 1

    record = score_item(item, use_llm=not args.no_llm)

    # Self-check: recomputing from stored factors must reproduce the value.
    recomputed = compute_wsjf(record["factors"])
    assert recomputed == record["wsjf"], (
        f"recompute mismatch: {recomputed} != {record['wsjf']}"
    )

    scores = upsert(load_scores(), record)
    save_scores(scores)

    print(f"score: {record['id']} factors={record['factors']} "
          f"WSJF={record['wsjf']} ({record['factor_source']})")
    print("score: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
