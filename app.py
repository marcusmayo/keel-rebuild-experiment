#!/usr/bin/env python3
"""Phase 5: Flask web app — TOTP login, dashboard, reconciliation review,
status-change proposal/confirm, audit log, and Excel export."""

import os
import sys
import json
import secrets
import datetime
import yaml
import pyotp
from functools import wraps
from flask import (
    Flask, request, session, redirect, url_for, render_template_string,
    send_file, make_response, jsonify
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# --- TOTP Setup ---

def get_totp_secret():
    """Read or generate the TOTP secret, stored in .totp_secret."""
    secret_path = os.path.join(BASE, ".totp_secret")
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            return f.read().strip()
    # Generate new secret
    secret = pyotp.random_base32()
    with open(secret_path, "w") as f:
        f.write(secret)
    # Print the otpauth URL once
    otpauth = pyotp.totp.TOTP(secret).provisioning_uri(
        name="operator", issuer_name="MeridianPPM"
    )
    print(f"\n{'='*60}")
    print(f"TOTP secret generated. Provisioning URI:")
    print(f"  {otpauth}")
    print(f"Secret (base32): {secret}")
    print(f"{'='*60}\n")
    return secret

TOTP_SECRET = get_totp_secret()

# --- Auth decorator ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# --- Data loaders ---

def load_portfolio():
    state_dir = os.path.join(BASE, "state")
    items = []
    for fname in sorted(os.listdir(state_dir)):
        if fname.endswith(".yaml") or fname.endswith(".yml"):
            with open(os.path.join(state_dir, fname)) as f:
                items.append(yaml.safe_load(f))
    items.sort(key=lambda x: x["id"])
    return items

def load_reconcile():
    recon_path = os.path.join(BASE, "reconcile.json")
    if not os.path.exists(recon_path):
        return {"summary": {"buckets": {}, "unconfirmed": [], "unconfirmed_count": 0}, "results": []}
    with open(recon_path) as f:
        return json.load(f)

def load_proposals():
    proposals_dir = os.path.join(BASE, "proposals")
    proposals = []
    for fname in ["jira_proposals.json", "backlog_proposals.json"]:
        path = os.path.join(proposals_dir, fname)
        if os.path.exists(path):
            with open(path) as f:
                proposals.extend(json.load(f))
    return proposals

def get_pending_proposals():
    """Load pending status-change proposals from proposals_queue.json."""
    queue_path = os.path.join(BASE, "proposals_queue.json")
    if os.path.exists(queue_path):
        with open(queue_path) as f:
            return json.load(f)
    return []

def save_pending_proposals(proposals):
    queue_path = os.path.join(BASE, "proposals_queue.json")
    with open(queue_path, "w") as f:
        json.dump(proposals, f, indent=2)

def audit_log(action, details):
    """Append an audit line to logs/audit.log."""
    logs_dir = os.path.join(BASE, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    line = json.dumps({"timestamp": timestamp, "action": action, "details": details})
    with open(os.path.join(logs_dir, "audit.log"), "a") as f:
        f.write(line + "\n")


# --- Routes ---

@app.route("/")
def login_page():
    if session.get("authenticated"):
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_TEMPLATE)

@app.route("/login", methods=["POST"])
def login():
    code = request.form.get("code", "").strip()
    totp = pyotp.TOTP(TOTP_SECRET)
    if totp.verify(code):
        session["authenticated"] = True
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_TEMPLATE, error="Invalid TOTP code. Try again.")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/dashboard")
@login_required
def dashboard():
    recon = load_reconcile()
    summary = recon["summary"]
    buckets = summary["buckets"]
    unconfirmed_count = summary.get("unconfirmed_count", 0)

    # Order buckets
    bucket_order = ["changed", "gap", "conflict", "ambiguous", "duplicate", "completed", "done_gap"]
    bucket_data = []
    for b in bucket_order:
        bucket_data.append({"name": b, "count": buckets.get(b, 0)})

    return render_template_string(DASHBOARD_TEMPLATE,
                                  buckets=bucket_data,
                                  unconfirmed_count=unconfirmed_count,
                                  total_proposals=summary.get("total_proposals", 0))

@app.route("/items")
@login_required
def items():
    portfolio = load_portfolio()
    pending = {p["item_id"]: p for p in get_pending_proposals()}
    return render_template_string(ITEMS_TEMPLATE, items=portfolio, pending=pending)

