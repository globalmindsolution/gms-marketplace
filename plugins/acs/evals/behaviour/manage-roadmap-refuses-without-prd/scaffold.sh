#!/usr/bin/env bash
# A shipped Python product with no PRD anywhere: /acs:manage-roadmap has no
# features to schedule, so it must refuse and point at /acs:create-prd rather
# than invent a roadmap ahead of the product it plans (ADR-0145). A local bare
# repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_local_origin
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
# The run the skill resumes: a ticketless run (ADR-0127), opened here so its
# id -- and so every grader path -- is deterministic.
acs run new --prompt "Plan a roadmap with no PRD" > /dev/null
