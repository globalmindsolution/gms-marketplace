#!/usr/bin/env bash
# create-test-docs: the shop repo, story EVAL-1 minted and given its three
# acceptance criteria through the plugin's own CLIs, and the working tree
# (main, nothing committed -- ADR-0127) carrying what the earlier Build steps would have PUBLISHED there, uncommitted:
# docs/development/customer-listing/EVAL-1/analysis.md, plan.md (whose Contract block owes test
# cases, so the pre-hook does NOT settle the step as no_cases_owed) and
# the API contract the Design phase approved (acs_api_contract_customers:
# lld/customer-listing/api/customers.md, one item, GET /customers, with the
# invalid_cursor error, and the run record EVAL-1/api-contract.md linking it).
#
# acs has no writer command for any of the three -- each coordinator copies
# its verified draft into the docs folder with cp and leaves it uncommitted -- so they
# are written in exactly the format their SKILL.md specifies (each passes
# front_matter_check.py / structure_lint.py; the plan's Contract block parses
# through acs_lib.plan_contract) and left uncommitted as ordinary repo files. No
# workspace step state is forged: the create-test-docs gate reads them when
# present and requires no predecessor step.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
ACS_FEATURES=customer-listing
acs_ticket "Cursor pagination for GET /customers" story \
  "Offset paging skips or repeats customers when rows are inserted between page requests. Replace it with an opaque cursor so a client can walk every customer exactly once."
printf '%s' '{"acceptance_criteria": [
  "GET /customers accepts an optional cursor query parameter and returns the page of customers that follows it",
  "Every GET /customers response carries next_cursor, which is null on the last page",
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

mkdir -p docs/architecture/lld/customer-listing/EVAL-1 docs/development/customer-listing/EVAL-1
cat > docs/development/customer-listing/EVAL-1/analysis.md <<'MD'
---
ticket: EVAL-1
ready_for_planning: true
---

# Analysis — EVAL-1: Cursor pagination for GET /customers

## Problem restated

Offset paging on GET /customers skips or repeats customers when rows are
inserted between page requests. Clients need an opaque cursor that walks every
customer exactly once, while existing offset clients keep working.

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | `list_customers` gains `cursor`, returns `next_cursor` | src/shop/__init__.py:8 |
| tests/test_customers.py | tests | new unit tests for cursor paging | tests/ holds only test_health.py |
| README.md | docs | API section documents `cursor` and `next_cursor` | README.md:7 |

## Questions

- C-1 cursor encoding — answered: URL-safe base64 of the last customer id.
- C-2 offset compatibility — answered: kept, deprecated; cursor wins.
- C-3 limit bounds — answered: default 20, maximum 100.
- C-4 malformed cursor — answered: HTTP 400, `invalid_cursor`.

## Assumptions

_None._

## Risks

- Public API: GET /customers is documented in README.md and called by
  clients; `offset` must keep working (src/shop/__init__.py, README.md).

## Refined acceptance criteria

The three criteria on the ticket are confirmed as written.

## Verdict

Ready for planning.
MD
cat > docs/development/customer-listing/EVAL-1/plan.md <<'MD'
# Plan — EVAL-1: Cursor pagination for GET /customers

Planned from docs/development/customer-listing/EVAL-1/analysis.md (ready for planning) and the ticket's three acceptance criteria.

## Approach

`list_customers` in `src/shop/__init__.py` gains a keyword-only `cursor`
argument. The cursor is the URL-safe base64 of the last customer id on the
page; decoding failure raises `InvalidCursor`, which the handler maps to
HTTP 400 with error code `invalid_cursor`. Every response carries
`next_cursor` (null on the last page). `offset` keeps working, deprecated;
when both are given, `cursor` wins. `limit` defaults to 20, capped at 100.

Rejected: a signed cursor (HMAC). Nothing in the repo holds a secret today,
and tampering is already caught as a malformed or unknown id.

Not done here: removing `offset`, or paging any other endpoint.

## Tests

| AC | Test (tests/test_customers.py) |
|---|---|
| AC-1 | a cursor returns the page after the customer it encodes |
| AC-2 | `next_cursor` is set mid-list and null on the last page |
| AC-3 | a malformed cursor raises `InvalidCursor` -> 400 `invalid_cursor` |

Run `python3 -m pytest -q --cov=src --cov-fail-under=90`; the coverage target
is 90%.

## Documentation

README.md's API section documents `cursor` and `next_cursor`.
docs/product/prd.md and docs/product/roadmap.md make no claim this changes.

## Risks

GET /customers is a public API: `offset` clients must keep working.

## Contract
delivery_path: small
owes:
  test_cases: true
  e2e: false
  reason: "GET /customers gains a query parameter, a response field and an error code; no browser flow"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_customers.py, README.md
MD
acs_api_contract_customers
