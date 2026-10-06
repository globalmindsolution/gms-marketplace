#!/usr/bin/env bash
# create-ticket on a bug report: the shop repo (PRD with F1 Customer listing
# shipped, architecture docs) and no ticket yet. The request reports a defect
# in the shipped customer listing, so the coordinator types it `bug`
# (ADR-0138), spawns the bug author, has the reviewer judge the draft, and
# writes the bug fields and the regression criterion into the ticket. The
# ticket-id floor is already reconciled (acs_repo), so --allocate mints
# EVAL-1 without asking for --seed-next.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
