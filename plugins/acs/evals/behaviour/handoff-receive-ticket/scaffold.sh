#!/usr/bin/env bash
# /acs:handoff receiving a ticket: a teammate (Lan) handed EVAL-1 over from her
# own clone. The scaffold plays her machine in a throwaway clone OUTSIDE the
# run directory -- same remote URL, so the same repo identity, pointed at this
# run's stand-in origin -- mints EVAL-1 there, starts its /acs:code step, leaves
# the work uncommitted and sends it with the plugin's own `acs.py handoff
# send`. Her clone is then deleted: all that remains is the package on
# .eval-origin.git's refs/acs/handoff/EVAL-1. This checkout is clean on main
# with no EVAL-1 state at all. What the run must produce, all through `acs.py
# handoff receive`: the work applied as uncommitted changes, the ticket and
# run restored into this workspace, nothing committed, and a reply showing
# Lan's note and the continue command.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_local_origin

origin="$PWD/.eval-origin.git"
lan="$(mktemp -d)"
trap 'rm -rf "$lan"' EXIT
git clone -q -b main "$origin" "$lan/shop"
(
  cd "$lan/shop"
  git remote set-url origin https://github.com/example/shop.git
  git config "url.$origin.insteadOf" https://github.com/example/shop.git
  git config user.email lan@example.com
  git config user.name Lan
  mkdir -p "$ACS_PARTITION"
  printf '{"next": 1, "reconciled": true, "seed_source": "explicit-user", "seeded_at": "%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ACS_PARTITION/counters.json"
  acs_ticket "Cap the customer page size at 100" task false \
    "list_customers must clamp limit to at most 100."
  acs_branch task/EVAL-1-cap-the-customer-page-size-at-100
  python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
  sed -i.bak 's/"limit": limit}/"limit": min(limit, 100)}/' src/shop/__init__.py
  rm -f src/shop/__init__.py.bak
  cat > tests/test_page_cap.py <<'PY'
from shop import list_customers


def test_limit_is_capped_at_100():
    assert list_customers(limit=500)["limit"] == 100
PY
  cat > "$lan/note.md" <<'MD'
## Done
- The clamp in src/shop/__init__.py and its test, tests/test_page_cap.py.

## In flight
- Nothing: the code step is open, the tests have not been run yet.

## Next
1. Run the tests, then review the change.

## Decisions
- A limit above 100 is silently clamped to 100, never rejected with a 400 (agreed with the API owner, not written down anywhere else).
MD
  python3 "$ACS_SCRIPTS/acs.py" handoff send --ticket EVAL-1 --note-file "$lan/note.md" > /dev/null
)
