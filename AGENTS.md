# Meridian PPM -- a portfolio reconciliation agent

## What we are building

Meridian Logistics runs a project portfolio in a simple, human-readable system:
one YAML file per work item. But the truth keeps drifting: the engineering team
lives in Jira, and a planning analyst keeps a separate backlog spreadsheet.
Every week someone has to eyeball three sources and guess what changed.

We are building Meridian PPM: a small self-hosted tool that ingests the two
external exports, compares them against the portfolio, sorts every source row
into a named review bucket, asks an AI model to judge ONLY the genuinely
ambiguous matches, proposes scores, and gives the operator a protected web
screen and an Excel workbook to review it all. The operator decides; the tool
never decides for them.

## Look and feel

Clean, dense, operator-grade. A dark dashboard with the bucket counts as the
hero numbers, a work-items table, a reconciliation review screen grouped by
bucket, and one-click Excel export. No marketing gloss, no onboarding tour.
It should feel like a cockpit, not a brochure.

## Product rules (non-negotiable)

1. Propose, don't mutate. Nothing changes a work item directly. Status changes
   are written as proposals and applied only after an explicit operator
   confirmation step. There is NO delete anywhere in the product -- no delete
   endpoint, no delete button, no delete code path.
2. Deterministic first. The AI model is consulted in exactly two places:
   judging the ambiguous bucket, and proposing scoring factors. Everything
   else -- parsing, matching, bucketing, arithmetic, export -- is plain
   deterministic code that produces identical output on identical input.
3. Read-only ingestion. Normalization and reconciliation never write to the
   portfolio; they only produce proposal and report files.
4. Every model verdict is stored with its reason, and scores are always
   recomputable from their stored factors by pure arithmetic.

## Technical guardrails (keep the model on rails -- the only technical section)

- Python 3.11+, Flask for the web app, PyYAML, openpyxl, pyotp. SQLite is NOT
  used: the portfolio is one YAML file per item in `state/`, exactly because a
  human must be able to read the record system in a text editor.
- The AI model is called over an OpenAI-compatible chat-completions HTTP API.
  Read `LLM_BASE_URL` (default `https://openrouter.ai/api/v1`),
  `OPENROUTER_API_KEY`, and `LLM_MODEL` from the environment (a `.env` file is
  provided). Both AI touchpoints must also run with `--no-llm` to skip the
  model for deterministic testing.
- Title matching uses the overlap coefficient on normalized token sets:
  lowercase the title, split on whitespace, strip punctuation, no stemming.
  overlap = |A intersect B| / min(|A|,|B|). Thresholds: HIGH = 0.80,
  LOW = 0.40.
- The web app listens on port 8000. Everything runs headless inside this dev
  container. Ship `run_e2e.sh` (one command, whole pipeline + oracle) and
  `verify_e2e.py` (the oracle that asserts the exact numbers in this brief).

## Matching and bucket rules

A source row is matched by ref first: if its ref equals a portfolio item's id,
they match regardless of title. A row with no ref is matched by title: its best
overlap score against all portfolio titles. Score >= HIGH is a match; score
< LOW is no match; in between is held as ambiguous. Each source row lands in
exactly one bucket:

- changed: matched, portfolio status is not done, and the row's status or
  title differs from the portfolio.
- conflict: matched, portfolio status IS done, and the row says the work is
  still active. The portfolio claims completion; the source disagrees.
- completed: matched, both sides done, nothing drifted.
- duplicate: the row's best match is a portfolio item already claimed by
  another source row (by ref or at >= HIGH).
- ambiguous: no ref, best score strictly between LOW and HIGH. Held for the
  model's SAME/DISTINCT judgment -- annotated in place, never moved to
  another bucket.
- gap: matches nothing, row is active. Untracked live work.
- done_gap: matches nothing, row is done. Finished work the portfolio never
  knew about.

Portfolio items that no source row claims are "unconfirmed" -- a report view,
not a bucket.

## Phase 1 -- Foundation and the seeded world

Features: project scaffold, and a generator script that writes the exact world
below: 20 portfolio YAML files into `state/`, a Jira CSV export (15 rows) and a
backlog XLSX export (7 rows) into `imports/`. The generator embeds this data
appendix verbatim -- it invents nothing.

Success criteria:
- Generator runs clean in one command.
- `state/` holds exactly 20 items, `imports/` holds exactly one CSV with 15
  data rows and one XLSX with 7 data rows, matching the appendix.

## Phase 2 -- Normalization

Features: two read-only normalizers map each export into canonical proposal
records (ref, title, status, source) in a `proposals/` folder.

Success criteria:
- Jira normalizer emits exactly 15 proposals; backlog normalizer exactly 7.
- Refs preserved where present; rows without refs carry an empty ref.
- Nothing under `state/` is created, modified, or removed.

## Phase 3 -- Reconciliation

Features: the reconciler applies the matching and bucket rules to all 22
proposals against the 20 portfolio items and writes `reconcile.json` with
every row's bucket, match target, and score, plus a summary block.

Success criteria (exact, from the appendix):
- Buckets: changed 11, gap 4, conflict 2, ambiguous 1, duplicate 1,
  completed 1, done_gap 2. Total 22.
- The ambiguous row is "Autonomous vehicle fleet navigation", best match
  ML-001, score strictly between 0.40 and 0.80.
- The duplicate row is "Ops latency dashboard", target ML-005.
- Unconfirmed portfolio items: exactly 6 (ML-009, ML-010, ML-011, ML-015,
  ML-019, ML-020).
