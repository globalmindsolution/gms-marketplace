#!/usr/bin/env bash
# analyze-requirements, the first acs run in a repo that has never answered
# acs's document questions (ADR-0132): .acs/settings.json carries the ticket
# prefix and nothing under `docs`, and there is no docs/development/ folder --
# so `acs.py docs where --doc analysis.md` reports `needs: [share, location]`
# with the built-in default `docs/development` as the proposed folder. The PRD,
# the architecture set and story EVAL-1 (customer-listing, three acceptance
# criteria) are cursor-pagination's, minted through the plugin's own CLIs.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

ACS_DOCS_UNDECIDED=1 acs_repo
acs_prd
acs_architecture
acs_ticket "Cursor pagination for GET /customers" story false \
  "Offset paging skips or repeats customers when rows are inserted between page requests. Replace it with an opaque cursor so a client can walk every customer exactly once."
printf '%s' '{"features": ["customer-listing"], "acceptance_criteria": [
  "GET /customers accepts an optional cursor query parameter and returns the page of customers that follows it",
  "Every GET /customers response carries next_cursor, which is null on the last page",
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
