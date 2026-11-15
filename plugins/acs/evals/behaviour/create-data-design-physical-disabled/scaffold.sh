#!/usr/bin/env bash
# /acs:create-data-design where the repo turned the physical schema OFF.
# Everything is create-data-design-orders' scaffold -- the shop repo, the HLD
# conceptual data model and data conventions, migrations/0001 for customers
# and products, and EVAL-1, the orders story with `features: [orders]` --
# plus one setting: design.lld_types keeps the logical ERD and drops
# `physical-schema`. A disabled type is never written, so the run owes the
# logical ERD alone, and the request does not mention the setting: the skill
# reads it from `acs step start`'s context.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
bash "$here/../create-data-design-orders/scaffold.sh"
. "$here/../_fixtures/repo.sh"  # ACS_DOCS_ANSWERED, for the rewrite below

cat > .acs/settings.json <<JSON
{
  "ticket_prefix": "EVAL",
  $ACS_DOCS_ANSWERED,
  "design": {
    "lld_types": ["api-contract", "logical-erd", "sequence", "activity", "state"]
  }
}
JSON
git add -A && git commit -qm "acs: no physical-schema documents"
