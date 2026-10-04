#!/usr/bin/env bash
# /acs:audit-design on a repo with code and a PRD but no architecture set:
# no hld/tech-stack.md anywhere, so there is no design to compare the code
# with. The skill must say so, point at /acs:create-architecture, and stop --
# writing no document, no code and no gap report. (docs/product/ is the PRD,
# not a design; the audit must not treat it as one.)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_prd
