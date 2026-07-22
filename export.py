"""Phase 5 -- Excel export.

Builds one XLSX workbook with exactly four sheets from reconcile.json
and the portfolio:
  Cross-Source  -- the matched rows (changed/conflict/completed/duplicate)
  Source-Only   -- gap + done_gap rows
  Unconfirmed   -- portfolio items no source row claimed
  Semantic      -- the judged ambiguous rows (verdict + reason)

Pure deterministic code; used both by the CLI and the web Export button.
"""
import argparse
import io
import json
import os

from openpyxl import Workbook

from common import EXPORTS_DIR, RECONCILE_PATH, load_portfolio

MATCHED_BUCKETS = ("changed", "conflict", "completed", "duplicate")
SOURCE_ONLY_BUCKETS = ("gap", "done_gap")


def build_workbook(reconcile_path=RECONCILE_PATH):
    with open(reconcile_path) as f:
        data = json.load(f)
    portfolio = load_portfolio()
    rows = data["rows"]

    wb = Workbook()

    ws = wb.active
    ws.title = "Cross-Source"
    ws.append(["ref", "title", "status", "source", "bucket", "match", "score"])
    for r in rows:
        if r["bucket"] in MATCHED_BUCKETS:
            ws.append([r["ref"], r["title"], r["status"], r["source"],
                       r["bucket"], r["match"], r["score"]])

    ws = wb.create_sheet("Source-Only")
    ws.append(["ref", "title", "status", "source", "bucket"])
    for r in rows:
        if r["bucket"] in SOURCE_ONLY_BUCKETS:
            ws.append([r["ref"], r["title"], r["status"], r["source"],
                       r["bucket"]])

    ws = wb.create_sheet("Unconfirmed")
    ws.append(["id", "title", "status"])
    for pid in data["summary"]["unconfirmed"]:
        item = portfolio[pid]
        ws.append([item["id"], item["title"], item["status"]])

    ws = wb.create_sheet("Semantic")
    ws.append(["title", "status", "source", "match", "score", "verdict",
               "reason"])
    for r in rows:
        if r["bucket"] == "ambiguous":
            ws.append([r["title"], r["status"], r["source"], r["match"],
                       r["score"], r.get("verdict", ""), r.get("reason", "")])

    return wb


def build_bytes(reconcile_path=RECONCILE_PATH):
    buf = io.BytesIO()
    build_workbook(reconcile_path).save(buf)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        EXPORTS_DIR, "reconciliation_export.xlsx"))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    wb = build_workbook()
    wb.save(args.out)
    counts = {ws.title: ws.max_row - 1 for ws in wb.worksheets}
    print(f"Wrote {args.out}: " +
          " ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
