#!/usr/bin/env bash
# create-ticket asked for technical work in a repo with no PRD: the shop repo
# (code, settings, a reconciled id counter) and no docs/product at all. A task
# is technical work no user sees, so it needs neither a PRD nor a link to one
# (ADR-0144): the run mints a task and completes.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
