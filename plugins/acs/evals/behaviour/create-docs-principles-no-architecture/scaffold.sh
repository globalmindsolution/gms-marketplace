#!/usr/bin/env bash
# A shipped Python product with a PRD but NO architecture doc set (no
# hld/tech-stack.md anywhere), no product doc sets yet, and a local bare
# repository standing in for GitHub. create-docs must degrade, not refuse:
# the principles set is authored from the PRD, the repo and the confirmed
# facts, with the missing architecture set recorded.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_prd
acs_local_origin
