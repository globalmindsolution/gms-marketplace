#!/usr/bin/env bash
# /acs:handoff asked to send with NOTHING to send: a clean checkout of the shop
# repo with a stand-in origin, no ticket, and no run this checkout points at.
# The user asks to hand "what I'm working on" to a teammate without naming a
# ticket. What the run must produce: nothing -- `acs.py run show` refuses
# (no current run), so no package is built and no ref is pushed -- and a reply
# that says there is nothing to hand off and how to name a ticket.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_local_origin
