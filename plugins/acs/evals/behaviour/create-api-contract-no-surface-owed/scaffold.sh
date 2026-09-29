#!/usr/bin/env bash
# create-api-contract (nothing owed): the shop repo, story EVAL-1 "Log slow
# customer listings", and the ticket branch carrying its published analysis
# (api_surface: false) and plan, whose Contract block says
# `api_contract: false` with a reason. The create-impl-plan step is RUN, not
# just its document committed, because the no-op is read from the run's own
# plan (runs/EVAL-1/steps/create-impl-plan/plan.md): `acs step start`, the
# draft, `acs.py filemap set`, result.json and post-create-impl-plan.py --
# the plugin's own writers, exactly what the planning coordinator does. The
# create-api-contract pre-hook then records the step completed with
# `outcome: no_surface_owed` and refuses the Skill call (exit 2); measured
# through `dispatch.py pre`.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Log slow customer listings" story false \
  "Operators cannot tell when customer listing pages are slow. When list_customers takes longer than 200 ms, log a warning through the standard logging module so slow pages show up in the service log."
printf '%s' '{"acceptance_criteria": [
  "list_customers logs one WARNING on the shop logger when a call takes longer than 200 ms",
  "The warning names the offset, the limit and the elapsed milliseconds",
  "A call that takes 200 ms or less logs nothing"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

acs_branch story/EVAL-1-log-slow-customer-listings
mkdir -p docs/tickets/EVAL-1
cat > docs/tickets/EVAL-1/analysis.md <<'MD'
---
ticket: EVAL-1
ready_for_planning: true
api_surface: false
needs_design_recommendation: false
---

# Analysis — EVAL-1: Log slow customer listings

## Problem restated

Slow customer listing pages are invisible to operators. `list_customers`
should log a warning when a call exceeds 200 ms.

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | time `list_customers`; log a WARNING on the `shop` logger above 200 ms | src/shop/__init__.py:8 |
| tests/test_slow_listing_log.py | tests | new unit tests with a patched clock | tests/ holds only test_health.py |

## Questions

_None._

## Assumptions

- The logger is `logging.getLogger("shop")`, the module's own name.
- The 200 ms threshold is a module constant, not a setting.

## Risks

_None beyond log volume on a slow database, bounded to one line per slow call._

## Refined acceptance criteria

The three criteria on the ticket are confirmed as written.

## Verdict

Ready for planning; no API surface changes (the return value, parameters and
errors of GET /customers are untouched; the log line is operator output); no
design needed.
MD
git add docs/tickets/EVAL-1
git commit -qm "EVAL-1 Analyze slow listing log"
cat > docs/tickets/EVAL-1/plan.md <<'MD'
# Plan — EVAL-1: Log slow customer listings

Planned from docs/tickets/EVAL-1/analysis.md (api_surface false).

## Approach

Wrap the body of `list_customers` in `src/shop/__init__.py` with
`time.perf_counter()`; above `SLOW_LISTING_MS = 200` log one WARNING on
`logging.getLogger("shop")` naming offset, limit and elapsed ms. The return
value and signature do not change.

## Tests

| AC | Test (tests/test_slow_listing_log.py) |
|---|---|
| AC-1 | a patched 250 ms call logs exactly one WARNING on `shop` |
| AC-2 | that warning names offset, limit and 250 |
| AC-3 | a patched 200 ms call logs nothing |

Run `python3 -m pytest -q --cov=src --cov-fail-under=90`; coverage target 90%.

## Documentation

docs/product/prd.md and docs/product/roadmap.md make no claim this changes.

## Contract
delivery_path: trivial
owes:
  api_contract: false
  test_cases: true
  e2e: false
  reason: "Operator log line only: GET /customers keeps its parameters, response and errors"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_slow_listing_log.py
MD
git add docs/tickets/EVAL-1
git commit -qm "EVAL-1 Plan slow listing log"
step="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan"
python3 "$ACS_SCRIPTS/acs.py" step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
cp docs/tickets/EVAL-1/plan.md "$step/plan.md"
python3 "$ACS_SCRIPTS/acs.py" filemap set --skill code --iteration 1 --task 1 --file src/shop/__init__.py --file tests/test_slow_listing_log.py > "$step/filemap.out"
python3 - "$step" <<'PY'
import json, sys
step = sys.argv[1]
file_map = json.load(open(step + "/filemap.out"))["tasks"]
json.dump({"status": "completed", "summary": "plan reviewer passed on iteration 1; plan published",
           "states": {"plan_path": "docs/tickets/EVAL-1/plan.md", "plan_approved": False,
                      "file_map": file_map},
           "findings": [], "errors": []}, open(step + "/result.json", "w"))
PY
rm "$step/filemap.out"
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$step/result.json" > /dev/null
