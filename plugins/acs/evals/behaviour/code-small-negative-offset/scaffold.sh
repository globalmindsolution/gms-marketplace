#!/usr/bin/env bash
# /acs:code on a ticket whose plan records `delivery_path: small`, so /acs:code
# must dispatch to the code-small leg (a real Skill call the grader sees).
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
# `small` needs no approval: plan-approval.py records nothing on this path.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
ACS_FEATURES=customer-listing
acs_ticket "Reject a negative page offset" task false \
  "list_customers(offset=-3) silently returns a page instead of refusing the offset."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["list_customers(offset=-1) raises ValueError", "list_customers(offset=0) still returns the first page"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
draft="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Reject a negative page offset

`list_customers` in `src/shop/__init__.py` accepts any offset. A negative one
is a caller bug that today returns a page; make it raise `ValueError` before
anything else happens. `limit` is out of scope.

## Approach

Add one guard at the top of `list_customers`: `offset < 0` raises
`ValueError("offset must be >= 0")`. Rejected: clamping to 0, because it hides
the caller's bug.

## Test strategy

New file `tests/test_list_customers.py`, written first and failing:

- AC-1: `list_customers(offset=-1)` raises `ValueError`.
- AC-2: `list_customers(offset=0)` returns offset 0 and limit 20.

Run: `python3 -m pytest -q tests/test_list_customers.py`. Coverage target:
90%, measured by the review's final gate.

## Docs

No product-doc fact changes; the README describes the endpoint, not its
validation.

## Contract
delivery_path: small
owes:
  api_contract: false
  test_cases: false
  e2e: false
  reason: "one local guard in a library function; no HTTP surface change and no browser flow"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_list_customers.py
MD
acs filemap set --skill code --iteration 1 --task 1 \
  --file src/shop/__init__.py --file tests/test_list_customers.py > /dev/null
mkdir -p docs/development/customer-listing/EVAL-1
cp "$draft" docs/development/customer-listing/EVAL-1/plan.md
result="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/result.json"
cat > "$result" <<'JSON'
{"status": "completed", "summary": "plan published; one executor task",
 "states": {"plan_path": "docs/development/customer-listing/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["src/shop/__init__.py", "tests/test_list_customers.py"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$result" > /dev/null 2>&1
