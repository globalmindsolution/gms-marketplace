#!/usr/bin/env bash
# An approved roadmap in /acs:manage-roadmap's shape whose Checkout milestone
# tracks the epic EVAL-1 -- minted through the plugin's own writer, tracing to
# card-checkout -- and whose delivery merged on main ("EVAL-1 ..." leads the
# commit subject), while every milestone still says `planned`. Status mode:
# the derived status moves Checkout to `delivered` and nothing else; a status
# refresh is not a new version (ADR-0145). A local bare repository stands in
# for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_moscow_prd
acs_ticket "Card checkout" epic "Shoppers pay by card." card-checkout
acs_roadmap EVAL-1
python3 "$ACS_SCRIPTS/acs.py" design init --status approved \
  docs/product/prd.md docs/product/roadmap.md docs/product/features/*/prd.md > /dev/null
git add -A && git commit -qm "PRD and roadmap"
git commit -q --allow-empty -m "EVAL-1 Card checkout (#12)"
acs_local_origin
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
# The run the skill resumes: a ticketless run (ADR-0127), opened here so its
# id -- and so every grader path -- is deterministic.
acs run new --prompt "Refresh the roadmap status" > /dev/null
