#!/usr/bin/env bash
# /acs:code on a ticket whose plan records `delivery_path: standard` and whose
# approval is current, so /acs:code must dispatch to the code-standard leg (a
# real Skill call the grader sees) and its pre-hook must let the deep path in.
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
# and then APPROVED the way a human approves it: `acs.py plan check`, the sole
# writer of plan-approval.json, which hashes the plan's bytes. Nothing here
# writes the approval record by hand; an edited plan would be unapproved.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
ACS_FEATURES=customer-listing
acs_ticket "Search customers by name" story false \
  "Merchants with hundreds of customers need to find one by name without paging."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["search_customers(customers, \"ali\") returns every customer whose name contains ali, case-insensitively", "a blank query raises ValueError", "the README documents GET /customers/search?q="]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
draft="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Search customers by name

A new public capability: find customers by a name fragment. It is a new
module in the library plus the API documentation merchants read, two
independent pieces of work.

## Approach

`src/shop/search.py` gains `search_customers(customers, query)`: `customers`
is a list of dicts with a `name` key; the result keeps input order and holds
every customer whose name contains `query`, compared case-insensitively. A
blank or whitespace-only query raises `ValueError` rather than returning
everyone. Rejected: a regex query, because merchants type names, not patterns.
Not done here: any index or persistence.

The README's API list gains `GET /customers/search?q=` and the CHANGELOG an
Unreleased entry. The two tasks share no file.

## Test strategy

Task 1, `tests/test_search.py`, written first and failing:

- AC-1: `"ali"` matches `Alice` and `Natalie`, not `Bob`; order kept.
- AC-2: `""` and `"  "` raise `ValueError`.

Run: `python3 -m pytest -q tests/test_search.py`. Coverage target: 90% of
`src/shop/search.py`, measured by the review's final gate.

Task 2 is documentation (AC-3); no test.

## Risks

A merchant list can hold thousands of customers; the scan is linear, which is
acceptable at that size and named here so the review can check it.

## Contract
delivery_path: standard
owes:
  api_contract: false
  test_cases: false
  e2e: false
  reason: "a library function and its documentation; the HTTP layer is out of scope and there is no browser flow"

### Executor tasks & file map
- task 1: src/shop/search.py, tests/test_search.py
- task 2: README.md, CHANGELOG.md
MD
acs filemap set --skill code --iteration 1 --task 1 \
  --file src/shop/search.py --file tests/test_search.py > /dev/null
acs filemap set --skill code --iteration 1 --task 2 \
  --file README.md --file CHANGELOG.md > /dev/null
mkdir -p docs/development/customer-listing/EVAL-1
cp "$draft" docs/development/customer-listing/EVAL-1/plan.md
result="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/result.json"
cat > "$result" <<'JSON'
{"status": "completed", "summary": "plan published; two disjoint executor tasks",
 "states": {"plan_path": "docs/development/customer-listing/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["src/shop/search.py", "tests/test_search.py"],
                         "2": ["README.md", "CHANGELOG.md"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$result" > /dev/null 2>&1
# The human's approval, through its sole writer. Refuse to seed an unapproved
# deep-path plan: the case would then measure the pre-hook, not the leg.
# (Captured first: `| grep -q` under pipefail can SIGPIPE the writer.)
checked="$(acs plan check --run EVAL-1)"
grep -q '"plan_approved": true' <<<"$checked"
