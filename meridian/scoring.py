"""Phase 4: WSJF scoring.

Asks the model to propose WSJF factors (business_value, time_criticality,
risk_reduction, job_size -- each 1-10) for a chosen item, then computes

    WSJF = (business_value + time_criticality + risk_reduction) / job_size

in plain arithmetic and stores factors and score together. Any stored score
is always exactly recomputable from its stored factors.
"""
from __future__ import annotations

from typing import Dict

from .llm import chat, extract_json, LLMError

FACTOR_NAMES = ("business_value", "time_criticality", "risk_reduction", "job_size")

SYSTEM_PROMPT = (
    "You are an Agile portfolio analyst estimating WSJF (Weighted Shortest Job "
    "First) factors. For the given work item, propose four integer factors, "
    "each from 1 to 10: business_value, time_criticality, risk_reduction, and "
    "job_size. Respond ONLY with a JSON object of the form "
    '{\"business_value\": int, \"time_criticality\": int, '
    '\"risk_reduction\": int, \"job_size\": int}.'
)


def compute_wsjf(factors: Dict) -> float:
    """Pure arithmetic: WSJF = (bv + tc + rr) / job_size, rounded to 6 dp."""
    bv = float(factors["business_value"])
    tc = float(factors["time_criticality"])
    rr = float(factors["risk_reduction"])
    js = float(factors["job_size"])
    if js == 0:
        raise ValueError("job_size must be non-zero")
    return round((bv + tc + rr) / js, 6)


def _clamp_int(value, lo: int = 1, hi: int = 10) -> int:
    iv = int(round(float(value)))
    return max(lo, min(hi, iv))


def propose_factors(item: Dict) -> Dict:
    """Call the model to propose the four WSJF factors for an item."""
    user = (
        f"Work item {item.get('id', '')}: \"{item.get('title', '')}\" "
        f"(status: {item.get('status', '')}).\n"
        "Propose the four WSJF factors as the JSON object described."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    content = chat(messages, temperature=0.0, max_tokens=200)
    data = extract_json(content)
    factors = {}
    for name in FACTOR_NAMES:
        if name not in data:
            raise LLMError(f"missing factor: {name}")
        factors[name] = _clamp_int(data[name])
    return factors


def score_item(item: Dict, *, use_llm: bool = True) -> Dict:
    """Produce a stored score record for an item.

    With use_llm False, uses deterministic placeholder factors (all mid-range)
    so the pipeline runs to completion without a network call. The stored score
    is always recomputable from the stored factors by pure arithmetic.
    """
    if use_llm:
        factors = propose_factors(item)
        source = "llm"
    else:
        factors = {
            "business_value": 5,
            "time_criticality": 5,
            "risk_reduction": 5,
            "job_size": 5,
        }
        source = "deterministic"
    score = compute_wsjf(factors)
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "factors": factors,
        "wsjf": score,
        "factor_source": source,
    }
