#!/usr/bin/env bash
# A teammate's fresh clone of a repo that already ran /acs:setup's CI step:
# .acs/ci/ (checker, commit-msg, pre-push, installer) and the conventions
# workflow are committed -- written by acs's own `setup apply` -- but git
# hooks are per-clone and never committed, so this clone has none (only
# git's *.sample files). No .pre-commit-config.yaml, so /acs:install-hooks
# takes the raw-git-hooks path: the committed installer installs BOTH
# commit-msg and pre-push, and nothing needs copying or committing.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
python3 "$ACS_SCRIPTS/acs.py" setup apply --answers - >/dev/null <<'JSON'
{"settings": {}, "ci": ["conventions"]}
JSON
git add -A && git commit -qm "acs conventions check"
hooks="$(git rev-parse --git-path hooks)"
rm -f "$hooks/commit-msg" "$hooks/pre-push"
