#!/usr/bin/env bash
# /acs:code on iteration 2 of the review loop: /acs:review-code already ran on
# EVAL-1's first implementation and left a verdict with one confirmed blocking
# finding (page_bounds computes 0-based bounds for 1-based pages). /acs:code
# must read that verdict, fix the finding test-first on the SAME branch, and
# answer it by id in its result.json.
#
# Every step is played through the plugin's own writers:
#   create-impl-plan  acs.py step start, the planner's draft (no CLI writer
#                     exists for its bytes), acs.py filemap set, the published
#                     copy committed on the ticket branch, post-create-impl-plan.py
#   code, iter 1      acs.py step start --step code, the implementer's commit and
#                     report, result.json, post-code.py
#   review-code       acs.py step start --step review-code, the verdict at the
#                     step root and in iter-1/, result.json, post-review-code.py
#                     -- which derives the block and sends the loop back to code
# The plan records `small`, so no approval is involved.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Add 1-based page numbers to the customer listing" task false \
  "Merchants page through customers by page number, starting at page 1."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["list_customers_page(customers, page=1) returns the first per_page customers", "list_customers_page(customers, page=2) returns the next per_page customers"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null
run="$ACS_PARTITION/runs/EVAL-1"
branch="task/EVAL-1-add-1-based-page-numbers-to-the-customer"

# --- create-impl-plan ------------------------------------------------------
acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
acs_branch "$branch"
draft="$run/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Add 1-based page numbers to the customer listing

`src/shop/__init__.py` gains `page_bounds(page, per_page)` -- the slice bounds
of a 1-based page -- and `list_customers_page(customers, page, per_page)`,
which returns that slice. Page 1 is the first `per_page` customers.

## Test strategy

New file `tests/test_pagination.py`, written first and failing:

- AC-1: page 1 of 50 customers at 10 per page is customers 0-9.
- AC-2: page 2 is customers 10-19.

Run: `python3 -m pytest -q tests/test_pagination.py`. Coverage target: 90%,
measured by the review's final gate.

## Contract
delivery_path: small
owes:
  api_contract: false
  test_cases: false
  e2e: false
  reason: "two helpers in one module; no HTTP surface change and no browser flow"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_pagination.py
MD
acs filemap set --skill code --iteration 1 --task 1 \
  --file src/shop/__init__.py --file tests/test_pagination.py > /dev/null
mkdir -p docs/tickets/EVAL-1
cp "$draft" docs/tickets/EVAL-1/plan.md
git add docs/tickets/EVAL-1/plan.md
git commit -qm "EVAL-1 Add the implementation plan"
cat > "$run/steps/create-impl-plan/result.json" <<'JSON'
{"status": "completed", "summary": "plan published; one executor task",
 "states": {"plan_path": "docs/tickets/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["src/shop/__init__.py", "tests/test_pagination.py"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" \
  --result-file "$run/steps/create-impl-plan/result.json" > /dev/null 2>&1

# --- code, iteration 1: the defect ships -----------------------------------
acs step start --step code --ticket EVAL-1 > /dev/null 2>&1
cat >> src/shop/__init__.py <<'PY'


def page_bounds(page, per_page=PAGE_SIZE):
    """Slice bounds for a 1-based page number."""
    start = page * per_page
    return start, start + per_page


def list_customers_page(customers, page=1, per_page=PAGE_SIZE):
    """One page of customers; page 1 is the first page."""
    start, end = page_bounds(page, per_page)
    return customers[start:end]
PY
cat > tests/test_pagination.py <<'PY'
from shop import list_customers_page


def test_a_page_holds_per_page_customers():
    customers = list(range(50))
    assert len(list_customers_page(customers, page=2, per_page=10)) == 10
PY
git add src/shop/__init__.py tests/test_pagination.py
git commit -qm "EVAL-1 Page bounds for 1-based pages"
mkdir -p "$run/steps/code/iter-1"
cat > "$run/steps/code/iter-1/implementer.json" <<'JSON'
{"files_changed": ["src/shop/__init__.py", "tests/test_pagination.py"],
 "tests": {"commands": ["python3 -m pytest -q tests/test_pagination.py"], "passed": 1, "failed": 0},
 "coverage": {"percent": null, "target": "measured in review"},
 "commits": ["EVAL-1 Page bounds for 1-based pages"], "problems": [], "seams": []}
JSON
cat > "$run/steps/code/result.json" <<JSON
{"status": "completed", "outcome": "implemented", "iteration": 1,
 "summary": "page_bounds and list_customers_page; 1 targeted test green",
 "states": {"branch": "$branch", "tasks_implemented": ["1"],
            "tests": {"passed": 1, "failed": 0}, "docs_updated": []},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-code.py" --result-file "$run/steps/code/result.json" > /dev/null 2>&1

# --- review-code, iteration 1: one confirmed blocking finding ---------------
acs step start --step review-code --ticket EVAL-1 > /dev/null 2>&1
review="$run/steps/review-code"
mkdir -p "$review/iter-1"
base="$(git rev-parse main)"
cat > "$review/iter-1/verdict.json" <<JSON
{
  "skill": "review-code", "run_id": "EVAL-1", "iteration": 1,
  "reviewed_sha": "$base", "passed": false,
  "findings": [
    {"id": "F-1-1", "status": "confirmed", "severity": "blocking", "kind": "defect",
     "lens": "B", "file": "src/shop/__init__.py", "line": 13,
     "claim": "page_bounds treats a 1-based page as 0-based: page 1 returns customers 10-19 at 10 per page, and the first page is unreachable.",
     "evidence": ["start = page * per_page, so page_bounds(1, 10) == (10, 20)",
                  "tests/test_pagination.py checks only a page's length, never which customers it holds"],
     "resolved_when": "page_bounds(1, n) == (0, n), and a test asserts page 1 returns the first per_page customers",
     "traces_to": ["AC-1", "AC-2"],
     "adjudication": {"verdict": "confirmed"}}
  ]
}
JSON
cp "$review/iter-1/verdict.json" "$review/verdict.json"
printf '{"adjudications": [{"id": "F-1-1", "verdict": "confirmed"}]}\n' > "$review/iter-1/adjudication.json"
cat > "$review/result.json" <<'JSON'
{"status": "completed", "outcome": "blocking_findings", "iteration": 1,
 "summary": "1 confirmed blocking finding: F-1-1 page_bounds off by one page",
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-review-code.py" --result-file "$review/result.json" > /dev/null 2>&1
# The kernel derived the block and opened iteration 2 of the review loop:
# refuse to seed anything else.
# (Captured first: `| grep -q` under pipefail can SIGPIPE the writer.)
ledger="$(acs run show --run EVAL-1 2>/dev/null | tr -d ' \n')"
grep -q '"review-code":{"iteration":2' <<<"$ledger"
