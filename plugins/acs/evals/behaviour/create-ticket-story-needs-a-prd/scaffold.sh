#!/usr/bin/env bash
# create-ticket asked for user-facing work in a repo with no PRD: the shop repo
# (code, settings, a reconciled id counter) and no docs/product at all. Product
# work is made from the PRD (ADR-0144): the run starts (the type is decided after
# it does) but mints nothing real -- it ends failed, pointing at /acs:create-prd.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
