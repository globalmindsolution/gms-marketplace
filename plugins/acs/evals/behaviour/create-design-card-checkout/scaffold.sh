#!/usr/bin/env bash
# create-design: the shop repo with its PRD (F2 checkout with card payments,
# NFR1 p95 < 300 ms) and architecture docs (a C4 context naming the external
# payments gateway), and one design-significant story, EVAL-1, minted with
# needs_design true and given its acceptance criteria through the plugin's own
# CLIs (new-ticket.py, `acs.py ticket save`). No branch and no docs/tickets/
# folder: create-design is Design-phase work that runs before either exists.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Checkout with card payments" story true \
  "Shoppers pay for an order by card at checkout. The shop charges the card through the external payments gateway and records the order only once the charge succeeds. This is PRD feature F2."
printf '%s' '{"acceptance_criteria": [
  "POST /checkout charges the shopper card through the payments gateway and returns the created order",
  "A declined card returns HTTP 402 with error code card_declined and records no order",
  "Retrying a checkout with the same idempotency key never charges the card twice"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
