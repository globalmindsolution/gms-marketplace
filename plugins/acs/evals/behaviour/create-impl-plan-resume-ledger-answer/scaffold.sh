#!/usr/bin/env bash
# create-impl-plan (resume): the shop repo, story EVAL-1 (cursor pagination)
# and the working tree (main, uncommitted -- ADR-0127) carrying its published analysis (SKILL.md's format,
# left uncommitted as the analyze-requirements coordinator does with cp). The
# analysis's four answers are in the clarification ledger as C-1..C-4
# (clarify.py). Then the first half of a planning run, written ONLY through
# the plugin's CLIs: `acs step start` opened create-impl-plan, `clarify.py
# add` recorded the user's answer to the planner's one question as C-5 --
# the cursor codec lives in a NEW module, src/shop/cursor.py, which nothing
# else names -- and `handoff.py` handed the run off (invocation
# `interrupted`, lock released, summary recorded).
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
ACS_FEATURES=customer-listing
acs_ticket "Cursor pagination for GET /customers" story false \
  "Offset paging skips or repeats customers when rows are inserted between page requests. Replace it with an opaque cursor so a client can walk every customer exactly once."
printf '%s' '{"acceptance_criteria": [
  "GET /customers accepts an optional cursor query parameter and returns the page of customers that follows it",
  "Every GET /customers response carries next_cursor, which is null on the last page",
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

mkdir -p docs/development/customer-listing/EVAL-1
cat > docs/development/customer-listing/EVAL-1/analysis.md <<'MD'
---
ticket: EVAL-1
ready_for_planning: true
api_surface: true
needs_design_recommendation: false
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

Ready for planning; api_surface true; no design needed.
MD

clarify() {
  python3 "$ACS_SCRIPTS/clarify.py" add --skill "$1" --ticket EVAL-1 \
    --question "$2" --answer "$3" > /dev/null
}
clarify analyze-requirements "How is the cursor encoded?" "URL-safe base64 of the last customer id"
clarify analyze-requirements "Does offset keep working?" "Yes, deprecated; cursor wins when both are given"
clarify analyze-requirements "What are the limit bounds?" "Default 20, maximum 100"
clarify analyze-requirements "What does a malformed cursor return?" "HTTP 400 with error code invalid_cursor"
python3 "$ACS_SCRIPTS/acs.py" step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
clarify create-impl-plan "Where should the cursor codec (encode and decode) live?" \
  "In a new module, src/shop/cursor.py, imported by list_customers; keep the codec out of src/shop/__init__.py"
python3 "$ACS_SCRIPTS/handoff.py" --ticket EVAL-1 --summary \
  "Iteration 1: the planner's survey raised one question, answered as C-5 (the cursor codec goes in a new module). In flight: no draft written yet. Next: planner iteration 1 with C-5 in context, then plan review, publish, declare the file map." > /dev/null
