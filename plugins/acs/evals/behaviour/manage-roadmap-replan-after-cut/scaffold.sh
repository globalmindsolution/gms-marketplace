#!/usr/bin/env bash
# The PRD already amended (ADR-0145: /acs:create-prd stops at the PRD):
# leadership cut order tracking to a Won't-have, but the roadmap -- in
# /acs:manage-roadmap's shape, approved at version 1 -- still schedules it in
# its own v2.6.0 milestone. Replan mode: the floor's `wont-scheduled` is the
# drift. A local bare repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_moscow_prd wont
acs_roadmap
python3 "$ACS_SCRIPTS/acs.py" design init --status approved \
  docs/product/prd.md docs/product/roadmap.md docs/product/features/*/prd.md > /dev/null
git add -A && git commit -qm "PRD and roadmap"
acs_local_origin
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
# The run the skill resumes: a ticketless run (ADR-0127), opened here so its
# id -- and so every grader path -- is deterministic.
acs run new --prompt "Re-plan the roadmap after the order tracking cut" > /dev/null
