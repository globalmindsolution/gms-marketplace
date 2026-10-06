#!/usr/bin/env bash
# /acs:code on a DOCS-ONLY ticket whose approved plan records `delivery_path:
# standard` with two disjoint documentation partitions. The ticket carries the
# user-confirmed `docs_only` flag, so the TDD steps relax: no failing test
# first and no new test, while the partitions still run as parallel slices and
# the existing tests stay green. An implementer that finds itself touching
# executable code or tests must stop -- none is in the map.
#
# The plan is produced the way /acs:create-impl-plan produces one, through the
# plugin's own writers wherever one exists:
#   acs.py ticket save                          (the docs_only flag)
#   acs.py step start --step create-impl-plan   (run, lock, pointer, ledger)
#   the draft at runs/EVAL-1/steps/create-impl-plan/plan.md (the planner's
#     Write; no CLI writer exists for its bytes)
#   acs.py filemap set --skill code --iteration 1 (the map the guard enforces)
#   the published copy in docs/development/<feature>/EVAL-1/, left uncommitted on main
#   post-create-impl-plan.py (finishes the step, releases the lock)
# and then APPROVED through the sole writer of plan-approval.json, `acs.py plan
# check`, which the standard path's pre-hook requires.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
ACS_FEATURES=customer-listing
acs_ticket "Document the customer listing API" story \
  "Merchants integrating with shop cannot find what GET /customers accepts or returns."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"docs_only": true, "acceptance_criteria": ["docs/api/customers.md documents GET /customers: the offset and limit parameters, the default of 20 per page, and the response shape", "the README links to docs/api/customers.md", "the CHANGELOG has an Unreleased entry for the new page"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null
grep -q '"docs_only": true' "$ACS_PARTITION/EVAL-1/ticket.json"

acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
draft="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Document the customer listing API

Documentation only: the ticket is flagged `docs_only`. No source or test file
changes. `list_customers(offset=0, limit=PAGE_SIZE)` in `src/shop/__init__.py`
is the behaviour being documented, read as it is: `PAGE_SIZE` is 20 and the
response is `{"items": [...], "offset": <offset>, "limit": <limit>}`.

## Approach

**Task 1 — the API page.** A new `docs/api/customers.md` documents
`GET /customers`: the `offset` and `limit` query parameters, the default of 20
per page, and the response shape, with one example (AC-1).

**Task 2 — the entry points.** The README's API list links to
`docs/api/customers.md` (AC-2), and the CHANGELOG gains an Unreleased entry
(AC-3). The two tasks share no file.

## Test strategy

Docs only: no new test. The existing suite
(`python3 -m pytest -q`) is run once and must stay green. Coverage target: 90%,
unchanged, measured by the review's final gate.

## Contract
delivery_path: standard
owes:
  test_cases: false
  e2e: false
  reason: "documentation of a public API across two entry points; no code, no browser flow"

### Executor tasks & file map
- task 1: docs/api/customers.md
- task 2: README.md, CHANGELOG.md
MD
acs filemap set --skill code --iteration 1 --task 1 --file docs/api/customers.md > /dev/null
acs filemap set --skill code --iteration 1 --task 2 \
  --file README.md --file CHANGELOG.md > /dev/null
mkdir -p docs/development/customer-listing/EVAL-1
cp "$draft" docs/development/customer-listing/EVAL-1/plan.md
result="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/result.json"
cat > "$result" <<'JSON'
{"status": "completed", "summary": "plan published; two disjoint documentation tasks",
 "states": {"plan_path": "docs/development/customer-listing/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["docs/api/customers.md"],
                         "2": ["README.md", "CHANGELOG.md"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$result" > /dev/null 2>&1
# The human's approval, through its sole writer. Refuse to seed an unapproved
# deep-path plan: the case would then measure the pre-hook, not the leg.
# (Captured first: `| grep -q` under pipefail can SIGPIPE the writer.)
approval="$(acs plan check --run EVAL-1)"
grep -q '"plan_approved": true' <<<"$approval"
