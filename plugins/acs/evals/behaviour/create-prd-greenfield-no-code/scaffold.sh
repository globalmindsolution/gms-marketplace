#!/usr/bin/env bash
# A greenfield product: the fixture repo with every line of code, test and
# build config removed, leaving a README that says nothing is built yet (the
# acs settings and identity stay). No PRD. A local bare repository stands in
# for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
git rm -rq src tests pyproject.toml CHANGELOG.md
cat > README.md <<'MD'
# groomr

Online booking for independent dog groomers. Nothing is built yet.
MD
git add -A && git commit -qm "Start groomr from an empty repo"
acs_local_origin
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
# The run the skill resumes: a ticketless run (ADR-0127), opened here so
# its id -- and so every grader path -- is deterministic.
acs run new --prompt "Define the groomr product" > /dev/null
