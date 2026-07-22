#!/usr/bin/env python3
"""Phase 4: Semantic judgment (ambiguous rows → LLM) and WSJF scoring."""

import os
import json
import sys
import requests

BASE = os.path.dirname(os.path.abspath(__file__))


def load_env():
    """Load .env file into os.environ."""
    env_path = os.path.join(BASE, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ[key.strip()] = val.strip()


def get_llm_config():
    """Return (base_url, api_key, model) from environment."""
    load_env()
    base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "z-ai/glm-5.2")
    return base_url, api_key, model


def llm_chat(messages, no_llm=False):
    """Send a chat completion request. Returns content string or None."""
    if no_llm:
        return None
    base_url, api_key, model = get_llm_config()
    if not api_key:
        print("Warning: OPENROUTER_API_KEY not set. Skipping LLM call.")
        return None
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None


def semantic_pass(no_llm=False):
    """Judge ambiguous rows with the model. Annotate reconcile.json in place."""
    recon_path = os.path.join(BASE, "reconcile.json")
    with open(recon_path) as f:
        data = json.load(f)

    ambiguous_rows = [r for r in data["results"] if r["bucket"] == "ambiguous"]

    if not ambiguous_rows:
        print("No ambiguous rows to judge.")
        return

    import yaml
    portfolio = {}
    state_dir = os.path.join(BASE, "state")
    for fname in os.listdir(state_dir):
        if fname.endswith(".yaml") or fname.endswith(".yml"):
            with open(os.path.join(state_dir, fname)) as f:
                item = yaml.safe_load(f)
            portfolio[item["id"]] = item

    for row in ambiguous_rows:
        source_title = row["title"]
        target_id = row["match_target"]
        target_title = portfolio.get(target_id, {}).get("title", "unknown")

        prompt = f"""You are a project portfolio analyst. Compare these two work items and decide if they refer to the SAME work or are DISTINCT.

Source item: "{source_title}"
Portfolio item: "{target_title}"

Reply with exactly one word on the first line: SAME or DISTINCT.
On the second line, provide a one-sentence reason for your judgment.

Example:
SAME
Both refer to the same project with slightly different wording."""

        messages = [{"role": "user", "content": prompt}]
        response = llm_chat(messages, no_llm=no_llm)

        if response:
            lines = response.strip().split("\n")
            verdict = lines[0].strip().upper() if lines else "UNKNOWN"
            reason = lines[1].strip() if len(lines) > 1 else ""
            if verdict not in ("SAME", "DISTINCT"):
                # Try to extract
                if "SAME" in verdict:
                    verdict = "SAME"
                elif "DISTINCT" in verdict:
                    verdict = "DISTINCT"
                else:
                    verdict = "UNKNOWN"
        else:
            verdict = "SKIPPED" if no_llm else "UNKNOWN"
            reason = "LLM not available" if no_llm else "LLM call failed"

        row["semantic_verdict"] = verdict
        row["semantic_reason"] = reason
        print(f"Ambiguous row '{source_title}' → {verdict}: {reason}")

    with open(recon_path, "w") as f:
        json.dump(data, f, indent=2)
    print("Semantic pass complete. reconcile.json updated.")


def score_item(item_id, no_llm=False):
    """Propose WSJF factors for an item, compute score, store in scores/."""
    import yaml
    state_dir = os.path.join(BASE, "state")
    path = os.path.join(state_dir, f"{item_id}.yaml")
    if not os.path.exists(path):
        print(f"Item {item_id} not found.")
        return None

    with open(path) as f:
        item = yaml.safe_load(f)

    prompt = f"""You are a project portfolio analyst using WSJF (Weighted Shortest Job First) prioritization.

For the following work item:
Title: {item['title']}
Status: {item['status']}

Propose scores (1-10) for each WSJF factor:
- business_value: How much business value does this deliver?
- time_criticality: How urgent is this?
- risk_reduction: How much does this reduce risk or unlock other work?
- job_size: How large is this effort? (1=smallest, 10=largest)

Reply in strict JSON format:
{{"business_value": N, "time_criticality": N, "risk_reduction": N, "job_size": N}}"""

    messages = [{"role": "user", "content": prompt}]
    response = llm_chat(messages, no_llm=no_llm)

    if response:
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r"\{[^}]+\}", response)
            if json_match:
                factors = json.loads(json_match.group())
            else:
                factors = json.loads(response)
        except json.JSONDecodeError:
            print(f"Failed to parse LLM response as JSON: {response}")
            return None
    else:
        # No-LLM: use placeholder factors
        factors = {
            "business_value": 5,
            "time_criticality": 5,
            "risk_reduction": 5,
            "job_size": 5,
        }

    # Compute WSJF = (business_value + time_criticality + risk_reduction) / job_size
    bv = float(factors["business_value"])
    tc = float(factors["time_criticality"])
    rr = float(factors["risk_reduction"])
    js = float(factors["job_size"])
    wsjf = (bv + tc + rr) / js if js != 0 else 0.0

    result = {
        "item_id": item_id,
        "title": item["title"],
        "factors": {
            "business_value": bv,
            "time_criticality": tc,
            "risk_reduction": rr,
            "job_size": js,
        },
        "wsjf_score": round(wsjf, 4),
        "wsjf_formula": f"({bv} + {tc} + {rr}) / {js}",
    }

    # Verify: recompute from stored factors
    f = result["factors"]
    recomputed = (f["business_value"] + f["time_criticality"] + f["risk_reduction"]) / f["job_size"]
    assert round(recomputed, 4) == result["wsjf_score"], "Score recomputation mismatch!"

    scores_dir = os.path.join(BASE, "scores")
    os.makedirs(scores_dir, exist_ok=True)
    out_path = os.path.join(scores_dir, f"{item_id}.json")
    with open(out_path, "w") as fout:
        json.dump(result, fout, indent=2)

    print(f"Scored {item_id}: WSJF = {result['wsjf_score']} → scores/{item_id}.json")
    return result


def main():
    no_llm = "--no-llm" in sys.argv
    print("=== Phase 4: Semantic Judgment ===")
    semantic_pass(no_llm=no_llm)
    print()
    print("=== Phase 4: WSJF Scoring (scoring ML-001 as example) ===")
    score_item("ML-001", no_llm=no_llm)


if __name__ == "__main__":
    main()