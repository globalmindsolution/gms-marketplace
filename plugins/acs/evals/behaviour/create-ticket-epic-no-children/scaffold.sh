#!/usr/bin/env bash
# create-ticket (epic): the shop repo with its PRD (F3 order tracking) and
# roadmap, and nothing else -- no ticket yet. The run mints EVAL-1 itself
# through the mandatory `acs step start --allocate`; a reconciled counter
# (acs_repo) lets it mint without asking for --seed-next.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