@app.route("/reconciliation")
@login_required
def reconciliation():
    recon = load_reconcile()
    results = recon["results"]

    # Group by bucket
    bucket_order = ["changed", "conflict", "completed", "duplicate", "ambiguous", "gap", "done_gap"]
    grouped = {}
    for b in bucket_order:
        grouped[b] = [r for r in results if r["bucket"] == b]

    return render_template_string(RECON_TEMPLATE, grouped=grouped, bucket_order=bucket_order)

@app.route("/propose", methods=["POST"])
@login_required
def propose():
    item_id = request.form.get("item_id", "").strip()
    new_status = request.form.get("new_status", "").strip()

    if not item_id or not new_status:
        return jsonify({"error": "Missing item_id or new_status"}), 400

    # Load current item to verify it exists
    portfolio = {i["id"]: i for i in load_portfolio()}
    if item_id not in portfolio:
        return jsonify({"error": "Item not found"}), 404

    item = portfolio[item_id]
    proposal = {
        "item_id": item_id,
        "title": item["title"],
        "current_status": item["status"],
        "proposed_status": new_status,
        "proposed_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    # Store as pending (replace any existing proposal for same item)
    pending = get_pending_proposals()
    pending = [p for p in pending if p["item_id"] != item_id]
    pending.append(proposal)
    save_pending_proposals(pending)

    audit_log("propose", proposal)

    if request.headers.get("Accept") == "application/json":
        return jsonify({"status": "ok", "proposal": proposal})
    return redirect(url_for("items"))

@app.route("/confirm", methods=["POST"])
@login_required
def confirm():
    item_id = request.form.get("item_id", "").strip()

    if not item_id:
        return jsonify({"error": "Missing item_id"}), 400

    pending = get_pending_proposals()
    match = next((p for p in pending if p["item_id"] == item_id), None)
    if not match:
        return jsonify({"error": "No pending proposal for this item"}), 404

    # Apply the change to the YAML file
    state_path = os.path.join(BASE, "state", f"{item_id}.yaml")
    with open(state_path) as f:
        item = yaml.safe_load(f)

    item["status"] = match["proposed_status"]

    with open(state_path, "w") as f:
        yaml.dump(item, f)

    # Remove from pending
    pending = [p for p in pending if p["item_id"] != item_id]
    save_pending_proposals(pending)

    audit_log("confirm", {
        "item_id": item_id,
        "old_status": match["current_status"],
        "new_status": match["proposed_status"],
    })

    if request.headers.get("Accept") == "application/json":
        return jsonify({"status": "ok", "applied": match})
    return redirect(url_for("items"))

@app.route("/cancel-proposal", methods=["POST"])
@login_required
def cancel_proposal():
    item_id = request.form.get("item_id", "").strip()

    if not item_id:
        return jsonify({"error": "Missing item_id"}), 400

    pending = get_pending_proposals()
    match = next((p for p in pending if p["item_id"] == item_id), None)
    pending = [p for p in pending if p["item_id"] != item_id]
    save_pending_proposals(pending)

    audit_log("cancel_proposal", {"item_id": item_id, "cancelled": match})

    if request.headers.get("Accept") == "application/json":
        return jsonify({"status": "ok"})
    return redirect(url_for("items"))

@app.route("/export")
@login_required
def export_xlsx():
    import io
    recon = load_reconcile()
    results = recon["results"]
    portfolio = {i["id"]: i for i in load_portfolio()}

    wb = Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # --- Sheet 1: Cross-Source (matched rows, i.e. not gap, not done_gap) ---
    ws1 = wb.create_sheet("Cross-Source")
    ws1.append(["Ref", "Title", "Status", "Source", "Bucket", "Match Target", "Score",
                "Semantic Verdict", "Semantic Reason"])
    for r in results:
        if r["bucket"] not in ("gap", "done_gap", "ambiguous"):
            ws1.append([
                r.get("ref", ""), r["title"], r["status"], r["source"], r["bucket"],
                r.get("match_target", ""), r.get("match_score", ""),
                r.get("semantic_verdict", ""), r.get("semantic_reason", "")
            ])

    # --- Sheet 2: Source-Only (gap + done_gap) ---
    ws2 = wb.create_sheet("Source-Only")
    ws2.append(["Ref", "Title", "Status", "Source", "Bucket"])
    for r in results:
        if r["bucket"] in ("gap", "done_gap"):
            ws2.append([r.get("ref", ""), r["title"], r["status"], r["source"], r["bucket"]])

    # --- Sheet 3: Unconfirmed (unclaimed portfolio items) ---
    ws3 = wb.create_sheet("Unconfirmed")
    ws3.append(["ID", "Title", "Status"])
    unconfirmed_ids = recon["summary"].get("unconfirmed", [])
    for uid in unconfirmed_ids:
        if uid in portfolio:
            item = portfolio[uid]
            ws3.append([item["id"], item["title"], item["status"]])

    # --- Sheet 4: Semantic (judged ambiguous rows) ---
    ws4 = wb.create_sheet("Semantic")
    ws4.append(["Ref", "Title", "Status", "Source", "Bucket", "Match Target", "Score",
                "Semantic Verdict", "Semantic Reason"])
    for r in results:
        if r.get("semantic_verdict"):
            ws4.append([
                r.get("ref", ""), r["title"], r["status"], r["source"], r["bucket"],
                r.get("match_target", ""), r.get("match_score", ""),
                r.get("semantic_verdict", ""), r.get("semantic_reason", "")
            ])

    # Style headers
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for ws in [ws1, ws2, ws3, ws4]:
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
        ws.auto_filter.ref = ws.dimensions

    # Write to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="meridian_reconciliation.xlsx",
    )


