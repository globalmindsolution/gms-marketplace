#!/usr/bin/env bash
# /acs:run-e2e-tests on a repo that configures no suite at all: the shop has a
# unit test, but .acs/settings.json configures no suite under `tests`,
# and no plan on the run said anything about e2e impact -- so the pre-hook has
# no evidenced no-op to settle and the skill runs. Its run set resolves to {}:
# it must say so plainly, still write the empty-arrays results artifact, and
# finish the step completed with the honest outcome (`no_harness`: the repo
# configures no suite), never a failure, never a runner of its own invention.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

acs_ticket "Serve the customer listing over HTTP" task false \
  "Expose list_customers as GET /customers on the WSGI front, honouring offset and limit."
