#!/usr/bin/env bash
# create-tech-design on a plain story (ADR-0139): the shop repo with its PRD, and
# story EVAL-1 minted through new-ticket.py and given its criteria through
# `acs.py ticket save`. A ticket carries no design flag, so nothing marks this
# story as needing a design: the user asking for one IS the ask, and the
# PreToolUse(Skill) gate (pre-create-tech-design.py's subject check) admits it.
# The case asserts the skill runs to a published tech design on that ask alone.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
ACS_FEATURES=service-health
acs_ticket "Show the app version on GET /health" story \
  "GET /health returns the package version alongside ok, so operators can see what is deployed."
printf '%s' '{"acceptance_criteria": [
  "GET /health returns a body carrying ok and the version from pyproject.toml"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
