#!/usr/bin/env python3
"""Phase 3 CLI: reconcile all proposals against the portfolio.

Reads proposals/ and state/, writes reports/reconcile.json with every row's
bucket, match target, and score, plus a summary block. Fully deterministic:
running twice produces byte-identical output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meridian.config import (  # noqa: E402
    JIRA_PROPOSALS,
    BACKLOG_PROPOSALS,
    RECONCILE_JSON,
    ensure_dirs,
)
from meridian.portfolio import load_portfolio  # noqa: E402
from meridian.reconcile import reconcile  # noqa: E402


def load_proposals() -> List[Dict]:
    proposals: List[Dict] = []
    for path in (JIRA_PROPOSALS, BACKLOG_PROPOSALS):
        with path.open("r", encoding="utf-8") as fh:
            proposals.extend(json.load(fh))
    return proposals


def write_report(report: Dict) -> None:
    with RECONCILE_JSON.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main() -> int:
    ensure_dirs()
    proposals = load_proposals()
    portfolio = load_portfolio()
    report = reconcile(proposals, portfolio)
    write_report(report)

    counts = report["summary"]["buckets"]
    print(f"Reconciled {report['summary']['total']} rows -> {RECONCILE_JSON}")
    order = ["changed", "gap", "conflict", "ambiguous", "duplicate",
             "completed", "done_gap"]
    print("Buckets: " + "  ".join(f"{b} {counts.get(b, 0)}" for b in order))
    print(f"Unconfirmed: {report['summary']['unconfirmed_count']} "
          f"{report['summary']['unconfirmed']}")
    print("reconcile: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