- Running reconciliation twice produces byte-identical `reconcile.json`.

## Phase 4 -- Semantic judgment and scoring

Features: the semantic pass sends ONLY the ambiguous rows to the model asking
SAME or DISTINCT with a one-sentence reason, and annotates the verdict into
`reconcile.json` in place -- bucket unchanged. The scoring tool asks the model
to propose WSJF factors (business_value, time_criticality, risk_reduction,
job_size, each 1-10) for a chosen item, then computes
WSJF = (business_value + time_criticality + risk_reduction) / job_size in
plain arithmetic and stores factors and score together.

Success criteria:
- After the pass, the 1 ambiguous row carries verdict SAME or DISTINCT plus a
  non-empty reason; its bucket is still ambiguous; every other row untouched.
- With `--no-llm`, both tools run to completion without any network call.
- For any stored score, recomputing from its stored factors reproduces the
  stored value exactly.

## Phase 5 -- Operator webchat

Features: a Flask app on port 8000 behind TOTP login (secret generated at
setup, printed once as an otpauth URL). Screens: dashboard (bucket counts as
hero numbers, unconfirmed count), work items table (all 20), reconciliation
review grouped by bucket showing the semantic verdicts, and a status-change
flow that is strictly propose-then-confirm with an audit line appended to
`logs/audit.log` on every confirm. An Export button downloads one XLSX with
four sheets: Cross-Source (the 15 matched rows), Source-Only (the 6 gap +
done_gap rows), Unconfirmed (the 6 unclaimed portfolio items), Semantic (the
1 judged row).

Success criteria (verify with the agent-browser skill in a real browser):
- A wrong TOTP code is rejected; a correct one reaches the dashboard.
- Dashboard numbers equal Phase 3's bucket counts exactly.
- Changing ML-009's status requires the confirm step; after confirm the YAML
  file reflects it and `logs/audit.log` gained exactly one line; before
  confirm, nothing changed.
- The export downloads, opens with openpyxl without errors, and has exactly
  the four sheets with the row counts above.
- No delete affordance exists anywhere in the UI.

## Phase 6 -- End to end and the oracle

Features: `run_e2e.sh` runs generate, normalize, reconcile, semantic, one
scoring call, export, then `verify_e2e.py` -- which asserts every number in
this brief and prints PASS/FAIL per check.

Success criteria:
- From a clean clone: `bash run_e2e.sh` completes with the oracle reporting
  ALL PASS, no manual steps.
- `bash run_e2e.sh --no-llm` also reaches ALL PASS with the semantic verdict
  checks marked skipped.

## Final success criteria -- do not declare victory until every one is true

1. `bash run_e2e.sh` from a clean clone ends in oracle ALL PASS.
2. The web app is running on port 8000, TOTP login works, and the dashboard
   shows changed 11 / gap 4 / conflict 2 / ambiguous 1 / duplicate 1 /
   completed 1 / done_gap 2 / unconfirmed 6.
3. The browser checks in Phase 5 all pass, verified with agent-browser.
4. Grep the codebase: no route, function, or button deletes a work item.
5. All of the above verified by you, in this container, before you stop.

## Data appendix -- the exact seeded world

Portfolio (`state/`, one YAML per item; fields: id, title, status):

    ML-001  Autonomous fleet routing optimization   in_progress
    ML-002  Driver scheduling engine                in_progress
    ML-003  Warehouse slotting analytics            in_progress
    ML-004  Cold chain temperature monitoring       in_progress
    ML-005  Ops latency dashboard rollout           in_progress
    ML-006  Customs paperwork automation            in_progress
    ML-007  Carrier rate benchmarking               in_progress
    ML-008  Dock door scheduling                    in_progress
    ML-009  Fuel consumption reporting              in_progress
    ML-010  Returns processing portal               in_progress
    ML-011  Vendor onboarding checklist             in_progress
    ML-012  Route deviation alerts                  in_progress
    ML-013  Pallet tracking tags                    in_progress
    ML-014  Invoice dispute workflow                in_progress
    ML-015  Safety incident register                in_progress
    ML-016  Legacy TMS migration                    done
    ML-017  Depot wifi upgrade                      done
    ML-018  Contract renewal archive                done
    ML-019  Driver fatigue study                    in_progress
    ML-020  Packaging waste audit                   in_progress

Jira CSV (`imports/`, columns: ref,title,status -- 15 data rows):

    ML-001  Autonomous fleet routing optimization   blocked
    ML-002  Driver scheduling engine                done
    ML-003  Warehouse slotting analytics            blocked
    ML-004  Cold chain temperature monitoring       done
    ML-005  Ops latency dashboard rollout           blocked
    ML-006  Customs paperwork automation            done
    ML-007  Carrier rate benchmark refresh          in_progress
    ML-008  Dock door scheduling v2                 in_progress
    ML-016  Legacy TMS migration                    in_progress
    ML-017  Depot wifi upgrade                      in_progress
    ML-018  Contract renewal archive                done
    ML-021  Telematics data lake                    done
    ML-022  EDI partner certification               done
    ML-023  Yard congestion heatmap                 in_progress
    ML-024  Reverse logistics pilot                 in_progress

Backlog XLSX (`imports/`, columns: title,status -- 7 data rows, no refs):

    Route deviation alerts                  blocked
    Pallet tracking tags                    done
    Invoice dispute workflow                blocked
    Ops latency dashboard                   in_progress
    Autonomous vehicle fleet navigation     in_progress
    Quarterly fuel hedging review           in_progress
    Trailer telematics retrofit             in_progress
