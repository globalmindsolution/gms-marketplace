#!/usr/bin/env bash
# The shared Python repo, never set up for acs: its .acs/settings.json is
# removed, so /acs:setup's detect sees a fresh init (no project settings, no
# CI install). The user keeps every default format, wants the convention
# check in CI, and -- the branch the setup/ cases never take -- turns ON the
# local commit-message check that is off by default under squash merges
# (enforcement.checks.commit_message: true, SKILL.md Step 2's Convention
# check row).
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
git rm -q .acs/settings.json
git commit -qm "No acs settings yet"
