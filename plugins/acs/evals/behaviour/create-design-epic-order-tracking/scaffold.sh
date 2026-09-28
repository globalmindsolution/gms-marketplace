#!/usr/bin/env bash
# create-design (epic): the shop repo with its PRD (F3 order tracking, NFR1
# p95 < 300 ms) and architecture docs (a C4 context with one external system),
# and one epic, EVAL-1 "Order tracking", minted through new-ticket.py (epics
# default to needs_design true, so the gate opens) and given its epic-level
# acceptance criteria through `acs.py ticket save`. No branch, no docs/tickets/
# folder, no children: the design runs before the fan-out.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Order tracking" epic true \
  "Shoppers track an order from payment to delivery: status updates from our two shipping carriers, an order status page, and an email to the shopper on every status change. PRD feature F3."
printf '%s' '{"acceptance_criteria": [
  "A shopper sees the current status and history of each of their orders",
  "Carrier status changes reach the shop within a minute of the carrier recording them",
  "A shopper is emailed on every order status change"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
