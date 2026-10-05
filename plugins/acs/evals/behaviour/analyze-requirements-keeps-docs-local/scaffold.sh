#!/usr/bin/env bash
# analyze-requirements in a repo whose team already chose to keep run documents
# LOCAL (ADR-0132): .acs/settings.json, committed, records
# docs.share_run_documents false. `acs.py docs where --doc analysis.md` then
# needs nothing and resolves the analysis to the run's own state folder,
# steps/analyze-requirements/local/analysis/ -- so the run must not ask, must
# not publish anything under docs/, and names the choice in its report. The
# PRD, the architecture set and story EVAL-1 are cursor-pagination's.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

ACS_DOCS_UNDECIDED=1 acs_repo
printf '{\n  "ticket_prefix": "EVAL",\n  "docs": {"share_run_documents": false}\n}\n' \
  > .acs/settings.json
git add -A && git commit -qm "acs: keep run documents local"
acs_prd
acs_architecture
acs_ticket "Cursor pagination for GET /customers" story false \
  "Offset paging skips or repeats customers when rows are inserted between page requests. Replace it with an opaque cursor so a client can walk every customer exactly once."
printf '%s' '{"features": ["customer-listing"], "acceptance_criteria": [
  "GET /customers accepts an optional cursor query parameter and returns the page of customers that follows it",
  "Every GET /customers response carries next_cursor, which is null on the last page",
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
