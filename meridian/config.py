"""Shared configuration, paths, and constants for Meridian PPM.

All matching thresholds and canonical filesystem locations live here so that
every stage of the pipeline agrees on the same deterministic layout.
"""
from __future__ import annotations

import os
from pathlib import Path

# Project root is the parent of this package directory.
ROOT = Path(__file__).resolve().parent.parent

# Canonical directories (one YAML per work item; human-readable record system).
STATE_DIR = ROOT / "state"
IMPORTS_DIR = ROOT / "imports"
PROPOSALS_DIR = ROOT / "proposals"
REPORTS_DIR = ROOT / "reports"
LOGS_DIR = ROOT / "logs"

# Canonical file locations.
JIRA_CSV = IMPORTS_DIR / "jira_export.csv"
BACKLOG_XLSX = IMPORTS_DIR / "backlog_export.xlsx"
JIRA_PROPOSALS = PROPOSALS_DIR / "jira_proposals.json"
BACKLOG_PROPOSALS = PROPOSALS_DIR / "backlog_proposals.json"
RECONCILE_JSON = REPORTS_DIR / "reconcile.json"
SCORES_JSON = REPORTS_DIR / "scores.json"
EXPORT_XLSX = REPORTS_DIR / "meridian_export.xlsx"
AUDIT_LOG = LOGS_DIR / "audit.log"
TOTP_SECRET_FILE = ROOT / ".totp_secret"

# Title-match thresholds (overlap coefficient on normalized token sets).
HIGH = 0.80
LOW = 0.40

# Statuses that count as "the work is finished".
DONE_STATUSES = {"done"}

# LLM configuration is read from the environment (a .env file is provided).
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
LLM_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")


def ensure_dirs() -> None:
    """Create the writable output directories if they do not yet exist.

    Never touches STATE_DIR or IMPORTS_DIR contents.
    """
    for d in (PROPOSALS_DIR, REPORTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
