#!/usr/bin/env bash
# create-impl-plan (oversize -> split): the shop repo with its PRD and
# architecture docs, story EVAL-1 "Storefront order management" minted with TEN
# acceptance criteria spanning checkout, history, refunds, a merchant
# dashboard, an export, emails and a migration, and the working tree (main, uncommitted -- ADR-0127) carrying
# its published analysis (written in SKILL.md's format and left uncommitted, as the
# analyze-requirements coordinator does with cp). Far beyond the sizing
# rubric's ~400 lines / ~7 criteria / ~4 tasks: the planner's oversize signal
# must fire.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Storefront order management" story false \
  "Everything a merchant and a shopper need around orders, in one go: card checkout, order history, refunds, a merchant order dashboard, a CSV export for accounting, and email notifications."
printf '%s' '{"acceptance_criteria": [
  "POST /checkout charges the card through the payments gateway and creates the order",
  "A declined card returns HTTP 402 with error code card_declined and creates no order",
  "GET /orders lists the signed-in shopper order history, newest first, 20 per page",
  "GET /orders/{id} returns one order with its line items and payment status",
  "POST /orders/{id}/refund refunds the charge through the payments gateway and marks the order refunded",
  "A refund older than 30 days is rejected with HTTP 409 and error code refund_window_closed",
  "The merchant dashboard lists every order with filters by status and date range",
  "GET /merchant/orders/export returns every order as CSV for accounting",
  "The shopper is emailed on order confirmation and on refund",
  "Orders, line items and refunds are stored in three new tables created by a migration"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

mkdir -p docs/tickets/EVAL-1
cat > docs/tickets/EVAL-1/analysis.md <<'MD'
---
ticket: EVAL-1
ready_for_planning: true
api_surface: true
needs_design_recommendation: false
---

# Analysis — EVAL-1: Storefront order management

## Problem restated

Merchants and shoppers need checkout, order history, refunds, a merchant
dashboard, an accounting export and email notifications -- none of which
exist in the shop today.

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/checkout.py | checkout | new: charge through the gateway, create the order | src/shop/__init__.py holds no order code |
| src/shop/orders.py | orders | new: history, detail, refunds | as above |
| src/shop/merchant.py | merchant | new: dashboard listing, CSV export | as above |
| src/shop/notify.py | notifications | new: confirmation and refund emails | as above |
| migrations/0001_orders.sql | storage | new: orders, line_items, refunds tables | no migrations/ directory yet |
| tests/ | tests | new suites for each module | tests/ holds only test_health.py |
| README.md | docs | API section gains six endpoints | README.md:5 |

## Questions

_None._

## Assumptions

- Emails go through an outbound email API.

## Risks

- Payments (charges and refunds) and a new stored shape (three tables): both
  load-bearing. Six new public endpoints.

## Refined acceptance criteria

The ten criteria on the ticket are confirmed as written.

## Verdict

Ready for planning; api_surface true; no design needed. The surface spans
five components and ten criteria.
MD
