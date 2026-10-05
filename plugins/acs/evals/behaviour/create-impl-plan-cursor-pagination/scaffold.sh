#!/usr/bin/env bash
# create-impl-plan: the shop repo, story EVAL-1 minted and given its
# acceptance criteria through the plugin's own CLIs, and the working tree
# (main, nothing committed -- ADR-0127) carrying the PUBLISHED analysis
# /acs:analyze-requirements would have left there:
# docs/tickets/EVAL-1/analysis.md, uncommitted.
#
# acs has no writer command for an analysis -- the analyze-requirements
# coordinator copies its verified draft into the docs folder with cp and
# leaves it uncommitted -- so the file below is written in exactly the format
# that skill's SKILL.md specifies (front matter + seven headings; it passes
# front_matter_check.py and structure_lint.py). No workspace step state is
# forged: the create-impl-plan gate reads analysis.md when present and
# requires no predecessor step.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Cursor pagination for GET /customers" story false \
  "Offset paging skips or repeats customers when rows are inserted between page requests. Replace it with an opaque cursor so a client can walk every customer exactly once."
printf '%s' '{"acceptance_criteria": [
  "GET /customers accepts an optional cursor query parameter and returns the page of customers that follows it",
  "Every GET /customers response carries next_cursor, which is null on the last page",
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

mkdir -p docs/tickets/EVAL-1
cat > docs/tickets/EVAL-1/analysis.md <<'MD'
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
