"""Phase 4 -- Semantic judgment.

Sends ONLY the ambiguous rows to the model asking SAME or DISTINCT with a
one-sentence reason, and annotates the verdict into reconcile.json in place.
The bucket is never changed. With --no-llm, runs to completion with no
network call (verdict left unset; the oracle marks these checks skipped).
"""
from __future__ import annotations

import json

from . import config
from .llm import judge_same_distinct


def run_semantic(no_llm: bool = False) -> int:
    if not config.RECONCILE_FILE.exists():
        print("reconcile.json not found; nothing to judge.")
        return 0

    data = json.loads(config.RECONCILE_FILE.read_text())
    rows = data.get("rows", [])
    judged = 0

    for row in rows:
        if row.get("bucket") != "ambiguous":
            continue
        if no_llm:
            row["semantic"] = {"verdict": None, "reason": None, "judged": False}
            print(f"[no-llm] ambiguous row '{row['title']}' left unjudged.")
            continue
        verdict, reason = judge_same_distinct(row["title"], row.get("portfolio_title") or "")
        row["semantic"] = {"verdict": verdict, "reason": reason, "judged": True}
        judged += 1
        print(f"Judged '{row['title']}' vs '{row.get('portfolio_title')}': {verdict}")

    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    config.RECONCILE_FILE.write_text(text)
    return judged


if __name__ == "__main__":
    import sys
    no_llm = "--no-llm" in sys.argv
    n = run_semantic(no_llm=no_llm)
    print(f"Semantic pass complete. Judged {n} ambiguous rows. (no-llm={no_llm})")
