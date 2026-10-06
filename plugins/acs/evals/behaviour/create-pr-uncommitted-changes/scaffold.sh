#!/usr/bin/env bash
# EVAL-1 implemented and recorded by /acs:code -- and, as every acs step now
# leaves its work (ADR-0127), UNCOMMITTED on the checked-out main: no step
# before /acs:create-pr branches, stages or commits. Around it, two files the
# commit plan must leave alone:
#
# * notes/release-plan.md -- the user's own untracked note, already there
#   when the run's baseline was recorded (the plan's `excluded`);
# * src/shop/pagination.py -- WIP written after the code run that no step
#   recorded (the plan's `left_out`).
#
# The prompt approves the proposed plan up front, so a correct run commits it
# through `acs.py pr commit` -- tests and code as separate commits on a new
# branch -- and leaves both files uncommitted. gh cannot reach a forge here,
# and base detection (critical) runs before the push, so nothing reaches the
# local origin.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Cap the customer page size at 100" task \
  "list_customers must refuse a limit above 100 with ValueError; 100 itself is allowed."
acs_local_origin

# The user's own note, dirty before the run began.
mkdir -p notes
printf '# Release plan\n\n- ship the page-size cap in 2.5.0\n' > notes/release-plan.md

# /acs:code: the step start records the run's baseline, the implementation is
# written and left uncommitted, and the result records the paths it wrote.
run="$ACS_PARTITION/runs/EVAL-1"
python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
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
cat > "$run/steps/code/result.json" <<'JSON'
{"status": "completed", "outcome": "implemented",
 "summary": "list_customers refuses a limit above MAX_PAGE_SIZE (100)", "iteration": 1,
 "states": {"specs_implemented": ["01-page-size-cap"],
            "files": ["src/shop/__init__.py", "tests/test_customers.py"],
            "tests": {"passed": 3, "failed": 0}, "docs_updated": []},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-code.py" --result-file "$run/steps/code/result.json" > /dev/null

# Work in progress nobody recorded, written after the code run.
cat > src/shop/pagination.py <<'PY'
from shop import PAGE_SIZE


def page_count(total, limit=PAGE_SIZE):
    """WIP: number of pages for `total` customers."""
    return (total + limit - 1) // limit
PY
