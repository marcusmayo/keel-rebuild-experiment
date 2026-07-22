"""Phase 3 -- reconcile all proposals against the portfolio.

Applies the matching and bucket rules from AGENTS.md and writes
reconcile.json. Pure deterministic code: identical input -> identical
bytes. Never writes to state/.
"""
import argparse
import json
import os

from common import (BUCKET_ORDER, HIGH, LOW, PROPOSALS_DIR, RECONCILE_PATH,
                    load_portfolio, overlap)


def best_title_match(title, portfolio):
    """Best overlap score of title against all portfolio titles.

    Returns (best_id, best_score). Ties break by lowest id for
    determinism.
    """
    best_id, best_score = None, -1.0
    for pid, item in portfolio.items():
        s = overlap(title, item["title"])
        if s > best_score:
            best_id, best_score = pid, s
    return best_id, best_score


def reconcile(portfolio, proposals):
    claims = set()  # portfolio ids claimed by a matched source row
    rows = []
    for p in proposals:
        ref, title, status = p["ref"], p["title"], p["status"]
        target, score, matched = None, 0.0, False
        ambiguous = False

        if ref and ref in portfolio:
            # Ref match wins regardless of title.
            target = ref
            score = overlap(title, portfolio[ref]["title"])
            matched = True
        else:
            best_id, best_score = best_title_match(title, portfolio)
            target, score = best_id, best_score
            if best_score >= HIGH:
                matched = True
            elif best_score >= LOW:
                ambiguous = True

        if matched:
            item = portfolio[target]
            if target in claims:
                bucket = "duplicate"
            else:
                claims.add(target)
                if item["status"] == "done":
                    bucket = "completed" if status == "done" else "conflict"
                elif status != item["status"] or title != item["title"]:
                    bucket = "changed"
                else:
                    bucket = "completed"
        elif ambiguous:
            bucket = "ambiguous"  # held for the model, never moved
        else:
            target = None
            bucket = "done_gap" if status == "done" else "gap"

        rows.append({
            "ref": ref,
            "title": title,
            "status": status,
            "source": p["source"],
            "bucket": bucket,
            "match": target,
            "score": round(score, 4),
        })

    unconfirmed = [pid for pid in portfolio if pid not in claims]
    summary = {"buckets": {b: sum(1 for r in rows if r["bucket"] == b)
                           for b in BUCKET_ORDER},
               "total": len(rows),
               "unconfirmed": unconfirmed}
    return {"summary": summary, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=RECONCILE_PATH)
    args = ap.parse_args()

    portfolio = load_portfolio()
    proposals = []
    for name in ("jira.json", "backlog.json"):
        with open(os.path.join(PROPOSALS_DIR, name)) as f:
            proposals.extend(json.load(f))

    result = reconcile(portfolio, proposals)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    s = result["summary"]
    print(f"Wrote {args.out}: " +
          " ".join(f"{k} {v}" for k, v in s["buckets"].items()) +
          f" | unconfirmed {len(s['unconfirmed'])}")


if __name__ == "__main__":
    main()
