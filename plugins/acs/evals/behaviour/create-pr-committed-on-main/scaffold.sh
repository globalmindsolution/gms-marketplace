#!/usr/bin/env bash
# EVAL-1 implemented and committed straight on main (unpushed), with its
# /acs:code run recorded through the plugin's own writers. The run's baseline is
# taken after that commit, so `acs.py pr plan-commits` proposes no group, but
# reports the commit in `ahead` (origin/main is one commit behind). create-pr
# must cut a feature branch at HEAD rather than push main. `gh` cannot reach a
# forge here, so the base detection then stops it before any push.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Cap the customer page size at 100" task \
  "list_customers must refuse a limit above 100 with ValueError; 100 itself is allowed."
acs_local_origin

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
