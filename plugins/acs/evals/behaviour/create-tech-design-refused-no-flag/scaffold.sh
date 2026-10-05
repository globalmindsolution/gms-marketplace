#!/usr/bin/env bash
# create-design (gate refusal): the shop repo with its PRD, and story EVAL-1
# minted with needs_design FALSE through new-ticket.py and given its criteria
# through `acs.py ticket save`. The PreToolUse(Skill) gate
# (pre-create-design.py's subject check) refuses a ticket without the flag:
#   blocked -- ticket EVAL-1 is not flagged needs_design -- /create-design only
#   runs for design-significant tickets; go straight to /acs:code EVAL-1.
# Measured through `dispatch.py pre` with a Skill payload: exit 2, and the only
# file it writes is the session's gate-evidence marker.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
ACS_FEATURES=service-health
acs_ticket "Show the app version on GET /health" story false \
  "GET /health returns the package version alongside ok, so operators can see what is deployed."
printf '%s' '{"acceptance_criteria": [
  "GET /health returns a body carrying ok and the version from pyproject.toml"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
