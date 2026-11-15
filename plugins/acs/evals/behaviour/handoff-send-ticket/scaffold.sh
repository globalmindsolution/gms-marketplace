#!/usr/bin/env bash
# /acs:handoff sending a ticket: EVAL-1's /acs:code step was started through
# the plugin's own `acs.py step start` and left in_progress, with the work
# UNCOMMITTED in the working tree (a source edit and a new test) -- the state a
# member is in when they hand a half-built ticket to a teammate. The shop
# repo has a stand-in origin (`acs_local_origin`), so the push lands in
# .eval-origin.git. What the run must produce, all through `acs.py handoff
# send`: one package on refs/acs/handoff/EVAL-1, no branch pushed, nothing
# committed, and the sender's work and run left exactly as they were.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_local_origin

acs_ticket "Cap the customer page size at 100" task \
  "list_customers must clamp limit to at most 100."
acs_branch task/EVAL-1-cap-the-customer-page-size-at-100

python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
sed -i.bak 's/"limit": limit}/"limit": min(limit, 100)}/' src/shop/__init__.py && rm -f src/shop/__init__.py.bak
cat > tests/test_page_cap.py <<'PY'
from shop import list_customers


def test_limit_is_capped_at_100():
    assert list_customers(limit=500)["limit"] == 100
PY
