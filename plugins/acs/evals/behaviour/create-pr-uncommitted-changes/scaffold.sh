#!/usr/bin/env bash
# EVAL-1 implemented, committed and recorded on its ticket branch -- and the
# branch is checked out with UNCOMMITTED work on top: an edit to the module
# and a new, untracked test file that /acs:code never recorded.
#
# create-pr never commits new work: "if uncommitted implementation changes
# exist, that is /acs:code's job: surface it as a problem and stop", and in a
# non-interactive run it does not guess -- it finishes `failed`. gh cannot
# reach a forge here either, and base detection (critical) runs before the
# push, so every correct run stops before pushing whichever it meets first.
# What the case pins: the uncommitted work is neither committed, stashed nor
# discarded, and nothing reaches the local origin.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Cap the customer page size at 100" task false \
  "list_customers must refuse a limit above 100 with ValueError; 100 itself is allowed."
acs_local_origin

branch=task/EVAL-1-cap-the-customer-page-size-at-100
acs_branch "$branch"
cat > src/shop/__init__.py <<'PY'
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    if limit > MAX_PAGE_SIZE:
        raise ValueError("limit must be at most %d" % MAX_PAGE_SIZE)
    return {"items": [], "offset": offset, "limit": limit}
PY
cat > tests/test_customers.py <<'PY'
import pytest

from shop import list_customers


def test_limit_of_100_is_allowed():
    assert list_customers(limit=100)["limit"] == 100


def test_limit_above_100_is_refused():
    with pytest.raises(ValueError):
        list_customers(limit=101)
PY
git add -A
git commit -qm "EVAL-1 Cap the customer page size at 100"

run="$ACS_PARTITION/runs/EVAL-1"
python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
cat > "$run/steps/code/result.json" <<JSON
{"status": "completed", "outcome": "implemented",
 "summary": "list_customers refuses a limit above MAX_PAGE_SIZE (100)", "iteration": 1,
 "states": {"branch": "$branch", "tasks_implemented": ["01-page-size-cap"],
            "tests": {"passed": 3, "failed": 0}, "docs_updated": []},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-code.py" --result-file "$run/steps/code/result.json" > /dev/null

# Work in progress nobody recorded: left uncommitted on the checked-out branch.
cat >> src/shop/__init__.py <<'PY'


def page_count(total, limit=PAGE_SIZE):
    """WIP: number of pages for `total` customers."""
    return (total + limit - 1) // limit
PY
printf 'from shop import page_count\n\n\ndef test_page_count():\n    assert page_count(41, 20) == 3\n' \
  > tests/test_page_count.py
