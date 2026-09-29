#!/usr/bin/env bash
# The shared Python repo. An eval run has no network and no `gh` credentials,
# so /acs:update cannot learn the latest release: `gh release list` fails and
# so does the raw.githubusercontent.com fallback. Its Step 2 then owes an
# honest `failed` -- version check unavailable, the manual commands printed --
# and it writes nothing.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
