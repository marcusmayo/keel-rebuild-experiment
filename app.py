"""Phase 5 -- Meridian PPM operator web app (Flask, port 8000).

TOTP-gated dashboard, work items table, reconciliation review, and a
strictly propose-then-confirm status change flow with an audit log.
Propose, don't mutate: nothing changes until the operator confirms.
There is NO delete anywhere in this product.
"""
import datetime
import functools
import json
import os

import pyotp
import yaml
from flask import (Flask, abort, redirect, render_template, request,
                   send_file, session, url_for)
import io

from common import (BUCKET_ORDER, LOGS_DIR, RECONCILE_PATH, ROOT,
                    STATE_DIR, load_portfolio)
from export import build_bytes
from setup_totp import ensure_secret

app = Flask(__name__)

TOTP_SECRET, _ = ensure_secret()
app.secret_key = TOTP_SECRET  # stable across restarts, file is 0600
STATUSES = ["in_progress", "blocked", "done"]


# ---------------------------------------------------------------- auth
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authed"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        code = (request.form.get("code") or "").strip().replace(" ", "")
        if pyotp.TOTP(TOTP_SECRET).verify(code, valid_window=1):
            session["authed"] = True
            return redirect(url_for("dashboard"))
        error = "Invalid code. Try again."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------ dashboard
def load_reconcile():
    if not os.path.exists(RECONCILE_PATH):
        return None
    with open(RECONCILE_PATH) as f:
        return json.load(f)


@app.route("/")
@login_required
def dashboard():
    data = load_reconcile()
    counts = {b: 0 for b in BUCKET_ORDER}
    unconfirmed = 0
    if data:
        counts.update(data["summary"]["buckets"])
        unconfirmed = len(data["summary"]["unconfirmed"])
    return render_template("dashboard.html", counts=counts,
                           unconfirmed=unconfirmed,
                           has_data=data is not None)


# ----------------------------------------------------------- work items
@app.route("/items")
@login_required
def items():
    portfolio = load_portfolio()
    return render_template("items.html", items=portfolio.values(),
                           statuses=STATUSES)


@app.route("/items/<item_id>/propose", methods=["POST"])
@login_required
def propose(item_id):
    portfolio = load_portfolio()
    if item_id not in portfolio:
        abort(404)
    new_status = request.form.get("status", "")
    if new_status not in STATUSES:
        abort(400)
    item = portfolio[item_id]
    if new_status == item["status"]:
        return redirect(url_for("items"))
    # Propose only: nothing is written. Stored in the session until the
    # operator explicitly confirms.
    session["pending"] = {"id": item_id, "title": item["title"],
                          "from": item["status"], "to": new_status}
    return redirect(url_for("confirm"))


@app.route("/items/confirm", methods=["GET", "POST"])
@login_required
def confirm():
    pending = session.get("pending")
    if not pending:
        return redirect(url_for("items"))
    if request.method == "POST":
        if request.form.get("decision") == "confirm":
            path = os.path.join(STATE_DIR, f"{pending['id']}.yaml")
            with open(path) as f:
                item = yaml.safe_load(f)
            item["status"] = pending["to"]
            with open(path, "w") as f:
                yaml.safe_dump(item, f, sort_keys=False)
            os.makedirs(LOGS_DIR, exist_ok=True)
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with open(os.path.join(LOGS_DIR, "audit.log"), "a") as f:
                f.write(f"{ts} status-change {pending['id']} "
                        f"{pending['from']} -> {pending['to']} "
                        f"confirmed by operator\n")
        session.pop("pending", None)
        return redirect(url_for("items"))
    return render_template("confirm.html", pending=pending)


# ------------------------------------------------------- reconciliation
@app.route("/reconciliation")
@login_required
def reconciliation():
    data = load_reconcile()
    if data is None:
        abort(503)
    grouped = {b: [] for b in BUCKET_ORDER}
    for row in data["rows"]:
        grouped[row["bucket"]].append(row)
    return render_template("reconciliation.html", grouped=grouped,
                           summary=data["summary"], order=BUCKET_ORDER)


# -------------------------------------------------------------- export
@app.route("/export")
@login_required
def export():
    if not os.path.exists(RECONCILE_PATH):
        abort(503)
    payload = build_bytes()
    return send_file(io.BytesIO(payload),
                     mimetype="application/vnd.openxmlformats-"
                              "officedocument.spreadsheetml.sheet",
                     as_attachment=True,
                     download_name="meridian_reconciliation.xlsx")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
