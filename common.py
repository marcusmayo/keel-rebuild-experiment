"""Shared deterministic helpers for Meridian PPM."""
import os
import re
import string

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(ROOT, "state")
IMPORTS_DIR = os.path.join(ROOT, "imports")
PROPOSALS_DIR = os.path.join(ROOT, "proposals")
LOGS_DIR = os.path.join(ROOT, "logs")
EXPORTS_DIR = os.path.join(ROOT, "exports")
RECONCILE_PATH = os.path.join(ROOT, "reconcile.json")
SCORES_PATH = os.path.join(ROOT, "scores.json")

HIGH = 0.80
LOW = 0.40

BUCKET_ORDER = ["changed", "conflict", "completed", "duplicate",
                "ambiguous", "gap", "done_gap"]


def load_env(path=None):
    """Parse a simple KEY=VALUE .env file into os.environ (no override)."""
    path = path or os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def load_portfolio():
    """Load all portfolio items from state/, sorted by id."""
    items = {}
    if not os.path.isdir(STATE_DIR):
        return items
    for name in sorted(os.listdir(STATE_DIR)):
        if not name.endswith((".yaml", ".yml")):
            continue
        with open(os.path.join(STATE_DIR, name)) as f:
            item = yaml.safe_load(f)
        items[item["id"]] = item
    return dict(sorted(items.items()))


def tokenize(title):
    """Lowercase, split on whitespace, strip punctuation, no stemming."""
    tokens = []
    for raw in title.lower().split():
        tok = raw.strip(string.punctuation)
        if tok:
            tokens.append(tok)
    return set(tokens)


def overlap(a, b):
    """Overlap coefficient: |A intersect B| / min(|A|, |B|)."""
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))
