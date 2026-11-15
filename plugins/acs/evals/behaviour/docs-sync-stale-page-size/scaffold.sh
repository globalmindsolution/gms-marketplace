#!/usr/bin/env bash
# /acs:docs-sync on a ticket whose code change made a doc stale: EVAL-1 raised
# PAGE_SIZE from 20 to 50, left UNCOMMITTED on main as /acs:code leaves it
# (ADR-0127), and README.md (committed on main) still says customers are
# listed "20 per page by default". /acs:code's step is recorded completed
# through the plugin's own writers -- `acs.py step start` (which records the
# run's baseline on the clean tree), then `post-code.py` fed the result document
# on stdin -- and the lock is released. What the run must produce: README.md
# saying 50, left uncommitted beside the code; no branch, no commit. A run that
# reads `git diff main...HEAD` sees nothing here.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

acs_ticket "Raise the customer page size to 50" task \
  "Customers are listed 50 per page by default instead of 20."

python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
sed -i.bak 's/^PAGE_SIZE = 20$/PAGE_SIZE = 50/' src/shop/__init__.py && rm -f src/shop/__init__.py.bak
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "PAGE_SIZE raised from 20 to 50 in src/shop/__init__.py",
 "states": {"docs_updated": [], "files": ["src/shop/__init__.py"]},
 "findings": [], "errors": []}
JSON
