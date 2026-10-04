#!/usr/bin/env bash
# analyze-requirements on a ticket whose feature already has a living
# analysis (ADR-0128, ADR-0129): the shop repo with its PRD and architecture
# docs; the customer-listing feature's Discovery analysis, committed at
# docs/product/features/customer-listing/analysis.md (version 1) -- the only
# place that records the decided maximum page size, 250; then story EVAL-1
# (cursor pagination) minted and given its feature and acceptance criteria
# through the plugin's own CLIs. A run on a ticket is a Development run: it
# starts from the living analysis, never edits it, and publishes its own
# analysis to docs/development/customer-listing/EVAL-1/.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
mkdir -p docs/product/features/customer-listing
cat > docs/product/features/customer-listing/analysis.md <<'MD'
---
status: proposed
version: 1
tickets: []
feature: customer-listing
ready_for_planning: true
api_surface: true
needs_design_recommendation: false
---

# Analysis — customer-listing: Customer listing that scales

## Problem restated

GET /customers pages by offset (src/shop/__init__.py:8); offset paging skips
or repeats customers when rows are inserted between requests.

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | listing gains a cursor | src/shop/__init__.py:8 |
| README.md | docs | API section | README.md:7 |

## Questions

- C-1 cursor encoding — answered: URL-safe base64 of the last customer id, opaque to clients.
- C-2 offset compatibility — answered: offset stays, deprecated; cursor wins when both are given.
- C-3 maximum page size — answered: `limit` defaults to 20; the maximum page size is 250.
- C-4 malformed cursor — answered: HTTP 400 with error code `invalid_cursor`.

## Assumptions

_None._

## Risks

- Public API: GET /customers is documented in README.md and called by clients.

## Refined acceptance criteria

_None proposed at the feature level._

## Verdict

Ready for planning as delivery tickets; no design needed.
MD
git add -A && git commit -qm "Customer listing discovery analysis"
acs_ticket "Cursor pagination for GET /customers" story false \
  "Offset paging skips or repeats customers when rows are inserted between page requests. Replace it with an opaque cursor so a client can walk every customer exactly once."
printf '%s' '{"features": ["customer-listing"], "acceptance_criteria": [
  "GET /customers accepts an optional cursor query parameter and returns the page of customers that follows it",
  "Every GET /customers response carries next_cursor, which is null on the last page",
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
