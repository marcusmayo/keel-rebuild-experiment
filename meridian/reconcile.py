"""Phase 3 reconciliation engine (pure deterministic code).

Applies the matching and bucket rules to all proposals against the portfolio
and produces a fully deterministic reconciliation structure. No AI here.

Matching:
  - A row is matched by ref first: if its ref equals a portfolio item's id,
    they match regardless of title.
  - A row with no ref is matched by title: best overlap against all portfolio
    titles. score >= HIGH is a match; score < LOW is no match; in between is
    held as ambiguous.

Buckets (each source row lands in exactly one):
  - changed:   matched, portfolio status not done, and row status or title
               differs from the portfolio.
  - conflict:  matched, portfolio status IS done, and row says work is active.
  - completed: matched, both sides done, nothing drifted.
  - duplicate: the row's best match is a portfolio item already claimed by
               another source row (by ref or at >= HIGH).
  - ambiguous: no ref, best score strictly between LOW and HIGH.
  - gap:       matches nothing, row is active.
  - done_gap:  matches nothing, row is done.

Portfolio items no source row claims are "unconfirmed" (a report view).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .config import HIGH, LOW, DONE_STATUSES
from .matching import best_title_match, overlap_coefficient


def _is_done(status: str) -> bool:
    return (status or "").strip().lower() in DONE_STATUSES


def _round_score(score: float) -> float:
    """Round scores to a stable precision for byte-identical output."""
    return round(float(score), 6)


def reconcile(proposals: List[Dict], portfolio: List[Dict]) -> Dict:
    """Reconcile proposals against portfolio; return the full report dict.

    Rows are processed in a deterministic order: jira source before backlog,
    then by input order within each source. This ordering matters only for the
    duplicate rule (first claimant of a portfolio item wins; later claimants of
    the same item become duplicates).
    """
    portfolio_by_id = {it["id"]: it for it in portfolio}

    # Stable processing order: jira first, then backlog, preserving input order.
    def sort_key(entry):
        idx, row = entry
        src_rank = 0 if row.get("source") == "jira" else 1
        return (src_rank, idx)

    ordered = [row for _, row in sorted(enumerate(proposals), key=sort_key)]

    # Track which portfolio ids have been claimed, and by which row index.
    claimed: Dict[str, int] = {}

    rows: List[Dict] = []

    for row in ordered:
        ref = (row.get("ref") or "").strip()
        title = row.get("title") or ""
        status = row.get("status") or ""
        source = row.get("source") or ""

        result: Dict = {
            "ref": ref,
            "title": title,
            "status": status,
            "source": source,
            "target": None,
            "score": None,
            "match_type": None,  # "ref" | "title" | None
            "bucket": None,
        }

        target: Optional[str] = None
        match_type: Optional[str] = None
        score: Optional[float] = None

        # --- Matching: ref first ---
        if ref and ref in portfolio_by_id:
            target = ref
            match_type = "ref"
            # Score is the title overlap against the matched item (informative).
            score = _round_score(
                overlap_coefficient(title, portfolio_by_id[ref]["title"])
            )
        else:
            # Title matching for rows without a resolvable ref.
            best_id, best_score = best_title_match(title, portfolio)
            score = _round_score(best_score)
            if best_score >= HIGH:
                target = best_id
                match_type = "title"
            elif best_score < LOW:
                target = None
                match_type = None
            else:
                # Ambiguous: held for the model. Record the best candidate as
                # the target so the operator can see the near-match, but the
                # bucket is ambiguous and never moved elsewhere.
                target = best_id
                match_type = None
                result["target"] = best_id
                result["score"] = score
                result["match_type"] = None
                result["bucket"] = "ambiguous"
                rows.append(result)
                continue

        result["target"] = target
        result["score"] = score
        result["match_type"] = match_type

        # --- Bucketing ---
        if target is None:
            # Matches nothing.
            result["bucket"] = "done_gap" if _is_done(status) else "gap"
            rows.append(result)
            continue

        # Matched to a portfolio item. Check duplicate first: is the target
        # already claimed by an earlier row?
        if target in claimed:
            result["bucket"] = "duplicate"
            rows.append(result)
            continue

        # This row is the first claimant of the target.
        claimed[target] = len(rows)

        port_item = portfolio_by_id[target]
        port_done = _is_done(port_item["status"])
        row_done = _is_done(status)

        if port_done:
            if not row_done:
                # Portfolio says done, source says still active.
                result["bucket"] = "conflict"
            else:
                # Both done, nothing drifted.
                result["bucket"] = "completed"
        else:
            # Portfolio not done. changed if status or title differs from the
            # portfolio; otherwise the match is fully in sync (completed-style).
            title_differs = (title.strip() != port_item["title"].strip())
            status_differs = (status.strip() != port_item["status"].strip())
            if status_differs or title_differs:
                result["bucket"] = "changed"
            else:
                result["bucket"] = "completed"

        rows.append(result)

    # --- Unconfirmed portfolio items: claimed by no source row ---
    unconfirmed = sorted(
        item["id"] for item in portfolio if item["id"] not in claimed
    )

    # --- Summary counts ---
    bucket_order = [
        "changed",
        "gap",
        "conflict",
        "ambiguous",
        "duplicate",
        "completed",
        "done_gap",
    ]
    counts = {b: 0 for b in bucket_order}
    for r in rows:
        counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1

    # Re-sort rows for stable, human-readable output: by source, then ref,
    # then title. This does not affect bucketing (already decided above).
    rows_sorted = sorted(
        rows, key=lambda r: (r["source"], r["ref"], r["title"])
    )

    report = {
        "summary": {
            "buckets": counts,
            "total": len(rows),
            "unconfirmed": unconfirmed,
            "unconfirmed_count": len(unconfirmed),
            "portfolio_count": len(portfolio),
            "thresholds": {"HIGH": HIGH, "LOW": LOW},
        },
        "rows": rows_sorted,
    }
    return report
