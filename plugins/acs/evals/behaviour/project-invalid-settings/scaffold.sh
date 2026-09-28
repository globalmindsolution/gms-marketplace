#!/usr/bin/env bash
# The shared Python repo, whose committed .acs/settings.json carries a
# hand-set merge_strategy acs does not know ("fast-forward"). /acs:project's
# Start runs lib.validate_settings before it reads any evidence: it raises
# GateError, the snippet exits 2, and the skill must surface that stderr
# verbatim and stop -- no mode, no leg (whose own pre-hook and `acs step
# start` refuse the same settings anyway).
#
# The malformed value is written by hand on purpose: it is a user's hand
# edit, and acs's own writer (`acs.py setup apply`) refuses to write it.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
printf '{\n  "ticket_prefix": "EVAL",\n  "merge_strategy": "fast-forward"\n}\n' > .acs/settings.json
git add -A && git commit -qm "Prefer fast-forward merges"
