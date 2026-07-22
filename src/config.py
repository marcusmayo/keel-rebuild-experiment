"""Paths, constants, and environment loading for Meridian PPM."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATE_DIR = ROOT / "state"
IMPORTS_DIR = ROOT / "imports"
PROPOSALS_DIR = ROOT / "proposals"
RECONCILE_FILE = ROOT / "reconcile.json"
SCORES_DIR = ROOT / "scores"
EXPORTS_DIR = ROOT / "exports"
LOGS_DIR = ROOT / "logs"
AUDIT_LOG = LOGS_DIR / "audit.log"
SECRETS_DIR = ROOT / "secrets"
TOTP_SECRET_FILE = SECRETS_DIR / "totp_secret"
FLASK_SECRET_FILE = SECRETS_DIR / "flask_secret"

TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

# Title-matching thresholds for the overlap coefficient.
HIGH = 0.80
LOW = 0.40

# Canonical bucket order used across reports and the UI.
BUCKETS = [
    "changed",
    "conflict",
    "completed",
    "duplicate",
    "ambiguous",
    "gap",
    "done_gap",
]

# Buckets whose rows have a match target in the portfolio (the "Cross-Source" set).
MATCHED_BUCKETS = ["changed", "conflict", "completed", "duplicate"]
# Buckets whose rows match nothing in the portfolio (the "Source-Only" set).
UNMATCHED_BUCKETS = ["gap", "done_gap"]

EXPORT_FILE = EXPORTS_DIR / "reconciliation_review.xlsx"


def load_env() -> None:
    """Load variables from a .env file at the repo root into os.environ.

    Existing environment variables take precedence (setdefault), so an
    operator who exports variables in the shell wins over the file.
    """
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


load_env()

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
