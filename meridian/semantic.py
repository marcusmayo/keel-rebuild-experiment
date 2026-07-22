"""Phase 4: semantic judgment of the ambiguous bucket.

Sends ONLY the ambiguous rows to the model, asking SAME or DISTINCT with a
one-sentence reason. The verdict is annotated into the row in place -- the
bucket is never changed and no other row is touched. With --no-llm the model
is not called and rows are left unannotated.
"""
from __future__ import annotations

from typing import Dict, List

from .llm import chat, extract_json, LLMError
from .portfolio import get_item


SYSTEM_PROMPT = (
    "You are a portfolio reconciliation judge. You are given a source work "
    "item and a candidate portfolio work item whose titles partially overlap. "
    "Decide whether they refer to the SAME underlying piece of work or are "
    "DISTINCT pieces of work. Respond ONLY with a JSON object of the form "
    '{\"verdict\": \"SAME\" | \"DISTINCT\", \"reason\": \"one sentence\"}.'
)


def _build_user_prompt(row: Dict) -> str:
    target_id = row.get("target")
    port = get_item(target_id) if target_id else None
    port_title = port["title"] if port else "(unknown)"
    return (
        f"Source row title: \"{row.get('title', '')}\" "
        f"(status: {row.get('status', '')}, source: {row.get('source', '')}).\n"
        f"Candidate portfolio item: {target_id} \"{port_title}\".\n"
        f"Title overlap score: {row.get('score')}.\n"
        "Are these the SAME underlying work or DISTINCT? "
        "Answer with the JSON object described."
    )


def judge_row(row: Dict) -> Dict:
    """Call the model for one ambiguous row; return {verdict, reason}."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(row)},
    ]
    content = chat(messages, temperature=0.0, max_tokens=200)
    data = extract_json(content)
    verdict = str(data.get("verdict", "")).strip().upper()
    reason = str(data.get("reason", "")).strip()
    if verdict not in {"SAME", "DISTINCT"}:
        raise LLMError(f"unexpected verdict: {verdict!r}")
    if not reason:
        raise LLMError("model returned an empty reason")
    return {"verdict": verdict, "reason": reason}


def run_semantic_pass(report: Dict, *, use_llm: bool = True) -> Dict:
    """Annotate ambiguous rows in the report in place. Buckets unchanged.

    Returns the same report dict (mutated). When use_llm is False, no model
    call is made and rows are left without a verdict.
    """
    ambiguous_rows = [r for r in report["rows"] if r["bucket"] == "ambiguous"]
    report["summary"]["semantic"] = {
        "judged": 0,
        "ambiguous_count": len(ambiguous_rows),
        "used_llm": bool(use_llm),
    }
    if not use_llm:
        return report

    judged = 0
    for row in ambiguous_rows:
        verdict = judge_row(row)
        row["semantic"] = verdict  # annotate in place; bucket stays ambiguous
        judged += 1
    report["summary"]["semantic"]["judged"] = judged
    return report
