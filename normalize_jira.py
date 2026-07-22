"""Phase 2 -- normalize the Jira CSV export into canonical proposals.

Read-only with respect to state/: only writes proposals/jira.json.
Canonical record: {ref, title, status, source}.
"""
import csv
import json
import os

from common import IMPORTS_DIR, PROPOSALS_DIR


def main():
    src = os.path.join(IMPORTS_DIR, "jira_export.csv")
    proposals = []
    with open(src, newline="") as f:
        for row in csv.DictReader(f):
            proposals.append({
                "ref": (row.get("ref") or "").strip(),
                "title": (row.get("title") or "").strip(),
                "status": (row.get("status") or "").strip(),
                "source": "jira",
            })
    os.makedirs(PROPOSALS_DIR, exist_ok=True)
    out = os.path.join(PROPOSALS_DIR, "jira.json")
    with open(out, "w") as f:
        json.dump(proposals, f, indent=2)
        f.write("\n")
    print(f"Wrote {len(proposals)} jira proposals to {out}")


if __name__ == "__main__":
    main()
