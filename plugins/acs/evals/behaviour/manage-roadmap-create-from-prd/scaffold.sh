#!/usr/bin/env bash
# A shipped Python product whose repo carries an approved PRD hub in the
# MoSCoW shape (ADR-0142) and one PRD per feature, but no roadmap yet: create
# mode for /acs:manage-roadmap (ADR-0145). A local bare repository stands in
# for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_moscow_prd
python3 "$ACS_SCRIPTS/acs.py" design init --status approved \
  docs/product/prd.md docs/product/features/*/prd.md > /dev/null
git add -A && git commit -qm "PRD"
acs_local_origin
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
# The run the skill resumes: a ticketless run (ADR-0127), opened here so its
# id -- and so every grader path -- is deterministic.
acs run new --prompt "Plan the roadmap from the PRD" > /dev/null
