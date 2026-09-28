#!/usr/bin/env bash
# /acs:code standalone, on a PROMPT subject: no ticket, no run, no plan. A
# subject is a ticket, a prompt or a document (§3.11), and nothing gates
# /acs:code on an upstream step, so the run resolves the prompt to a run of its
# own, derives an implicit plan from a read-only survey (recorded at
# runs/<run-id>/steps/code/plan.md), judges it onto a cheap path and
# dispatches that leg.
#
# Only the product repo is seeded. Deliberately NOT seeded: a ticket (the
# prompt must not mint one) and any acs run (the Skill call's gate creates it).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
