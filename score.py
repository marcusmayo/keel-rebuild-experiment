"""Phase 4 -- WSJF scoring.

Asks the model to propose WSJF factors for a chosen portfolio item
(business_value, time_criticality, risk_reduction, job_size; each 1-10),
then computes in plain deterministic arithmetic:

    WSJF = (business_value + time_criticality + risk_reduction) / job_size

Factors and score are stored together in scores.json so any score is
recomputable from its stored factors. --no-llm uses fixed factors
(5,5,5,5) and makes no network call.
"""
import argparse
import json
import os

from common import SCORES_PATH, load_portfolio
from llm import chat, extract_json

FACTORS = ["business_value", "time_criticality", "risk_reduction", "job_size"]

PROMPT = """You are scoring a portfolio work item with Weighted Shortest Job First.

Item {pid}: "{title}" (status: {status})

Propose four integer factors, each from 1 to 10:
- business_value: relative value to the business
- time_criticality: how fast value decays
- risk_reduction: risk removed or opportunity enabled
- job_size: relative effort (10 = largest)

Answer with a JSON object only:
{{"business_value": N, "time_criticality": N, "risk_reduction": N, "job_size": N}}"""


def propose_factors(item):
    text = chat([{"role": "user", "content": PROMPT.format(
        pid=item["id"], title=item["title"], status=item["status"])}])
    data = extract_json(text)
    factors = {}
    for f in FACTORS:
        v = int(data[f])
        factors[f] = max(1, min(10, v))
    return factors


def wsjf(factors):
    return (factors["business_value"] + factors["time_criticality"]
            + factors["risk_reduction"]) / factors["job_size"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True, help="portfolio item id")
    ap.add_argument("--no-llm", action="store_true",
                    help="skip the model; use fixed factors 5/5/5/5")
    args = ap.parse_args()

    portfolio = load_portfolio()
    if args.item not in portfolio:
        raise SystemExit(f"unknown item: {args.item}")
    item = portfolio[args.item]

    if args.no_llm:
        factors = {f: 5 for f in FACTORS}
    else:
        factors = propose_factors(item)
    score = wsjf(factors)

    scores = {}
    if os.path.exists(SCORES_PATH):
        with open(SCORES_PATH) as f:
            scores = json.load(f)
    scores[args.item] = {"id": args.item, "title": item["title"],
                         "factors": factors, "wsjf": score,
                         "model": "no-llm" if args.no_llm else "llm"}
    with open(SCORES_PATH, "w") as f:
        json.dump(scores, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"{args.item}: factors={factors} WSJF={score:.4f}"
          + (" (no-llm)" if args.no_llm else ""))


if __name__ == "__main__":
    main()