# --- Templates ---

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Meridian PPM — Login</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #0f172a; color: #e2e8f0; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px;
            padding: 40px; width: 400px; max-width: 90vw; }
    h1 { font-size: 1.5rem; margin-bottom: 4px; color: #f8fafc; }
    .subtitle { color: #94a3b8; font-size: 0.85rem; margin-bottom: 24px; }
    input { width: 100%; padding: 12px; border: 1px solid #475569; border-radius: 8px;
            background: #0f172a; color: #e2e8f0; font-size: 1rem;
            text-align: center; letter-spacing: 4px; }
    input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.2); }
    button { width: 100%; padding: 12px; margin-top: 16px; background: #3b82f6; color: white;
             border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 600; }
    button:hover { background: #2563eb; }
    .error { color: #f87171; font-size: 0.85rem; margin-top: 12px; text-align: center; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Meridian PPM</h1>
    <p class="subtitle">Portfolio Reconciliation Agent</p>
    <form method="post" action="/login">
      <input type="text" name="code" placeholder="000000" maxlength="6" autocomplete="off" autofocus>
      <button type="submit">Authenticate</button>
    </form>
    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}
  </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Meridian PPM — Dashboard</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #0f172a; color: #e2e8f0; min-height: 100vh; }
    nav { background: #1e293b; border-bottom: 1px solid #334155; padding: 0 24px;
          display: flex; align-items: center; height: 56px; }
    nav .brand { font-weight: 700; font-size: 1.1rem; color: #f8fafc; }
    nav .links { margin-left: auto; display: flex; gap: 16px; }
    nav a { color: #94a3b8; text-decoration: none; font-size: 0.9rem; }
    nav a:hover, nav a.active { color: #e2e8f0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
    h1 { font-size: 1.5rem; margin-bottom: 24px; color: #f8fafc; }
    .hero-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                 gap: 16px; margin-bottom: 32px; }
    .hero-card { background: #1e293b; border: 1px solid #334155; border-radius: 10px;
                 padding: 20px; text-align: center; }
    .hero-card .count { font-size: 2.2rem; font-weight: 700; }
    .hero-card .label { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase;
                        letter-spacing: 1px; margin-top: 4px; }
    .hero-card.changed .count { color: #f59e0b; }
    .hero-card.gap .count { color: #ef4444; }
    .hero-card.conflict .count { color: #f97316; }
    .hero-card.ambiguous .count { color: #a855f7; }
    .hero-card.duplicate .count { color: #6366f1; }
    .hero-card.completed .count { color: #22c55e; }
    .hero-card.done_gap .count { color: #64748b; }
    .hero-card.unconfirmed .count { color: #94a3b8; }
    .export-section { text-align: right; margin-bottom: 16px; }
    .btn { display: inline-block; padding: 10px 20px; background: #3b82f6; color: white;
           border: none; border-radius: 8px; font-size: 0.9rem; cursor: pointer;
           text-decoration: none; font-weight: 600; }
    .btn:hover { background: #2563eb; }
  </style>
</head>
<body>
  <nav>
    <span class="brand">Meridian PPM</span>
    <div class="links">
      <a href="/dashboard" class="active">Dashboard</a>
      <a href="/items">Work Items</a>
      <a href="/reconciliation">Reconciliation</a>
      <a href="/export">Export</a>
      <a href="/logout">Logout</a>
    </div>
  </nav>
  <div class="container">
    <h1>Reconciliation Dashboard</h1>
    <div class="hero-grid">
      {% for b in buckets %}
      <div class="hero-card {{ b.name }}">
        <div class="count">{{ b.count }}</div>
        <div class="label">{{ b.name }}</div>
      </div>
      {% endfor %}
      <div class="hero-card unconfirmed">
        <div class="count">{{ unconfirmed_count }}</div>
        <div class="label">unconfirmed</div>
      </div>
    </div>
    <div class="export-section">
      <a href="/export" class="btn">Download Excel Workbook</a>
    </div>
  </div>
</body>
</html>
"""

ITEMS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Meridian PPM — Work Items</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #0f172a; color: #e2e8f0; min-height: 100vh; }
    nav { background: #1e293b; border-bottom: 1px solid #334155; padding: 0 24px;
          display: flex; align-items: center; height: 56px; }
    nav .brand { font-weight: 700; font-size: 1.1rem; color: #f8fafc; }
    nav .links { margin-left: auto; display: flex; gap: 16px; }
    nav a { color: #94a3b8; text-decoration: none; font-size: 0.9rem; }
    nav a:hover, nav a.active { color: #e2e8f0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
    h1 { font-size: 1.5rem; margin-bottom: 24px; color: #f8fafc; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #1e293b; }
    th { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8;
         background: #1e293b; position: sticky; top: 0; }
    tr:hover { background: #1e293b; }
    .status-badge { display: inline-block; padding: 3px 10px; border-radius: 20px;
                    font-size: 0.8rem; font-weight: 600; }
    .status-done { background: #14532d; color: #4ade80; }
    .status-in_progress { background: #1e3a5f; color: #60a5fa; }
    .status-blocked { background: #451a03; color: #fbbf24; }
    .propose-form { display: flex; gap: 6px; align-items: center; }
    .propose-form select { padding: 4px 8px; background: #1e293b; color: #e2e8f0;
                           border: 1px solid #475569; border-radius: 4px; font-size: 0.8rem; }
    .propose-form button { padding: 4px 10px; background: #3b82f6; color: white;
                           border: none; border-radius: 4px; font-size: 0.8rem; cursor: pointer; }
    .propose-form button:hover { background: #2563eb; }
    .btn-confirm { background: #22c55e !important; }
    .btn-confirm:hover { background: #16a34a !important; }
    .btn-cancel { background: #ef4444 !important; }
    .btn-cancel:hover { background: #dc2626 !important; }
    .pending-row { background: #172554; }
    .pending-info { font-size: 0.75rem; color: #fbbf24; }
  </style>
</head>
<body>
  <nav>
    <span class="brand">Meridian PPM</span>
    <div class="links">
      <a href="/dashboard">Dashboard</a>
      <a href="/items" class="active">Work Items</a>
      <a href="/reconciliation">Reconciliation</a>
      <a href="/export">Export</a>
      <a href="/logout">Logout</a>
    </div>
  </nav>
  <div class="container">
    <h1>Work Items (Portfolio)</h1>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Title</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for item in items %}
        <tr class="{% if item.id in pending %}pending-row{% endif %}">
          <td><strong>{{ item.id }}</strong></td>
          <td>{{ item.title }}</td>
          <td>
            <span class="status-badge status-{{ item.status }}">
              {{ item.status }}
            </span>
            {% if item.id in pending %}
            <br><span class="pending-info">→ proposed: {{ pending[item.id].proposed_status }}</span>
            {% endif %}
          </td>
          <td>
            {% if item.id not in pending %}
            <form class="propose-form" method="post" action="/propose">
              <input type="hidden" name="item_id" value="{{ item.id }}">
              <select name="new_status">
                <option value="in_progress">in_progress</option>
                <option value="blocked">blocked</option>
                <option value="done">done</option>
              </select>
              <button type="submit">Propose</button>
            </form>
            {% else %}
            <form class="propose-form" method="post" action="/confirm" style="display:inline;">
              <input type="hidden" name="item_id" value="{{ item.id }}">
              <button type="submit" class="btn-confirm">Confirm</button>
            </form>
            <form class="propose-form" method="post" action="/cancel-proposal" style="display:inline;">
              <input type="hidden" name="item_id" value="{{ item.id }}">
              <button type="submit" class="btn-cancel">Cancel</button>
            </form>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</body>
</html>
"""

RECON_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Meridian PPM — Reconciliation</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #0f172a; color: #e2e8f0; min-height: 100vh; }
    nav { background: #1e293b; border-bottom: 1px solid #334155; padding: 0 24px;
          display: flex; align-items: center; height: 56px; }
    nav .brand { font-weight: 700; font-size: 1.1rem; color: #f8fafc; }
    nav .links { margin-left: auto; display: flex; gap: 16px; }
    nav a { color: #94a3b8; text-decoration: none; font-size: 0.9rem; }
    nav a:hover, nav a.active { color: #e2e8f0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
    h1 { font-size: 1.5rem; margin-bottom: 24px; color: #f8fafc; }
    .bucket-section { margin-bottom: 32px; }
    .bucket-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
    .bucket-header h2 { font-size: 1.1rem; color: #f8fafc; }
    .bucket-count { background: #334155; padding: 2px 10px; border-radius: 12px;
                    font-size: 0.8rem; color: #94a3b8; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
    th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #1e293b; font-size: 0.85rem; }
    th { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8;
         background: #1e293b; }
    tr:hover { background: #1e293b; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 20px;
             font-size: 0.7rem; font-weight: 600; }
    .badge-changed { background: #451a03; color: #f59e0b; }
    .badge-conflict { background: #431407; color: #f97316; }
    .badge-completed { background: #14532d; color: #4ade80; }
    .badge-duplicate { background: #1e1b4b; color: #818cf8; }
    .badge-ambiguous { background: #2e1065; color: #c084fc; }
    .badge-gap { background: #450a0a; color: #f87171; }
    .badge-done_gap { background: #1e293b; color: #64748b; }
    .verdict { font-size: 0.8rem; margin-top: 2px; }
    .verdict-SAME { color: #4ade80; }
    .verdict-DISTINCT { color: #f87171; }
    .verdict-SKIPPED { color: #94a3b8; }
  </style>
</head>
<body>
  <nav>
    <span class="brand">Meridian PPM</span>
    <div class="links">
      <a href="/dashboard">Dashboard</a>
      <a href="/items">Work Items</a>
      <a href="/reconciliation" class="active">Reconciliation</a>
      <a href="/export">Export</a>
      <a href="/logout">Logout</a>
    </div>
  </nav>
  <div class="container">
    <h1>Reconciliation Review</h1>
    {% for bucket_name in bucket_order %}
    {% set rows = grouped.get(bucket_name, []) %}
    {% if rows %}
    <div class="bucket-section">
      <div class="bucket-header">
        <h2>{{ bucket_name }}</h2>
        <span class="bucket-count">{{ rows|length }} row{{ 's' if rows|length != 1 else '' }}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Ref</th>
            <th>Title</th>
            <th>Status</th>
            <th>Source</th>
            <th>Match Target</th>
            <th>Score</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
          <tr>
            <td>{{ row.get('ref', '') or '—' }}</td>
            <td>{{ row.title }}</td>
            <td><span class="badge badge-{{ row.status }}">{{ row.status }}</span></td>
            <td>{{ row.source }}</td>
            <td>{{ row.get('match_target', '—') or '—' }}</td>
            <td>{{ row.get('match_score', '') }}</td>
            <td>
              {% if row.get('semantic_verdict') %}
              <span class="verdict verdict-{{ row.semantic_verdict }}">
                {{ row.semantic_verdict }}
              </span>
              <br><small style="color:#94a3b8;">{{ row.semantic_reason }}</small>
              {% else %}
              —
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% endif %}
    {% endfor %}
  </div>
</body>
</html>
"""


def main():
    port = int(os.environ.get("PORT", 8000))
    print(f"\nStarting Meridian PPM on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()