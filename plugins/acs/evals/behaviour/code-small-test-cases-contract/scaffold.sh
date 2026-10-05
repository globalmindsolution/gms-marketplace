#!/usr/bin/env bash
# /acs:code on a ticket whose plan records `delivery_path: small` AND whose run
# carries a test-cases.md from /acs:create-test-docs. On the small path that
# document IS the test contract: one test per TC-n row, each naming its TC id
# in the test's docstring (execute.md, step 1). The case asserts every case
# became a test that names it.
#
# Seeded through the plugin's own writers wherever one exists:
#   create-impl-plan   acs.py step start, the planner's draft, acs.py filemap
#                      set, the published copy (uncommitted), post-create-impl-plan.py
#   create-test-docs   acs.py step start, the test designer's test-cases.md in
#                      the step directory and its published copy (uncommitted),
#                      result.json, post-create-test-docs.py
# `small` needs no approval.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Reject a non-positive page limit" task false \
  "list_customers(limit=0) returns an empty page forever; a limit below 1 is a caller bug."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["list_customers(limit=0) and list_customers(limit=-5) raise ValueError", "list_customers(limit=1) still returns a page with limit 1"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null
run="$ACS_PARTITION/runs/EVAL-1"

acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
draft="$run/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Reject a non-positive page limit

`list_customers` in `src/shop/__init__.py` accepts any `limit`. A limit below
1 is a caller bug; make it raise `ValueError` before anything else happens.
`offset` is out of scope.

## Approach

One guard at the top of `list_customers`: `limit < 1` raises
`ValueError("limit must be >= 1")`. Rejected: clamping to 1, because it hides
the caller's bug.

## Test strategy

`test-cases.md` (from /acs:create-test-docs) is the test contract: one test
per TC-n row in the new `tests/test_list_customers.py`, written first and
failing. Run: `python3 -m pytest -q tests/test_list_customers.py`. Coverage
target: 90%, measured by the review's final gate.

## Contract
delivery_path: small
owes:
  api_contract: false
  test_cases: true
  e2e: false
  reason: "one local guard in a library function; no HTTP surface change and no browser flow"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_list_customers.py
MD
acs filemap set --skill code --iteration 1 --task 1 \
  --file src/shop/__init__.py --file tests/test_list_customers.py > /dev/null
mkdir -p docs/tickets/EVAL-1
cp "$draft" docs/tickets/EVAL-1/plan.md
cat > "$run/steps/create-impl-plan/result.json" <<'JSON'
{"status": "completed", "summary": "plan published; one executor task",
 "states": {"plan_path": "docs/tickets/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["src/shop/__init__.py", "tests/test_list_customers.py"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" \
  --result-file "$run/steps/create-impl-plan/result.json" > /dev/null 2>&1

acs step start --step create-test-docs --ticket EVAL-1 > /dev/null 2>&1
cat > "$run/steps/create-test-docs/test-cases.md" <<'MD'
---
ticket: EVAL-1
cases: 3
e2e_cases: 0
---

# Test cases — EVAL-1: Reject a non-positive page limit

## Scope

The two acceptance criteria, at unit level in tests/ with pytest, as
docs/tickets/EVAL-1/plan.md plans. The plan owes no e2e.

## Cases

| ID | AC | Type | Preconditions | Steps | Expected | Suite |
| --- | --- | --- | --- | --- | --- | --- |
| TC-1 | AC-1 | unit | none | `list_customers(limit=0)` | raises `ValueError` | `tests/test_list_customers.py` |
| TC-2 | AC-1 | unit | none | `list_customers(limit=-5)` | raises `ValueError` | `tests/test_list_customers.py` |
| TC-3 | AC-2 | unit | none | `list_customers(limit=1)` | returns `{"items": [], "offset": 0, "limit": 1}` | `tests/test_list_customers.py` |

## Traceability

| AC | Cases |
| --- | --- |
| AC-1 | TC-1, TC-2 |
| AC-2 | TC-3 |

## Gaps and assumptions

_None._
MD
cp "$run/steps/create-test-docs/test-cases.md" docs/tickets/EVAL-1/test-cases.md
cat > "$run/steps/create-test-docs/result.json" <<'JSON'
{"status": "completed", "outcome": "cases_written", "summary": "3 cases, every AC traced",
 "states": {"cases": 3, "e2e_cases": 0, "untraced_acs": []}, "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-test-docs.py" \
  --result-file "$run/steps/create-test-docs/result.json" > /dev/null 2>&1
grep -q '"status": "completed"' "$run/steps/create-test-docs/state.json"
