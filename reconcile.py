#!/usr/bin/env python3
"""Phase 3: Reconciliation — match proposals to portfolio and bucket them."""
import os
import re
import json
import yaml

STATE_DIR = "state"
PROPOSALS_DIR = "proposals"
HIGH = 0.80
LOW = 0.40
ACTIVE_STATUSES = {"in_progress", "blocked", "todo", "open", "in progress"}
DONE_STATUSES = {"done", "completed", "closed", "resolved"}


def tokenize(title):
    """Lowercase, split on whitespace, strip punctuation. No stemming."""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    return set(title.split())


def overlap_coeff(title_a, title_b):
    """Overlap coefficient: |A ∩ B| / min(|A|, |B|)."""
    tokens_a = tokenize(title_a)
    tokens_b = tokenize(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / min(len(tokens_a), len(tokens_b))


def is_done(status):
    return status.lower().strip() in DONE_STATUSES


def is_active(status):
    return status.lower().strip() in ACTIVE_STATUSES


def load_portfolio():
    """Load all portfolio items from state/ directory."""
    items = {}
    for fname in sorted(os.listdir(STATE_DIR)):
        if fname.endswith(".yaml") or fname.endswith(".yml"):
            path = os.path.join(STATE_DIR, fname)
            with open(path) as f:
                item = yaml.safe_load(f)
            items[item["id"]] = item
    return items


def load_proposals():
    """Load all proposals from proposals/ directory."""
    proposals = []
    for fname in sorted(os.listdir(PROPOSALS_DIR)):
        if fname.endswith(".json"):
            path = os.path.join(PROPOSALS_DIR, fname)
            with open(path) as f:
                proposals.append(json.load(f))
    return proposals


def reconcile():
    portfolio = load_portfolio()
    proposals = load_proposals()

    claimed_by_ref = set()   # portfolio ids claimed by explicit ref match
    claimed_by_title = set() # portfolio ids claimed by title match at >= HIGH

    results = []

    # Pass 1: match by ref first, then title. Ref claims take priority.
    for idx, prop in enumerate(proposals):
        ref = prop["ref"]
        matched_id = None
        match_score = None
        match_method = None

        if ref and ref in portfolio:
            matched_id = ref
            match_score = 1.0
            match_method = "ref"
            if matched_id not in claimed_by_ref:
                claimed_by_ref.add(matched_id)
        elif not ref:
            # Title matching: find best overlap score
            best_score = 0.0
            best_id = None
            for pid, pitem in portfolio.items():
                score = overlap_coeff(prop["title"], pitem["title"])
                if score > best_score:
                    best_score = score
                    best_id = pid
            if best_score >= HIGH:
                matched_id = best_id
                match_score = best_score
                match_method = "title"
                # Only claim if not already claimed by ref
                if matched_id not in claimed_by_ref and matched_id not in claimed_by_title:
                    claimed_by_title.add(matched_id)
            elif best_score >= LOW:
                # Ambiguous: record best match for reference
                matched_id = best_id
                match_score = best_score
                match_method = "title_best_effort"
            else:
                match_score = best_score if best_score > 0 else 0.0
                match_method = "title_best_effort" if best_score > 0 else "none"
        else:
            # ref exists but not in portfolio
            match_method = "ref_not_found"
            match_score = 0.0

        results.append({
            "idx": idx,
            "ref": ref,
            "title": prop["title"],
            "status": prop["status"],
            "source": prop["source"],
            "matched_id": matched_id,
            "match_score": round(match_score, 4) if match_score is not None else None,
            "match_method": match_method,
        })

    # Pass 2: determine duplicates
    # Ref claims take priority over title claims.
    # First pass: establish ref claimants (in idx order)
    # Second pass: establish title claimants for unclaimed portfolio items (in idx order)

    first_claimant = {}  # portfolio_id -> idx of first claimant

    # Process ref matches first
    for r in results:
        pid = r["matched_id"]
        if pid is None:
            continue
        if r["match_method"] == "ref":
            if pid not in first_claimant:
                first_claimant[pid] = r["idx"]

    # Then process title matches at >= HIGH (only for unclaimed)
    for r in results:
        pid = r["matched_id"]
        if pid is None:
            continue
        method = r["match_method"]
        score = r["match_score"]
        is_title_strong = (method == "title" and score is not None and score >= HIGH)
        if is_title_strong and pid not in first_claimant:
            first_claimant[pid] = r["idx"]

    # Pass 3: assign buckets
    for r in results:
        pid = r["matched_id"]
        score = r["match_score"]
        method = r["match_method"]

        # Determine if this is a duplicate
        is_dup = False
        is_strong_match = (method == "ref") or (method == "title" and score is not None and score >= HIGH)
        if is_strong_match and pid is not None and pid in first_claimant:
            if first_claimant[pid] != r["idx"]:
                is_dup = True

        if is_dup:
            r["bucket"] = "duplicate"
        elif method == "ref" or (method == "title" and score is not None and score >= HIGH):
            # Matched — check portfolio status
            pitem = portfolio[pid]
            p_done = is_done(pitem["status"])
            r_done = is_done(r["status"])
            r_active = is_active(r["status"])

            if p_done and r_active:
                r["bucket"] = "conflict"
            else:
                # Title or status differs?
                title_diff = r["title"].lower().strip() != pitem["title"].lower().strip()
                status_diff = r["status"].lower().strip() != pitem["status"].lower().strip()
                if title_diff or status_diff:
                    r["bucket"] = "changed"
                else:
                    r["bucket"] = "completed"
        elif method == "title_best_effort" and score is not None and LOW <= score < HIGH:
            r["bucket"] = "ambiguous"
        else:
            # No match
            if is_done(r["status"]):
                r["bucket"] = "done_gap"
            else:
                r["bucket"] = "gap"

    # Calculate summary
    summary = {}
    for bucket in ["changed", "gap", "conflict", "ambiguous", "duplicate", "completed", "done_gap"]:
        summary[bucket] = sum(1 for r in results if r["bucket"] == bucket)

    # Unconfirmed portfolio items
    all_claimed = set()
    for r in results:
        if r["matched_id"] and r["bucket"] != "duplicate":
            is_strong = (r["match_method"] == "ref") or \
                        (r["match_method"] == "title" and r["match_score"] is not None and r["match_score"] >= HIGH)
            if is_strong:
                all_claimed.add(r["matched_id"])
    unconfirmed = sorted(set(portfolio.keys()) - all_claimed)

    output = {
        "summary": summary,
        "unconfirmed": unconfirmed,
        "results": results,
    }

    with open("reconcile.json", "w") as f:
        json.dump(output, f, indent=2, sort_keys=True)

    print(f"Reconciliation complete: {len(results)} rows processed")
    for bucket, count in summary.items():
        print(f"  {bucket}: {count}")
    print(f"  unconfirmed: {len(unconfirmed)} ({', '.join(unconfirmed)})")


if __name__ == "__main__":
    reconcile()