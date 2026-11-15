#!/usr/bin/env bash
# /acs:create-flows where the repo opted INTO the component documents.
# Everything is create-flows-order-cancellation's scaffold -- the shop repo,
# the HLD, the orders code (placed -> paid -> shipped -> delivered, refunds
# through src/shop/payments.py) and EVAL-1, the cancellation story with
# `features: [orders]` -- plus one setting: design.lld_types adds the
# opt-in `component-detail` and `class` to the defaults. So beside the flow
# and the state machine, the run owes a components/ document with both an
# internals flowchart and a classDiagram. The request does not mention the
# setting: the skill reads it from `acs step start`'s context.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
bash "$here/../create-flows-order-cancellation/scaffold.sh"
. "$here/../_fixtures/repo.sh"  # ACS_DOCS_ANSWERED, for the rewrite below

cat > .acs/settings.json <<JSON
{
  "ticket_prefix": "EVAL",
  $ACS_DOCS_ANSWERED,
  "design": {
    "lld_types": ["api-contract", "logical-erd", "physical-schema", "sequence", "activity",
                  "state", "component-detail", "class"]
  }
}
JSON
git add -A && git commit -qm "acs: component and class documents on"
