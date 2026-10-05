#!/usr/bin/env bash
# /acs:docs-sync when the ticket's change is NOT in the working tree: EVAL-1
# raised PAGE_SIZE from 20 to 50 and an older acs committed it on a ticket
# branch, with /acs:code's step recorded completed through the plugin's own
# writers -- but the checkout has since been switched back to `main`, whose
# README ("20 per page") is true of main's code. docs-sync has no branch
# precondition any more (ADR-0127): it reads the run's changeset with
# `acs.py changes diff`, which here is EMPTY, so no doc is owed. What the run
# must produce: no branch switched, nothing committed anywhere, README.md
# untouched, and the step completed with an empty `files` -- never a checkout
# of the ticket branch to "find" the change.
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

# Someone switched the checkout back to main afterwards; the change lives
# only on the ticket branch.
git checkout -q main
