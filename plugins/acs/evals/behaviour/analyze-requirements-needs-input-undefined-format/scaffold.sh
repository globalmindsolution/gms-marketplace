#!/usr/bin/env bash
# analyze-requirements (not ready for planning): the shop repo with its PRD
# and architecture docs, and story EVAL-1 "Customer export for finance",
# minted and given two acceptance criteria through the plugin's own CLIs. The
# second criterion hinges on the target accounting system's import format,
# which nothing in the repo, the ticket or the prompt defines.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Customer export for finance" story false \
  "Finance wants to export our customers so they can reconcile them in their accounting system."
printf '%s' '{"acceptance_criteria": [
  "Finance can download an export of every customer",
  "The export imports into the accounting system finance uses without manual edits"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
