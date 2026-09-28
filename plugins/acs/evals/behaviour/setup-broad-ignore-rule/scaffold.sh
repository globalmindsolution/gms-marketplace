#!/usr/bin/env bash
# The shared Python repo, never set up for acs (its .acs/settings.json is
# removed), whose committed .gitignore ignores the WHOLE .acs/ directory.
# Setup's conventions install copies .acs/ci/check-conventions.py, which CI
# must read -- and that broad rule swallows it. detect reports it under
# `swallowed_by_a_broad_rule` and apply returns a warning; SKILL.md Step 3:
# warnings are "what you relay but must not fix for them -- a conflicting
# `!.acs/` negation, or a broad rule swallowing .acs/settings.json, is their
# configuration to decide."
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
git rm -q .acs/settings.json
printf '.acs/\n*.pyc\n' > .gitignore
git add -A && git commit -qm "Ignore local tool state"
