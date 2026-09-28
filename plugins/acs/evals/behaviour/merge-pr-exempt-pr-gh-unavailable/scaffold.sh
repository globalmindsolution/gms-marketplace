#!/usr/bin/env bash
# A one-off, non-ticket hotfix: branch hotfix/health-casing, pushed to the
# local origin, standing in for PR #12. No acs ticket, run or partition exists
# for it -- which is exactly what /acs:merge-pr's exempt `--pr N` mode is for:
# it merges a sanctioned non-ticket PR "without inventing a ticket for it",
# and resolves no run and writes no partition, lock, pointer or state.
#
# The mode's first act, `acs step start --step merge-pr --pr 12`, reads the PR
# with `gh pr view` to check it is OPEN and carries the exempt label (or an
# exempt branch). gh has no forge here, so that read fails and the command
# exits 2: the correct run surfaces it and stops. Whether the PR carries the
# `acs-exempt` label cannot be judged offline at all -- that refusal needs gh.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_local_origin

acs_branch hotfix/health-casing
printf '\n- `GET /health` always answers in lowercase.\n' >> README.md
git commit -qam "Document the lowercase health answer"
git push -q -u origin hotfix/health-casing 2>/dev/null
git checkout -q main
