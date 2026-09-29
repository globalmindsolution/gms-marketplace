#!/usr/bin/env bash
# /acs:handoff while a REVIEW is in flight, not code: EVAL-1's /acs:code step
# was started and finished completed through the plugin's own writers
# (`acs.py step start`, then `post-code.py`), and /acs:review-code was then
# started through `acs.py step start` (which takes the run lock and points this
# checkout at the run) and left in_progress -- the state a long session is in
# when the user says "hand this off" halfway through a review. What the run
# must produce, all through handoff.py: the review-code step and its invocation
# finalized `interrupted` with stop_reason context_pressure and the summary,
# the soft context flushed to steps/review-code/handoff-context.md, the
# completed code step untouched, and `/acs:review-code EVAL-1` in the reply.
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
cat > tests/test_page_cap.py <<'PY'
from shop import list_customers


def test_limit_is_capped_at_100():
    assert list_customers(limit=500)["limit"] == 100
PY
git add -A
git commit -qm "EVAL-1 cap the customer page size at 100"
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "list_customers clamps limit to 100",
 "states": {"branch": "task/EVAL-1-cap-the-customer-page-size-at-100", "docs_updated": []},
 "findings": [], "errors": []}
JSON

python3 "$ACS_SCRIPTS/acs.py" step start --step review-code --ticket EVAL-1 > /dev/null 2>&1
