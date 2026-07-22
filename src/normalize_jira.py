"""Phase 2 -- Read-only normalization of the Jira CSV export.

Maps each Jira row into a canonical proposal record (ref, title, status,
source) written to proposals/jira/<seq>.json. Never touches state/.
"""
from __future__ import annotations

import csv
import json

from . import config
from .generate import JIRA_CSV

OUT_DIR = config.PROPOSALS_DIR / "jira"


def normalize_jira() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(JIRA_CSV, newline="") as fh:
        reader = csv.DictReader(fh)
        for seq, row in enumerate(reader, start=1):
            record = {
                "source": "jira",
                "seq": seq,
                "ref": (row.get("ref") or "").strip(),
                "title": (row.get("title") or "").strip(),
                "status": (row.get("status") or "").strip(),
            }
            with open(OUT_DIR / f"{seq:04d}.json", "w") as out:
                json.dump(record, out, indent=2, sort_keys=True, ensure_ascii=False)
                out.write("\n")
            count += 1
    return count


if __name__ == "__main__":
    print(f"Normalized {normalize_jira()} Jira proposals.")
