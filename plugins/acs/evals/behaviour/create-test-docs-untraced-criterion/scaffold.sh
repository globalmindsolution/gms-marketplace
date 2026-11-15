#!/usr/bin/env bash
# create-test-docs (untraced criterion): the shop repo, story EVAL-1 (cursor
# pagination) minted with FOUR acceptance criteria -- the fourth, "The
# pagination code is clean and easy to maintain", has no observable outcome --
# and the working tree (main, uncommitted -- ADR-0127) carrying what the earlier Build steps would have
# published: analysis.md (C-5 about AC-4 left open), plan.md (AC-4 planned as
# written, no test) and the approved API contract (acs_api_contract_customers).
# Each is written in its SKILL.md
# format and left uncommitted as its coordinator does with cp.
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
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor",
  "The pagination code is clean and easy to maintain"
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
- C-5 what measures AC-4 — open.

## Assumptions

_None._

## Risks

- Public API: GET /customers is documented in README.md and called by
  clients; `offset` must keep working (src/shop/__init__.py, README.md).

## Refined acceptance criteria

AC-1..AC-3 are confirmed as written. AC-4 ("clean and easy to maintain")
has no observable outcome; C-5 asks what would measure it -- open.

## Verdict

Ready for planning.
MD
cat > docs/development/customer-listing/EVAL-1/plan.md <<'MD'
# Plan — EVAL-1: Cursor pagination for GET /customers

Planned from docs/development/customer-listing/EVAL-1/analysis.md.

## Approach

`list_customers` in `src/shop/__init__.py` gains `cursor` and returns
`next_cursor`; a malformed cursor raises `InvalidCursor` -> 400
`invalid_cursor`. `offset` keeps working; `limit` defaults to 20, max 100.

## Tests

| AC | Test (tests/test_customers.py) |
|---|---|
| AC-1 | a cursor returns the page after the customer it encodes |
| AC-2 | `next_cursor` is null on the last page |
| AC-3 | a malformed cursor -> 400 `invalid_cursor` |
| AC-4 | none: no observable outcome (C-5 open — planned as written) |

Run `python3 -m pytest -q --cov=src --cov-fail-under=90`; coverage target 90%.

## Risks

C-5 open — planned as written.

## Contract
delivery_path: small
owes:
  test_cases: true
  e2e: false
  reason: "GET /customers gains a query parameter, a response field and an error code"

### Executor tasks & file map
- task 1: src/shop/__init__.py, tests/test_customers.py, README.md
MD
acs_api_contract_customers
