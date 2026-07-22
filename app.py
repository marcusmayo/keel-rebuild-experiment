#!/usr/bin/env python3
"""Meridian PPM -- operator web console (Flask, port 8000).

Screens behind TOTP login:
  - dashboard: bucket counts as hero numbers + unconfirmed count.
  - work items: all portfolio items.
  - reconciliation review: rows grouped by bucket, showing semantic verdicts.
  - status-change flow: strictly propose-then-confirm; every confirm appends an
    audit line to logs/audit.log.
  - export: downloads the four-sheet XLSX.

Product rules honored here: propose don't mutate (status changes go through an
explicit confirm), and there is NO delete affordance anywhere.
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from meridian.auth import ensure_secret, verify_code, provisioning_uri
from meridian.config import RECONCILE_JSON, AUDIT_LOG, EXPORT_XLSX, ensure_dirs
from meridian.export import build_workbook
from meridian.portfolio import load_portfolio, get_item, update_status

app = Flask(__name__)
app.secret_key = os.environ.get("MERIDIAN_SECRET_KEY", "meridian-dev-secret-key")

BUCKET_ORDER = [
    "changed",
    "gap",
    "conflict",
    "ambiguous",
    "duplicate",
    "completed",
    "done_gap",
]

# Allowed statuses for the propose-then-confirm flow (no delete).
ALLOWED_STATUSES = ["in_progress", "blocked", "done", "on_hold"]


@app.context_processor
def inject_globals():
    return {"show_nav": is_authed()}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_report():
    if RECONCILE_JSON.exists():
        with RECONCILE_JSON.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    return {"summary": {"buckets": {}, "unconfirmed": [],
                        "unconfirmed_count": 0, "total": 0}, "rows": []}


def is_authed() -> bool:
    return bool(session.get("authed"))


def require_auth():
    if not is_authed():
        return redirect(url_for("login"))
    return None


def append_audit(line: str) -> None:
    ensure_dirs()
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{ts} {line}\n")


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    secret = ensure_secret()
    if request.method == "POST":
        code = request.form.get("code", "")
        if verify_code(secret, code):
            session["authed"] = True
            return redirect(url_for("dashboard"))
        error = "Invalid authentication code."
    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@app.route("/")
def dashboard():
    guard = require_auth()
    if guard:
        return guard
    report = load_report()
    counts = report["summary"].get("buckets", {})
    hero = [(b, counts.get(b, 0)) for b in BUCKET_ORDER]
    return render_template(
        "dashboard.html",
        hero=hero,
        total=report["summary"].get("total", 0),
        unconfirmed_count=report["summary"].get("unconfirmed_count", 0),
        active="dashboard",
    )


# --------------------------------------------------------------------------- #
# Work items
# --------------------------------------------------------------------------- #
@app.route("/work-items")
def work_items():
    guard = require_auth()
    if guard:
        return guard
    items = load_portfolio()
    report = load_report()
    unconfirmed = set(report["summary"].get("unconfirmed", []))
    return render_template(
        "work_items.html",
        items=items,
        unconfirmed=unconfirmed,
        active="work_items",
    )


# --------------------------------------------------------------------------- #
# Reconciliation review (grouped by bucket)
# --------------------------------------------------------------------------- #
@app.route("/review")
def review():
    guard = require_auth()
    if guard:
        return guard
    report = load_report()
    grouped = {b: [] for b in BUCKET_ORDER}
    for r in report.get("rows", []):
        grouped.setdefault(r["bucket"], []).append(r)
    counts = report["summary"].get("buckets", {})
    return render_template(
        "review.html",
        grouped=grouped,
        bucket_order=BUCKET_ORDER,
        counts=counts,
        unconfirmed=report["summary"].get("unconfirmed", []),
        active="review",
    )


# --------------------------------------------------------------------------- #
# Status-change flow: propose -> confirm
# --------------------------------------------------------------------------- #
@app.route("/status/<item_id>", methods=["GET"])
def status_form(item_id):
    guard = require_auth()
    if guard:
        return guard
    item = get_item(item_id)
    if item is None:
        abort(404)
    return render_template(
        "status_form.html",
        item=item,
        statuses=ALLOWED_STATUSES,
        active="work_items",
    )


@app.route("/status/<item_id>/propose", methods=["POST"])
def status_propose(item_id):
    guard = require_auth()
    if guard:
        return guard
    item = get_item(item_id)
    if item is None:
        abort(404)
    new_status = request.form.get("new_status", "").strip()
    if new_status not in ALLOWED_STATUSES:
        abort(400)
    # Propose only: show a confirmation page. Nothing is written yet.
    return render_template(
        "status_confirm.html",
        item=item,
        new_status=new_status,
        active="work_items",
    )


@app.route("/status/<item_id>/confirm", methods=["POST"])
def status_confirm(item_id):
    guard = require_auth()
    if guard:
        return guard
    item = get_item(item_id)
    if item is None:
        abort(404)
    new_status = request.form.get("new_status", "").strip()
    if new_status not in ALLOWED_STATUSES:
        abort(400)
    old_status = item["status"]
    # Apply the change (the only sanctioned mutation) and audit it.
    update_status(item_id, new_status)
    append_audit(
        f"STATUS_CHANGE item={item_id} from={old_status} to={new_status} "
        f"operator={ACCOUNT_LABEL}"
    )
    return render_template(
        "status_done.html",
        item=get_item(item_id),
        old_status=old_status,
        active="work_items",
    )


ACCOUNT_LABEL = "operator"


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
@app.route("/export")
def export():
    guard = require_auth()
    if guard:
        return guard
    report = load_report()
    wb = build_workbook(report)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    # Also persist a copy to reports/ for the oracle.
    ensure_dirs()
    wb.save(EXPORT_XLSX)
    return send_file(
        buf,
        as_attachment=True,
        download_name="meridian_export.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


if __name__ == "__main__":
    ensure_dirs()
    secret = ensure_secret()
    # Print the provisioning URL once at startup for operator convenience.
    print("Meridian PPM operator console")
    print(f"otpauth URL: {provisioning_uri(secret)}")
    app.run(host="0.0.0.0", port=8000, debug=False)
