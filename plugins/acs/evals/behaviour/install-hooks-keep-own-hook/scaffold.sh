#!/usr/bin/env bash
# The shared Python repo, never set up for acs CI (no .acs/ci/), in a clone
# whose owner already keeps a hand-written pre-push hook that runs the tests.
# /acs:install-hooks must bootstrap .acs/ci/ from the plugin templates,
# install commit-msg, and leave the non-acs pre-push hook alone -- its own
# installer refuses to clobber one. Git hooks are per-clone and never
# committed, so the hook is written straight into .git/hooks, as its owner
# would have.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo

hooks="$(git rev-parse --git-path hooks)"
mkdir -p "$hooks"
cat > "$hooks/pre-push" <<'HOOK'
#!/bin/sh
# team pre-push: run the unit tests before every push
exec python3 -m pytest -q
HOOK
chmod +x "$hooks/pre-push"
