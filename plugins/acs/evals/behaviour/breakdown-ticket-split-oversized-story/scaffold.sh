#!/usr/bin/env bash
# breakdown-ticket on an oversized STORY: the shop repo (PRD, architecture
# docs) and story EVAL-1 "Storefront order management" (feature
# order-management), minted by new-ticket.py with seven acceptance criteria
# spanning checkout, refunds and a merchant export, given them through `acs.py
# ticket save`. Its plan, published uncommitted to
# docs/development/order-management/EVAL-1/plan.md as /acs:create-impl-plan
# leaves it on a split answer (ADR-0069), records that the decomposition
# exceeds one reviewable PR and names three split seams. Nothing is minted
# yet: the split converts EVAL-1 to an epic that keeps its id, then mints the
# children under it (ADR-0138). Every ticket lives in the workspace only
# (ADR-0128).
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
ACS_FEATURES=order-management
acs_ticket "Storefront order management" story false \
  "Everything a merchant and a shopper need around orders, in one go: card checkout, refunds and a CSV export for accounting."
printf '%s' '{"acceptance_criteria": [
  "POST /checkout charges the card through the payments gateway and creates the order",
  "A declined card returns HTTP 402 with error code card_declined and creates no order",
  "POST /orders/{id}/refund refunds the charge through the payments gateway and marks the order refunded",
  "A refund older than 30 days is rejected with HTTP 409 and error code refund_window_closed",
  "GET /merchant/orders/export returns every order as CSV for accounting",
  "The export lists one row per order with its id, date, total and status",
  "Orders and refunds are stored in two new tables created by a migration"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

mkdir -p docs/development/order-management/EVAL-1
cat > docs/development/order-management/EVAL-1/plan.md <<'MD'
# Plan — EVAL-1: Storefront order management

## Oversize

This decomposition exceeds one reviewable PR: 3 executor tasks over three
concerns, seven acceptance criteria and roughly 1,100 changed lines. The user
chose to split (C-1). Split seams, in order:

1. Checkout and order storage — the migration, POST /checkout and the declined
   card path (AC-1, AC-2, AC-7).
2. Refunds — POST /orders/{id}/refund and the 30-day window (AC-3, AC-4).
3. Merchant CSV export — GET /merchant/orders/export (AC-5, AC-6).

## Contract
delivery_path: complex
owes:
  test_cases: true
  e2e: false
  reason: "Three new endpoints; no browser flow in this repo"

### Executor tasks & file map
- task 1: migrations/0001_orders.sql, src/shop/checkout.py, tests/test_checkout.py
- task 2: src/shop/refunds.py, tests/test_refunds.py
- task 3: src/shop/merchant.py, tests/test_merchant.py
MD
