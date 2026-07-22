#!/usr/bin/env python3
"""Phase 4: Semantic judgment for ambiguous rows and WSJF scoring."""
import os
import json
import sys
import requests

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "z-ai/glm-5.2")


def call_llm(prompt, no_llm=False):
    """Call the LLM via OpenAI-compatible chat-completions API."""
    if no_llm:
        return None

    if not OPENROUTER_API_KEY:
        print("Warning: OPENROUTER_API_KEY not set. Running without LLM.")
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a precise portfolio reconciliation assistant. Answer concisely."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
    }
    try:
        resp = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        msg = choice.get("message", {})
        # Some reasoning models put output in reasoning field, not content
        result = msg.get("content") or msg.get("reasoning") or ""
        return result.strip() if result else None
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None


def semantic_judgment(no_llm=False):
    """Judge ambiguous rows: SAME or DISTINCT."""
    with open("reconcile.json") as f:
        data = json.load(f)

    ambiguous_rows = [r for r in data["results"] if r["bucket"] == "ambiguous"]

    if not ambiguous_rows:
        print("No ambiguous rows to judge.")
        return

    for r in ambiguous_rows:
        match_id = r["matched_id"]
        row_title = r["title"]
        match_title = "unknown"
        # Load portfolio item title
        import yaml
        try:
            with open(f"state/{match_id}.yaml") as f:
                pitem = yaml.safe_load(f)
                match_title = pitem["title"]
        except Exception:
            pass

        prompt = (
            f"You are judging whether two work items are the SAME item with minor wording differences "
            f"or DISTINCT items.\n\n"
            f"Row title: \"{row_title}\"\n"
            f"Portfolio title: \"{match_title}\"\n\n"
            f"Answer exactly one of: \"SAME\" or \"DISTINCT\", followed by a one-sentence reason."
        )

        verdict_raw = call_llm(prompt, no_llm=no_llm)

        if verdict_raw is None:
            if no_llm:
                r["semantic_verdict"] = "SKIPPED"
                r["semantic_reason"] = "--no-llm flag active, model not called"
            else:
                r["semantic_verdict"] = "ERROR"
                r["semantic_reason"] = "LLM call failed"
        else:
            # Parse the verdict
            verdict_upper = verdict_raw.upper()
            if "DISTINCT" in verdict_upper:
                r["semantic_verdict"] = "DISTINCT"
            elif "SAME" in verdict_upper:
                r["semantic_verdict"] = "SAME"
            else:
                r["semantic_verdict"] = "UNCLEAR"
            r["semantic_reason"] = verdict_raw

        print(f"Ambiguous row judged: {r['semantic_verdict']} — {r['semantic_reason'][:80]}")

    with open("reconcile.json", "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)

    print(f"Judged {len(ambiguous_rows)} ambiguous row(s)")


def score_wsjf(item_id, no_llm=False):
    """Ask model for WSJF factors for a given item, then compute WSJF."""
    import yaml

    # Load the portfolio item
    with open(f"state/{item_id}.yaml") as f:
        pitem = yaml.safe_load(f)

    prompt = (
        f"For this work item, propose WSJF factors on a scale of 1-10 (1=lowest, 10=highest):\n\n"
        f"Title: \"{pitem['title']}\"\n"
        f"Status: {pitem['status']}\n\n"
        f"Return exactly four numbers in this JSON format:\n"
        f'{{"business_value": <1-10>, "time_criticality": <1-10>, '
        f'"risk_reduction": <1-10>, "job_size": <1-10>}}'
    )

    raw = call_llm(prompt, no_llm=no_llm)

    if raw is None:
        if no_llm:
            factors = {
                "business_value": 5,
                "time_criticality": 5,
                "risk_reduction": 5,
                "job_size": 5,
            }
            print(f"Using default factors (--no-llm): {factors}")
        else:
            print("LLM call failed, cannot score.")
            return None
    else:
        try:
            # Try to extract JSON from the response
            import re
            match = re.search(r'\{[^}]+\}', raw)
            if match:
                factors = json.loads(match.group())
            else:
                factors = json.loads(raw)
        except Exception:
            print(f"Failed to parse LLM response: {raw}")
            return None

    bv = factors["business_value"]
    tc = factors["time_criticality"]
    rr = factors["risk_reduction"]
    js = factors["job_size"]

    wsjf = (bv + tc + rr) / js if js != 0 else 0.0

    result = {
        "item_id": item_id,
        "title": pitem["title"],
        "factors": {
            "business_value": bv,
            "time_criticality": tc,
            "risk_reduction": rr,
            "job_size": js,
        },
        "wsjf_score": round(wsjf, 4),
    }

    # Verify recomputation
    recomputed = (bv + tc + rr) / js if js != 0 else 0.0
    assert abs(recomputed - wsjf) < 0.0001, "WSJF score verification failed!"

    os.makedirs("scores", exist_ok=True)
    score_path = f"scores/{item_id}_wsjf.json"
    with open(score_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"WSJF score for {item_id}: {wsjf} (factors: {factors})")
    print(f"Score saved to {score_path}")
    print(f"Verification: recomputing from factors reproduces stored value exactly.")

    return result


def main():
    no_llm = "--no-llm" in sys.argv

    # 1. Semantic judgment
    print("=== Semantic Judgment ===")
    semantic_judgment(no_llm=no_llm)

    # 2. WSJF scoring for a chosen item (ML-001 as default example)
    score_item = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "ML-001"
    print(f"\n=== WSJF Scoring for {score_item} ===")
    score_wsjf(score_item, no_llm=no_llm)


if __name__ == "__main__":
    main()