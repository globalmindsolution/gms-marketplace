#!/usr/bin/env bash
# create-ticket in a repo with no PRD: the shop repo (code, settings, a
# reconciled id counter) and no docs/product at all. Tickets are made from the
# PRD (ADR-0144), so the skill's pre-gate refuses before an id is minted and
# the run points at /acs:create-prd.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
