#!/usr/bin/env python3
"""Phase 4 CLI: run the semantic pass over the ambiguous bucket.

Reads reports/reconcile.json, sends ONLY the ambiguous rows to the model
(unless --no-llm), annotates each verdict in place, and writes the file back.
Buckets are never changed; non-ambiguous rows are never touched.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meridian.config import RECONCILE_JSON  # noqa: E402
from meridian.semantic import run_semantic_pass  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantic judgment pass.")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip the model; run deterministically.")
    args = parser.parse_args()

    with RECONCILE_JSON.open("r", encoding="utf-8") as fh:
        report = json.load(fh)

    run_semantic_pass(report, use_llm=not args.no_llm)

    with RECONCILE_JSON.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")

    sem = report["summary"]["semantic"]
    if args.no_llm:
        print(f"semantic: skipped model (--no-llm); "
              f"{sem['ambiguous_count']} ambiguous row(s) left unjudged")
    else:
        print(f"semantic: judged {sem['judged']}/{sem['ambiguous_count']} "
              "ambiguous row(s)")
        for r in report["rows"]:
            if r["bucket"] == "ambiguous" and "semantic" in r:
                print(f"  - {r['title']!r} -> {r['semantic']['verdict']}: "
                      f"{r['semantic']['reason']}")
    print("semantic: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
