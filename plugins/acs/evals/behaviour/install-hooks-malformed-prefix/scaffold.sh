#!/usr/bin/env bash
# The shared Python repo, never set up for acs CI (no .acs/ci/), whose
# committed .acs/settings.json carries a hand-set lowercase ticket prefix
# ("shop"). /acs:install-hooks' Step 1 resolves the conventions and prints
# MALFORMED -- the prefix must be an uppercase identifier -- and the skill
# must stop there: "Do not install hooks that would only block every
# commit." So Step 2 never copies .acs/ci/ and Step 3 never installs.
#
# The malformed value is written by hand on purpose: it is a user's hand
# edit, and acs's own writer (`acs.py setup apply`) refuses to write it.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
printf '{\n  "ticket_prefix": "shop"\n}\n' > .acs/settings.json
git add -A && git commit -qm "Use the shop ticket prefix"
hooks="$(git rev-parse --git-path hooks)"
rm -f "$hooks/commit-msg" "$hooks/pre-push"
