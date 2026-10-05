#!/usr/bin/env bash
# /acs:create-api-contract where the repo turned the `api-contract` LLD type
# OFF. Everything is create-api-contract-cursor-pagination's scaffold -- the
# shop repo, the HLD API landscape and conventions, the documented customers
# interface and EVAL-1, the cursor-pagination story with its analysis and no
# plan -- plus one setting: design.lld_types keeps the data and flow types
# and drops `api-contract`. A disabled type is never written (ADR-0134), so
# the run completes as a recorded no-op, outcome type_disabled, and writes
# nothing. The request does not mention the setting: the skill reads it from
# `acs step start`'s context.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
bash "$here/../create-api-contract-cursor-pagination/scaffold.sh"
. "$here/../_fixtures/repo.sh"  # ACS_DOCS_ANSWERED, for the rewrite below

cat > .acs/settings.json <<JSON
{
  "ticket_prefix": "EVAL",
  $ACS_DOCS_ANSWERED,
  "design": {
    "lld_types": ["logical-erd", "physical-schema", "sequence", "activity", "state"]
  }
}
JSON
git add .acs/settings.json && git commit -qm "acs: no api-contract documents"
