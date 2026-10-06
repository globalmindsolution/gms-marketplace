#!/usr/bin/env bash
# EVAL-1 implemented, committed and recorded: its ticket branch carries the
# change -- committed by an earlier /acs:create-pr whose push never happened --
# and is checked out with a clean working tree, and the /acs:code run that
# produced it is recorded through the plugin's own writers (`acs step start`,
# then the result document /acs:code writes and its post-hook). The run's
# baseline is recorded after that commit, so `acs.py pr plan-commits` has no
# group to propose: create-pr skips its commit phase and goes straight to
# publishing. No /acs:review-code has run, so create-pr's one brake (a review
# that did not pass) has nothing to refuse.
#
# The branch is deliberately NOT pushed: create-pr detects the base with
# `gh repo view` BEFORE it pushes, that call is critical, and `gh` cannot
# reach a forge here -- so the correct run stops before the push and the
# local origin never sees the branch.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Cap the customer page size at 100" task \
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
 "states": {"specs_implemented": ["01-page-size-cap"],
            "files": ["src/shop/__init__.py", "tests/test_customers.py"],
            "tests": {"passed": 3, "failed": 0}, "docs_updated": []},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-code.py" --result-file "$run/steps/code/result.json" > /dev/null
