#!/usr/bin/env bash
# /acs:handoff with a run in flight: EVAL-1's /acs:code step was started
# through the plugin's own `acs.py step start` (which takes the run lock and
# points this checkout at the run) and left in_progress, with a first commit
# on the ticket branch -- the state a long session is in when the user says
# "hand this off". What the run must produce, all through handoff.py: the code
# step and its invocation finalized `interrupted` with stop_reason
# context_pressure and the summary, the soft context flushed to
# steps/code/handoff-context.md, and the continue command in the reply.
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
cat > tests/test_page_cap.py <<'PY'
from shop import list_customers


def test_limit_is_capped_at_100():
    assert list_customers(limit=500)["limit"] == 100
PY
git add -A
git commit -qm "EVAL-1 failing test for the page-size cap"
