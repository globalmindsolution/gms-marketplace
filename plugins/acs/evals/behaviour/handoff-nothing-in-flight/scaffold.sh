#!/usr/bin/env bash
# /acs:handoff with NOTHING in flight: EVAL-1's /acs:code step was started and
# finished through the plugin's own writers (`acs.py step start`, then
# `post-code.py` fed the result document), so the run ledger records `code`
# completed, no step is in_progress, the lock is released, and this checkout's
# pointer still names run EVAL-1. What the run must produce: nothing on disk --
# no flush file (Step 3 is skipped when nothing is in flight), no step
# finalized -- and a reply that says there is nothing to hand off while still
# printing handoff.py's `continue_with`, which is `/acs:ship EVAL-1` here.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

acs_ticket "Cap the customer page size at 100" task false \
  "list_customers must clamp limit to at most 100."
acs_branch task/EVAL-1-cap-the-customer-page-size-at-100

python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
sed -i.bak 's/"limit": limit}/"limit": min(limit, 100)}/' src/shop/__init__.py && rm -f src/shop/__init__.py.bak
git commit -qam "EVAL-1 cap the customer page size at 100"
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "list_customers clamps limit to 100",
 "states": {"branch": "task/EVAL-1-cap-the-customer-page-size-at-100", "docs_updated": []},
 "findings": [], "errors": []}
JSON
