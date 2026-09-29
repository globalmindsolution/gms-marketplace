#!/usr/bin/env bash
# /acs:docs-sync on a ticket whose code change made a doc stale: EVAL-1 raised
# PAGE_SIZE from 20 to 50 on its branch, and README.md (committed on main)
# still says customers are listed "20 per page by default". /acs:code's step is
# recorded completed through the plugin's own writers -- `acs.py step start`,
# then `post-code.py` fed the result document on stdin -- so the run ledger
# names the ticket branch the way a real pipeline leaves it, and the lock is
# released. What the run must produce: README.md saying 50, as a NEW commit on
# the SAME branch; no new branch, no amended commit.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

acs_ticket "Raise the customer page size to 50" task false \
  "Customers are listed 50 per page by default instead of 20."
acs_branch task/EVAL-1-raise-the-customer-page-size-to-50

python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
sed -i.bak 's/^PAGE_SIZE = 20$/PAGE_SIZE = 50/' src/shop/__init__.py && rm -f src/shop/__init__.py.bak
git commit -qam "EVAL-1 raise the customer page size to 50"
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "PAGE_SIZE raised from 20 to 50 in src/shop/__init__.py",
 "states": {"branch": "task/EVAL-1-raise-the-customer-page-size-to-50", "docs_updated": []},
 "findings": [], "errors": []}
JSON
