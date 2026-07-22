"""Deterministic title matching via the overlap coefficient.

Rules (from the brief, non-negotiable):
  - lowercase the title, split on whitespace, strip punctuation, no stemming.
  - overlap = |A intersect B| / min(|A|, |B|).
  - HIGH = 0.80, LOW = 0.40.
"""
from __future__ import annotations

import string
from typing import Dict, List, Optional, Tuple

from .config import HIGH, LOW

# Punctuation stripped from the edges of each whitespace-split token.
_PUNCT = string.punctuation


def normalize_tokens(title: str) -> set:
    """Return the normalized token set for a title.

    Lowercase, split on whitespace, strip surrounding punctuation from each
    token, drop empties. No stemming.
    """
    tokens = set()
    for raw in (title or "").lower().split():
        token = raw.strip(_PUNCT)
        if token:
            tokens.add(token)
    return tokens


def overlap_coefficient(a_title: str, b_title: str) -> float:
    """Overlap coefficient of two titles' normalized token sets."""
    a = normalize_tokens(a_title)
    b = normalize_tokens(b_title)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    denom = min(len(a), len(b))
    if denom == 0:
        return 0.0
    return inter / denom


def best_title_match(
    title: str, portfolio: List[Dict]
) -> Tuple[Optional[str], float]:
    """Best portfolio match for a title by overlap coefficient.

    Returns (portfolio_id, score). Ties are broken by portfolio id order so
    the result is fully deterministic. Returns (None, 0.0) for empty input.
    """
    best_id: Optional[str] = None
    best_score = -1.0
    for item in portfolio:
        score = overlap_coefficient(title, item["title"])
        if score > best_score:
            best_score = score
            best_id = item["id"]
    if best_id is None:
        return None, 0.0
    return best_id, best_score


def classify_score(score: float) -> str:
    """Classify a title-overlap score into match / ambiguous / no-match."""
    if score >= HIGH:
        return "match"
    if score < LOW:
        return "no_match"
    return "ambiguous"
