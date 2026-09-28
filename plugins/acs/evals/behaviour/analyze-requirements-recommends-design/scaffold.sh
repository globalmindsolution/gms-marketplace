#!/usr/bin/env bash
# analyze-requirements (design recommended): the shop repo with its PRD (F3
# order tracking) and architecture docs (one payments flow, nothing inbound
# from third parties), and story EVAL-1 minted with needs_design FALSE through
# new-ticket.py, then given three acceptance criteria. The ticket adds a new
# inbound integration, a stored shape and an outbound flow -- what the
# analysis should flag as design-significant.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Live order tracking from carrier updates" story false \
  "Shoppers see where their order is. Our two shipping carriers push shipment status changes to us; we keep every change per order and show the latest on the order, and we email the shopper when it changes."
printf '%s' '{"acceptance_criteria": [
  "Carrier status updates are accepted and stored per order",
  "GET /orders/{id} returns the latest shipment status of the order",
  "The shopper is emailed when the shipment status of their order changes"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
