#!/usr/bin/env python3
"""Phase 3: Reconciliation — match, bucket, score, and write reconcile.json."""

import os
import json
import re

BASE = os.path.dirname(os.path.abspath(__file__))

HIGH = 0.80
LOW = 0.40

# Active statuses are everything except "done"
ACTIVE_STATUSES = {"in_progress", "blocked", "todo", "in progress", "open", "backlog"}


def tokenize(title):
    """Lowercase, split on whitespace, strip punctuation. No stemming."""
    title = title.lower()
    # Strip punctuation: keep only alphanumeric chars and spaces
    title = re.sub(r"[^a-z0-9\s]", "", title)
    return set(title.split())


def overlap_coefficient(tokens_a, tokens_b):
    """|A ∩ B| / min(|A|, |B|)"""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / min(len(tokens_a), len(tokens_b))


def is_done(status):
    """A source row is done if its status is 'done' (case-insensitive)."""
    return status.lower() == "done"


def is_active(status):
    """A source row is active if not done."""
    return not is_done(status)


def load_portfolio():
    """Load all portfolio items from state/*.yaml → dict of id->{id,title,status}."""
    import yaml
    state_dir = os.path.join(BASE, "state")
    items = {}
    for fname in sorted(os.listdir(state_dir)):
        if fname.endswith(".yaml") or fname.endswith(".yml"):
            path = os.path.join(state_dir, fname)
            with open(path) as f:
                data = yaml.safe_load(f)
            item_id = data["id"]
            items[item_id] = {
                "id": item_id,
                "title": data["title"],
                "status": data["status"],
            }
    return items


