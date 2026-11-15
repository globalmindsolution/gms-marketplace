#!/usr/bin/env bash
# analyze-requirements (no design judgment, ADR-0139): the shop repo with its PRD
# (F3 order tracking) and architecture docs (one payments flow, nothing inbound
# from third parties), and story EVAL-1 minted through new-ticket.py, then given
# three acceptance criteria. The ticket adds a new inbound integration, a stored
# shape and an outbound flow -- exactly the change an older analysis would have
# called design-significant. A ticket carries no design flag now and the user
# runs /acs:create-tech-design when they want a design, so the analysis must
# map and risk all of it without judging, asking about or recording whether a
# design is needed.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Live order tracking from carrier updates" story \
  "Shoppers see where their order is. Our two shipping carriers push shipment status changes to us; we keep every change per order and show the latest on the order, and we email the shopper when it changes."
printf '%s' '{"features": ["order-tracking"], "acceptance_criteria": [
  "Carrier status updates are accepted and stored per order",
  "GET /orders/{id} returns the latest shipment status of the order",
  "The shopper is emailed when the shipment status of their order changes"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
