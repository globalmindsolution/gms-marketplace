#!/usr/bin/env bash
# The shared Python repo, never set up: no .acs/settings.json. SKILL.md Step 2
# item 5 offers the design-document catalog `setup detect` reports under
# `design`; asked for one opt-in and one opt-out, setup applies exactly that
# through `setup apply`, and the defaults it keeps are not written.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
