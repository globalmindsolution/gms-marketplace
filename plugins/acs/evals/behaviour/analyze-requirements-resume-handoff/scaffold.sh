#!/usr/bin/env bash
# analyze-requirements (resume): the shop repo with its PRD and architecture
# docs and story EVAL-1 (cursor pagination), then the first half of an
# analysis run, written ONLY through the plugin's own CLIs: `acs step start`
# opened the step, `clarify.py add` recorded the user's four answers (C-1..C-4;
# C-3's maximum page size, 250, appears nowhere else), and `handoff.py` handed
# the run off -- finalizing the invocation `interrupted` (stop_reason
# context_pressure), releasing the lock and writing the handoff summary the
# next `acs step start` returns with `reconcile: true`. No survey notes, draft,
# branch or development folder exist: the resumed run re-surveys, skips Stage 2
# (everything is answered) and publishes.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Cursor pagination for GET /customers" story \
  "Offset paging skips or repeats customers when rows are inserted between page requests. Replace it with an opaque cursor so a client can walk every customer exactly once."
printf '%s' '{"features": ["customer-listing"], "acceptance_criteria": [
  "GET /customers accepts an optional cursor query parameter and returns the page of customers that follows it",
  "Every GET /customers response carries next_cursor, which is null on the last page",
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

python3 "$ACS_SCRIPTS/acs.py" step start --step analyze-requirements --ticket EVAL-1 > /dev/null 2>&1
clarify() {
  python3 "$ACS_SCRIPTS/clarify.py" add --skill analyze-requirements --ticket EVAL-1 \
    --question "$1" --answer "$2" > /dev/null
}
clarify "How is the cursor encoded?" "URL-safe base64 of the last customer id on the page; opaque to clients"
clarify "Does offset keep working for existing clients?" "Yes, deprecated but supported; cursor wins when both are given"
clarify "What is the maximum page size (limit)?" "limit keeps its default of 20; the maximum page size is 250"
clarify "What does a malformed or tampered cursor return?" "HTTP 400 with error code invalid_cursor"
python3 "$ACS_SCRIPTS/handoff.py" --ticket EVAL-1 --summary \
  "Stage 2 done: the user's answers are recorded as C-1..C-4 in the clarification ledger. In flight: nothing written yet (no survey notes, no draft). Next: re-run the Stage 1 survey, skip Stage 2 (all answered), then Stage 3 draft, impact review and publish." > /dev/null
