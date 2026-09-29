#!/usr/bin/env bash
# /acs:docs-sync's hard precondition, broken: EVAL-1 raised PAGE_SIZE from 20
# to 50 on its ticket branch (README.md on main still says "20 per page"), and
# /acs:code's step is recorded completed through the plugin's own writers with
# states.branch naming that branch -- but the checkout has since been switched
# back to `main`. The skill: "confirm [the current branch] matches the
# ticket's recorded branch ... A mismatch is a fail-fast error -- stop and
# surface it; never silently switch branches." What the run must produce:
# nothing committed anywhere, HEAD still on main, and the step finished
# `failed` with the mismatch surfaced.
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

# Someone switched the checkout back to main afterwards.
git checkout -q main
