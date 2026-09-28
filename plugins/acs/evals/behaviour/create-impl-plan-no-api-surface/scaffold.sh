#!/usr/bin/env bash
# create-impl-plan (no API surface): the shop repo, story EVAL-1 "Log slow
# customer listings" minted and given its criteria through the plugin's own
# CLIs, and the ticket branch carrying the PUBLISHED analysis
# /acs:analyze-requirements would have left -- front matter api_surface:
# false, because the change is an operator log line and GET /customers keeps
# its parameters, response and errors. acs has no writer command for an
# analysis (its coordinator copies the verified draft with cp and commits
# it), so the file is written in exactly SKILL.md's format and committed.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Log slow customer listings" story false \
  "Operators cannot tell when customer listing pages are slow. When list_customers takes longer than 200 ms, log a warning through the standard logging module so slow pages show up in the service log."
printf '%s' '{"acceptance_criteria": [
  "list_customers logs one WARNING on the shop logger when a call takes longer than 200 ms",
  "The warning names the offset, the limit and the elapsed milliseconds",
  "A call that takes 200 ms or less logs nothing"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

acs_branch story/EVAL-1-log-slow-customer-listings
mkdir -p docs/tickets/EVAL-1
cat > docs/tickets/EVAL-1/analysis.md <<'MD'
---
ticket: EVAL-1
ready_for_planning: true
api_surface: false
needs_design_recommendation: false
---

# Analysis — EVAL-1: Log slow customer listings

## Problem restated

Slow customer listing pages are invisible to operators. `list_customers`
should log a warning when a call exceeds 200 ms.

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | time `list_customers`; log a WARNING on the `shop` logger above 200 ms | src/shop/__init__.py:8 |
| tests/test_slow_listing_log.py | tests | new unit tests with a patched clock | tests/ holds only test_health.py |

## Questions

_None._

## Assumptions

- The logger is `logging.getLogger("shop")`, the module's own name.
- The 200 ms threshold is a module constant, not a setting.

## Risks

_None beyond log volume on a slow database, bounded to one line per slow call._

## Refined acceptance criteria

The three criteria on the ticket are confirmed as written.

## Verdict

Ready for planning; no API surface changes (the return value, parameters and
errors of GET /customers are untouched; the log line is operator output); no
design needed.
MD
git add docs/tickets/EVAL-1
git commit -qm "EVAL-1 Analyze slow listing log"
