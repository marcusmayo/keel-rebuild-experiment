"""Phase 5 -- Operator web app.

Flask app on port 8000 behind TOTP login. Screens: dashboard (bucket counts
as hero numbers, unconfirmed count), work items table, reconciliation review
grouped by bucket with semantic verdicts, and a status-change flow that is
strictly propose-then-confirm with an audit line appended on every confirm.
An Export button downloads the four-sheet workbook.

The operator decides; the tool never decides for them. Work items are only
created or updated in place, and that is the entire lifecycle.
"""
from __future__ import annotations

import datetime
import io
from pathlib import Path

import pyotp
from flask import (
    Flask, flash, g, redirect, render_template, request, send_file, session, url_for,
)

from . import config
from .export import build_workbook
from .portfolio import load_portfolio, load_portfolio_map, save_item
from .reconcile import load_reconcile
from .setup import ensure_secrets

STATUSES = ["in_progress", "blocked", "done"]


def _totp() -> pyotp.TOTP:
    secret, _uri, _generated = ensure_secrets()
    return pyotp.TOTP(secret)


def create_app() -> Flask:
    secret, _uri, _generated = ensure_secrets()
    app = Flask(
        __name__,
        template_folder=str(config.TEMPLATES_DIR),
        static_folder=str(config.STATIC_DIR),
    )
    app.secret_key = config.FLASK_SECRET_FILE.read_text().strip()

    @app.before_request
    def require_login():
        if request.endpoint in ("login", "static"):
            return None
        if not session.get("logged_in"):
            return redirect(url_for("login"))

    @app.context_processor
    def inject_globals():
        return {"buckets_order": config.BUCKETS}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("logged_in"):
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            code = request.form.get("code", "").strip()
            if code and _totp().verify(code, valid_window=1):
                session["logged_in"] = True
                return redirect(url_for("dashboard"))
            flash("Invalid TOTP code.", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    def dashboard():
        rec = load_reconcile()
        summary = rec.get("summary", {})
        return render_template("dashboard.html", summary=summary)

    @app.route("/items")
    def items():
        portfolio = load_portfolio()
        # Attach any stored WSJF score for display.
        scores = {}
        for sf in config.SCORES_DIR.glob("*.json") if config.SCORES_DIR.exists() else []:
            try:
                import json
                rec = json.loads(sf.read_text())
                scores[rec["item"]] = rec
            except Exception:  # noqa: BLE001
                pass
        for it in portfolio:
            it["_score"] = scores.get(it["id"])
        return render_template("items.html", items=portfolio)

    @app.route("/items/<item_id>", methods=["GET"])
    def item_detail(item_id):
        item = load_portfolio_map().get(item_id)
        if not item:
            flash("Item not found.", "error")
            return redirect(url_for("items"))
        return render_template("item_detail.html", item=item, statuses=STATUSES)

    @app.route("/items/<item_id>/propose", methods=["POST"])
    def propose_status(item_id):
        item = load_portfolio_map().get(item_id)
        if not item:
            flash("Item not found.", "error")
            return redirect(url_for("items"))
        new_status = request.form.get("status", "").strip()
        if new_status not in STATUSES:
            flash("Invalid status.", "error")
            return redirect(url_for("item_detail", item_id=item_id))
        # Store the pending proposal in the session only -- nothing on disk changes.
        session["pending"] = {
            "id": item_id,
            "old_status": item["status"],
            "new_status": new_status,
        }
        return render_template("confirm.html", item=item, new_status=new_status)

    @app.route("/items/<item_id>/confirm", methods=["POST"])
    def confirm_status(item_id):
        pending = session.get("pending")
        if not pending or pending.get("id") != item_id:
            flash("No pending proposal for this item. Propose a change first.", "error")
            return redirect(url_for("item_detail", item_id=item_id))
        item = load_portfolio_map().get(item_id)
        if not item:
            flash("Item not found.", "error")
            return redirect(url_for("items"))
        old_status = item["status"]
        new_status = pending["new_status"]
        item["status"] = new_status
        save_item(item)  # persisted only after explicit confirmation

        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        actor = session.get("user", "operator")
        with open(config.AUDIT_LOG, "a") as fh:
            fh.write(f"{ts}\t{actor}\t{item_id}\t{old_status}->{new_status}\tconfirmed\n")

        session.pop("pending", None)
        flash(f"Confirmed: {item_id} status is now {new_status}.", "success")
        return redirect(url_for("item_detail", item_id=item_id))

    @app.route("/review")
    def review():
        rec = load_reconcile()
        rows = rec.get("rows", [])
        by_bucket: dict[str, list] = {b: [] for b in config.BUCKETS}
        for r in rows:
            by_bucket.setdefault(r["bucket"], []).append(r)
        return render_template("review.html", by_bucket=by_bucket, summary=rec.get("summary", {}))

    @app.route("/export")
    def export():
        wb = build_workbook()
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name="reconciliation_review.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    return app


app = create_app()


if __name__ == "__main__":
    secret, uri, generated = ensure_secrets()
    if generated:
        print("New TOTP secret generated.")
    print("otpauth URL:", uri)
    print("Starting Meridian PPM web app on http://0.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000)
