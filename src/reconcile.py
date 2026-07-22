"""Phase 3 -- Reconciliation.

Applies the matching and bucket rules to all proposals against the portfolio
and writes reconcile.json with every row's bucket, match target, and score,
plus a summary block. Pure deterministic code: identical input -> identical
byte output.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config
from .matching import overlap_coefficient
from .portfolio import load_portfolio_map

SOURCE_PRIORITY = {"jira": 0, "backlog": 1}


def load_proposals() -> list[dict[str, Any]]:
    """Load all proposal records, sorted for deterministic ordering."""
    props: list[dict[str, Any]] = []
    for path in sorted(config.PROPOSALS_DIR.glob("*/*.json")):
        with open(path) as fh:
            props.append(json.load(fh))
    props.sort(key=lambda p: (SOURCE_PRIORITY.get(p.get("source"), 9), p.get("seq", 0)))
    return props


def _best_title_match(title: str, portfolio: dict[str, dict]) -> tuple[str | None, float]:
    best_id: str | None = None
    best_score = 0.0
    for pid, pitem in portfolio.items():
        score = overlap_coefficient(title, pitem["title"])
        if score > best_score:
            best_score = score
            best_id = pid
    return best_id, best_score


def _build_rows(proposals: list[dict], portfolio: dict[str, dict]) -> list[dict]:
    """Compute each proposal's raw match (ref first, then title overlap)."""
    rows: list[dict] = []
    for prop in proposals:
        ref = prop.get("ref", "")
        title = prop["title"]
        status = prop["status"]

        best_id, best_score = _best_title_match(title, portfolio)
        best_score = round(best_score, 6)

        match_target: str | None = None
        score: float | None = best_score
        match_kind = "none"

        if ref:
            # A row with a ref is matched by ref only (regardless of title).
            if ref in portfolio:
                match_target = ref
                match_kind = "ref"
                score = round(overlap_coefficient(title, portfolio[ref]["title"]), 6)
            else:
                match_kind = "none"
                match_target = None
                score = best_score
        else:
            # A row with no ref is matched by title.
            if best_score >= config.HIGH:
                match_target = best_id
                match_kind = "title"
            elif best_score < config.LOW:
                match_kind = "none"
                match_target = None
            else:
                match_kind = "ambiguous"
                match_target = best_id  # best match, held for the model

        portfolio_title = portfolio[match_target]["title"] if match_target else None
        portfolio_status = portfolio[match_target]["status"] if match_target else None

        rows.append({
            "source": prop.get("source"),
            "seq": prop.get("seq"),
            "ref": ref,
            "title": title,
            "status": status,
            "bucket": None,  # assigned below
            "match_target": match_target,
            "match_kind": match_kind,
            "score": score,
            "portfolio_title": portfolio_title,
            "portfolio_status": portfolio_status,
        })
    return rows


def _assign_buckets(rows: list[dict]) -> None:
    """Resolve claims (ref first, then title >= HIGH) and assign buckets.

    A portfolio item is claimed by the first row that matches it (by ref or at
    >= HIGH). A later row whose best match is already claimed becomes a
    duplicate. Ambiguous rows (no ref, score strictly between LOW and HIGH)
    never claim and stay ambiguous.
    """
    # Claim order: ref matches first, then title matches, each in proposal order.
    claim_order = sorted(
        range(len(rows)),
        key=lambda i: (
            0 if rows[i]["match_kind"] == "ref" else 1,
            SOURCE_PRIORITY.get(rows[i]["source"], 9),
            rows[i]["seq"],
        ),
    )
    claimed: set[str] = set()
    for i in claim_order:
        r = rows[i]
        if r["match_kind"] in ("ref", "title"):
            tgt = r["match_target"]
            if tgt in claimed:
                r["bucket"] = "duplicate"
            else:
                claimed.add(tgt)

    for r in rows:
        if r["bucket"] is not None:
            continue  # already set (duplicate)
        kind = r["match_kind"]
        if kind == "ambiguous":
            r["bucket"] = "ambiguous"
            continue
        if kind == "none":
            r["bucket"] = "done_gap" if r["status"] == "done" else "gap"
            continue
        # Matched (ref or title) and the claim was won.
        pstatus = r["portfolio_status"]
        if pstatus == "done":
            r["bucket"] = "conflict" if r["status"] != "done" else "completed"
        else:
            if r["status"] != pstatus or r["title"] != r["portfolio_title"]:
                r["bucket"] = "changed"
            else:
                # Matched active row with no drift: aligned, nothing changed.
                r["bucket"] = "completed"


def _summary(rows: list[dict], portfolio: dict[str, dict]) -> dict:
    buckets = {b: 0 for b in config.BUCKETS}
    for r in rows:
        buckets[r["bucket"]] += 1
    claimed_ids = {r["match_target"] for r in rows if r["bucket"] in config.MATCHED_BUCKETS}
    # Ambiguous rows also reference a target but do not claim it.
    unconfirmed = sorted(pid for pid in portfolio if pid not in claimed_ids)
    return {
        "total": len(rows),
        "buckets": buckets,
        "unconfirmed": unconfirmed,
        "unconfirmed_count": len(unconfirmed),
    }


def reconcile(out_path: Path | None = None) -> dict:
    """Run reconciliation and write reconcile.json (or out_path). Returns data."""
    portfolio = load_portfolio_map()
    proposals = load_proposals()
    rows = _build_rows(proposals, portfolio)
    _assign_buckets(rows)
    summary = _summary(rows, portfolio)

    data = {"summary": summary, "rows": rows}
    # Stable row order: by source priority then seq (Jira 1-15, Backlog 1-7).
    rows.sort(key=lambda r: (SOURCE_PRIORITY.get(r["source"], 9), r["seq"]))

    target = out_path or config.RECONCILE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    target.write_text(text)
    return data


def load_reconcile() -> dict:
    if not config.RECONCILE_FILE.exists():
        return {"summary": {"total": 0, "buckets": {b: 0 for b in config.BUCKETS},
                            "unconfirmed": [], "unconfirmed_count": 0}, "rows": []}
    return json.loads(config.RECONCILE_FILE.read_text())


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--out" else None
    data = reconcile(out_path=out)
    s = data["summary"]
    print(f"Reconciled {s['total']} rows: {s['buckets']}")
    print(f"Unconfirmed: {s['unconfirmed_count']} -> {s['unconfirmed']}")
