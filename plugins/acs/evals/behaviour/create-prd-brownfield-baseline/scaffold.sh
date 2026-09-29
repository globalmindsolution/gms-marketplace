#!/usr/bin/env bash
# A shipped Python product with no PRD yet (brownfield), and a local bare
# repository standing in for GitHub so the delivery branch can be pushed.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_local_origin
