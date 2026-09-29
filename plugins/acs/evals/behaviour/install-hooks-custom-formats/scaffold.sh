#!/usr/bin/env bash
# A clone of a repo whose team changed the conventions with /acs:setup: the
# commit subject is `{ticket_id}: {summary}` (a colon after the id), branches
# are `{ticket_id}/{slug}`, and the commit-message check -- off by default --
# is turned on (enforcement.checks.commit_message). All of it is written by
# acs's own `setup apply`, with the conventions CI step, and committed. The
# clone has no git hooks yet. /acs:install-hooks must install hooks that
# enforce THOSE formats: the installed commit-msg hook runs the committed
# checker against the committed settings, so `EVAL-7: Add wishlist export`
# passes and `EVAL-7 Add wishlist export` (the default format) is refused.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
python3 "$ACS_SCRIPTS/acs.py" setup apply --answers - >/dev/null <<'JSON'
{"settings": {"formats": {"commit_message": "{ticket_id}: {summary}",
                          "branch_name": "{ticket_id}/{slug}"},
              "enforcement": {"checks": {"commit_message": true}}},
 "ci": ["conventions"]}
JSON
git add -A && git commit -qm "EVAL-1: Team conventions"
hooks="$(git rev-parse --git-path hooks)"
rm -f "$hooks/commit-msg" "$hooks/pre-push"