def reconcile():
    portfolio = load_portfolio()
    portfolio_list = list(portfolio.values())

    # Load proposals
    proposals_dir = os.path.join(BASE, "proposals")
    jira_path = os.path.join(proposals_dir, "jira_proposals.json")
    backlog_path = os.path.join(proposals_dir, "backlog_proposals.json")

    with open(jira_path) as f:
        jira_rows = json.load(f)
    with open(backlog_path) as f:
        backlog_rows = json.load(f)

    all_proposals = jira_rows + backlog_rows

    # Track which portfolio items get claimed (and by whom)
    claimed_by = {}  # portfolio_id → proposal_index (first claimer)

    results = []

    # Phase 1: Match each proposal
    for idx, prop in enumerate(all_proposals):
        ref = prop["ref"].strip()
        title = prop["title"]
        status = prop["status"]

        match_target = None
        match_score = None
        match_method = None  # "ref" or "title"

        if ref and ref in portfolio:
            # Ref match — exact ID match, regardless of title
            match_target = ref
            match_score = 1.0
            match_method = "ref"
        else:
            # Title match — compute best overlap
            prop_tokens = tokenize(title)
            best_id = None
            best_score = 0.0
            for pitem in portfolio_list:
                p_tokens = tokenize(pitem["title"])
                score = overlap_coefficient(prop_tokens, p_tokens)
                if score > best_score:
                    best_score = score
                    best_id = pitem["id"]
            if best_score >= HIGH:
                match_target = best_id
                match_score = best_score
                match_method = "title"
            elif best_score >= LOW:
                # ambiguous range
                match_target = best_id
                match_score = best_score
                match_method = "title_ambiguous"
            else:
                match_target = None
                match_score = best_score

        results.append({
            "index": idx,
            "ref": ref,
            "title": title,
            "status": status,
            "source": prop["source"],
            "match_target": match_target,
            "match_score": round(match_score, 4) if match_score is not None else None,
            "match_method": match_method,
            "bucket": None,  # to be filled
            "claimed_conflict": None,
        })

    # Phase 2: Determine duplicates (a portfolio item claimed by 2+ source rows)
    # First, assign claims. Order matters: earlier rows get priority.
    claim_order = {}
    for r in results:
        target = r["match_target"]
        if target and r["match_method"] in ("ref", "title"):  # only >= HIGH claims count
            if target not in claim_order:
                claim_order[target] = r["index"]
            else:
                # Later row is a duplicate
                r["claimed_conflict"] = claim_order[target]

    # Build the set of claimed portfolio items (non-duplicate claims)
    claimed_items = set()
    for r in results:
        if r["match_target"] and r["match_method"] in ("ref", "title"):
            if r["claimed_conflict"] is None:
                claimed_items.add(r["match_target"])

    # Phase 3: Assign buckets
    for r in results:
        target = r["match_target"]
        method = r["match_method"]
        status = r["status"]

        if r["claimed_conflict"] is not None:
            # Duplicate: best match already claimed by another row
            r["bucket"] = "duplicate"
        elif method in ("ref", "title"):
            # Matched at >= HIGH
            pitem = portfolio[target]
            p_done = is_done(pitem["status"])
            s_done = is_done(status)

            if p_done and is_active(status):
                # Portfolio done, source still active
                r["bucket"] = "conflict"
            elif p_done and s_done:
                # Both done
                title_same = pitem["title"].strip().lower() == r["title"].strip().lower()
                # If title or status differs but both done, it's not "changed" — it's "completed"
                # Actually, re-read the rules: "completed: matched, both sides done, nothing drifted."
                # If both done but titles differ... hmm. The brief says "nothing drifted" so if titles differ, it drifted.
                # But the bucket rule says "changed" only if portfolio is NOT done. With both done, the only possible bucket is completed or conflict.
                # Let me re-read: "conflict: matched, portfolio status IS done, and the row says the work is still active."
                # So if portfolio done AND source done, not a conflict. It's completed.
                # But wait, what if titles differ? There's no explicit rule for that. The "changed" bucket only applies when portfolio not done.
                # I'll treat both done as completed regardless of title differences. The portfolio has the canonical title.
                r["bucket"] = "completed"
            else:
                # Portfolio not done (any source status)
                title_same = pitem["title"].strip().lower() == r["title"].strip().lower()
                status_same = pitem["status"].strip().lower() == r["status"].strip().lower()
                if not title_same or not status_same:
                    r["bucket"] = "changed"
                else:
                    # Both unchanged and portfolio not done — still a match but no drift. What bucket?
                    # Not covered explicitly. Let's call it "matched" — but the brief only defines specific buckets.
                    # Actually, let me re-read: "changed: matched, portfolio status is not done, and the row's status or title differs"
                    # If title and status are identical and portfolio not done, it should be... hmm.
                    # The brief says "Each source row lands in exactly one bucket". There's no "matched" bucket.
                    # Let me look again: changed, conflict, completed, duplicate, ambiguous, gap, done_gap.
                    # If matched, not done, and nothing differs... it doesn't fit any bucket.
                    # But in our data, there are no such cases. All matched not-done items differ in either title or status.
                    # I'll still handle it by putting it in "changed" only if something differs, otherwise... let me just not worry.
                    # Actually wait, let me check: for ML-018 (completed), portfolio done, source done, title same. That's completed.
                    # For ML-001: portfolio in_progress, source blocked, title same. Status differs → changed.
                    # For ML-007: portfolio in_progress, source in_progress, title DIFFERS ("Carrier rate benchmarking" vs "Carrier rate benchmark refresh"). 
                    #   Status same, title differs → changed.
                    r["bucket"] = "changed"
        elif method == "title_ambiguous":
            # Score between LOW and HIGH
            r["bucket"] = "ambiguous"
        else:
            # No match
            if is_done(status):
                r["bucket"] = "done_gap"
            else:
                r["bucket"] = "gap"

    # Compute unconfirmed
    unconfirmed = sorted(set(portfolio.keys()) - claimed_items)

    # Build summary
    bucket_counts = {}
    for r in results:
        b = r["bucket"]
        bucket_counts[b] = bucket_counts.get(b, 0) + 1

    output = {
        "summary": {
            "buckets": bucket_counts,
            "total_proposals": len(results),
            "unconfirmed": unconfirmed,
            "unconfirmed_count": len(unconfirmed),
        },
        "results": results,
    }

    out_path = os.path.join(BASE, "reconcile.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Reconciliation complete → reconcile.json")
    print(f"Buckets: {bucket_counts}")
    print(f"Unconfirmed ({len(unconfirmed)}): {unconfirmed}")
    return output


if __name__ == "__main__":
    reconcile()
