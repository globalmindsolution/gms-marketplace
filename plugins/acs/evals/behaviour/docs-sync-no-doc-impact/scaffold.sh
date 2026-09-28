#!/usr/bin/env bash
# /acs:docs-sync on a changeset that makes no doc stale: EVAL-1 is an internal
# refactor -- list_customers now builds its page through a private helper, with
# a unit test pinning the unchanged behaviour -- so README.md ("20 per page by
# default"), CHANGELOG.md and every other doc are still true. /acs:code's step
# is recorded completed through the plugin's own writers (`acs.py step start`,
# then `post-code.py` fed the result document on stdin), so the run ledger
# names the ticket branch the way a real pipeline leaves it. What the run must
# produce: NO doc change and NO commit, the step completed with an empty
# docs_committed, and a report that says nothing needed updating.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

acs_ticket "Extract the customer page builder" task false \
  "Internal refactor: list_customers builds its page through a private helper. No behaviour change."
acs_branch task/EVAL-1-extract-the-customer-page-builder

python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
cat > src/shop/__init__.py <<'PY'
PAGE_SIZE = 20


def health():
    return "ok"


def _page(items, offset, limit):
    return {"items": list(items), "offset": offset, "limit": limit}


def list_customers(offset=0, limit=PAGE_SIZE):
    return _page([], offset, limit)
PY
cat > tests/test_customers.py <<'PY'
from shop import PAGE_SIZE, list_customers


def test_default_page_is_unchanged():
    assert list_customers() == {"items": [], "offset": 0, "limit": PAGE_SIZE}


def test_offset_and_limit_are_passed_through():
    assert list_customers(40, 10) == {"items": [], "offset": 40, "limit": 10}
PY
git add -A
git commit -qm "EVAL-1 extract the customer page builder"
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "list_customers builds its page through _page(); behaviour unchanged",
 "states": {"branch": "task/EVAL-1-extract-the-customer-page-builder", "docs_updated": []},
 "findings": [], "errors": []}
JSON
