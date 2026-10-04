#!/usr/bin/env bash
# /acs:code on a ticket whose plan records `delivery_path: trivial`, so /acs:code
# must dispatch to the code-trivial leg (a real Skill call the grader sees).
#
# The plan is produced the way /acs:create-impl-plan produces one, through the
# plugin's own writers wherever one exists:
#   acs.py step start --step create-impl-plan   (run, lock, pointer, ledger)
#   the draft at runs/EVAL-1/steps/create-impl-plan/plan.md -- the ONE file
#     plan-approval.py and /acs:code read; the planner subagent writes it with
#     the Write tool, so there is no CLI writer for its bytes
#   acs.py filemap set --skill code --iteration 1 (the map the guard enforces)
#   the published copy in docs/development/<feature>/EVAL-1/, left uncommitted on main
#   post-create-impl-plan.py (finishes the step, releases the lock)
# `trivial` needs no approval: plan-approval.py records nothing on this path.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
ACS_FEATURES=customer-listing
acs_ticket "Default customer page size should be 25" task false \
  "Merchants asked for 25 customers per page. PAGE_SIZE is still 20."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["list_customers() defaults to a limit of 25", "the README states 25 per page"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
draft="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Default customer page size should be 25

A constant corrected. `PAGE_SIZE` in `src/shop/__init__.py` is `20`; the
ticket asks for `25`. `list_customers` already reads it as its default
`limit`, so nothing else in the code changes. The README's "20 per page" is
the one doc fact the change makes stale.

## Test strategy

New file `tests/test_page_size.py`, written first and failing:

- AC-1: `list_customers()["limit"] == 25`.

Run: `python3 -m pytest -q tests/test_page_size.py`. Coverage target: 90%,
measured by the review's final gate.

## Docs

`README.md`: "20 per page by default" becomes "25 per page by default"
(AC-2). No PRD or roadmap fact changes.

## Contract
delivery_path: trivial
owes:
  api_contract: false
  test_cases: false
  e2e: false
  reason: "a constant corrected; no public surface changes shape and there is no browser flow"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_page_size.py, README.md
MD
acs filemap set --skill code --iteration 1 --task 1 \
  --file src/shop/__init__.py --file tests/test_page_size.py --file README.md > /dev/null
mkdir -p docs/development/customer-listing/EVAL-1
cp "$draft" docs/development/customer-listing/EVAL-1/plan.md
result="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/result.json"
cat > "$result" <<'JSON'
{"status": "completed", "summary": "plan published; one executor task",
 "states": {"plan_path": "docs/development/customer-listing/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["src/shop/__init__.py", "tests/test_page_size.py", "README.md"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$result" > /dev/null 2>&1
