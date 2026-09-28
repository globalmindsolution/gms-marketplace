#!/usr/bin/env bash
# EVAL-1 is in review: its ticket branch is pushed to the local origin, the
# /acs:code run is recorded, and a completed /acs:create-pr run recorded PR #7
# -- all through the plugin's own writers (`acs step start`, the result
# document each skill writes, and its post-hook). That recorded PR reference
# is what opens the /acs:merge-pr gate.
#
# The PR's state cannot be read: `gh` has no forge to reach, and the remote
# URL resolves to the local bare repository, so even an authenticated gh finds
# no GitHub remote. Readiness is a critical read, so the correct run refuses
# to merge, deletes nothing and reports gh as unavailable.
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
git add -A
git commit -qm "EVAL-1 Cap the customer page size at 100"
git push -q -u origin "$branch" 2>/dev/null
git checkout -q main

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

python3 "$ACS_SCRIPTS/acs.py" step start --step create-pr --ticket EVAL-1 > /dev/null 2>&1
cat > "$run/steps/create-pr/result.json" <<JSON
{"status": "completed", "summary": "PR #7 ready for review",
 "states": {"pr": {"number": 7, "url": "https://github.com/example/shop/pull/7",
                   "branch": "$branch", "base": "main"}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-pr.py" --result-file "$run/steps/create-pr/result.json" > /dev/null
