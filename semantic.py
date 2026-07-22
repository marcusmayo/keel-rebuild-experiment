"""Phase 4 -- semantic judgment pass.

Sends ONLY the ambiguous rows to the model for a SAME/DISTINCT verdict
with a one-sentence reason, and annotates the verdict into
reconcile.json in place. Buckets never change.

--no-llm skips the model entirely (deterministic testing) and marks
verdicts as SKIPPED.
"""
import argparse
import json
import re

from common import RECONCILE_PATH, load_portfolio
from llm import chat, extract_json

PROMPT = """You are reconciling a project portfolio against an external source row.

Portfolio item {pid}: "{ptitle}" (status: {pstatus})
Source row: "{rtitle}" (status: {rstatus}, source: {source})

Do these two rows refer to the SAME underlying work item, or are they
DISTINCT items? Answer with a JSON object only:
{{"verdict": "SAME" or "DISTINCT", "reason": "one sentence"}}"""


def judge(portfolio, row):
    item = portfolio[row["match"]]
    text = chat([{"role": "user", "content": PROMPT.format(
        pid=row["match"], ptitle=item["title"], pstatus=item["status"],
        rtitle=row["title"], rstatus=row["status"], source=row["source"],
    )}])
    try:
        data = extract_json(text)
        verdict = str(data.get("verdict", "")).upper()
        reason = str(data.get("reason", "")).strip()
    except (ValueError, KeyError):
        m = re.search(r"\b(SAME|DISTINCT)\b", text.upper())
        verdict = m.group(1) if m else ""
        reason = text.strip()
    if verdict not in ("SAME", "DISTINCT"):
        verdict = "SAME" if "SAME" in text.upper() else "DISTINCT"
    if not reason:
        reason = text.strip() or "model returned no reason"
    return verdict, reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true",
                    help="skip the model; mark verdicts SKIPPED")
    args = ap.parse_args()

    with open(RECONCILE_PATH) as f:
        data = json.load(f)
    portfolio = load_portfolio()

    judged = 0
    for row in data["rows"]:
        if row["bucket"] != "ambiguous":
            continue
        if args.no_llm:
            row["verdict"] = "SKIPPED"
            row["reason"] = "no-llm mode: model call skipped"
        else:
            verdict, reason = judge(portfolio, row)
            row["verdict"] = verdict
            row["reason"] = reason
        judged += 1  # bucket stays "ambiguous" -- annotated in place

    with open(RECONCILE_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"Annotated {judged} ambiguous row(s) in {RECONCILE_PATH}"
          + (" (no-llm)" if args.no_llm else ""))


if __name__ == "__main__":
    main()
