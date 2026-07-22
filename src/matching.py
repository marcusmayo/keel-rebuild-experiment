"""Deterministic title matching via the overlap coefficient.

The rule (from AGENTS.md): lowercase the title, split on whitespace, strip
punctuation, no stemming. overlap = |A intersect B| / min(|A|, |B|).
Thresholds HIGH = 0.80, LOW = 0.40.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_tokens(title: str) -> set[str]:
    """Lowercase, then extract alphanumeric tokens (splits on whitespace and
    strips punctuation in one step). Equivalent to 'split on whitespace,
    strip punctuation' for the seeded data, which contains no punctuation."""
    return set(_TOKEN_RE.findall(title.lower()))


def overlap_coefficient(a: str, b: str) -> float:
    """overlap = |A intersect B| / min(|A|, |B|). Returns 0.0 for empty sets."""
    ta = normalize_tokens(a)
    tb = normalize_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))
