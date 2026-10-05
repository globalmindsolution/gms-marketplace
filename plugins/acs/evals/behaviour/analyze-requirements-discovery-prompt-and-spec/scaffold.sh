#!/usr/bin/env bash
# analyze-requirements in Discovery (ADR-0128, ADR-0129): the shop repo with
# its PRD (F3 Order tracking) and architecture docs, and a spec product
# "attached" for the order tracking feature -- written to attachments/, left
# untracked, never committed. Deliberately NOT seeded: a ticket (a Discovery
# run needs none and must not mint one), any acs run (the Skill call's gate,
# or `acs step start --args`, opens one over the invocation), and any feature
# folder under docs/product/features/ -- the run creates the feature's living
# analysis there.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
mkdir -p attachments
cat > attachments/order-tracking-spec.md <<'MD'
# Order tracking — product spec (draft from product)

Shoppers want to know where their order is without emailing support.

## What we want

1. Our two shipping carriers push shipment status changes to us; we keep
   every change per order.
2. `GET /orders/{id}` shows the latest shipment status of the order.
3. The shopper gets an email whenever the shipment status of their order
   changes.
4. A shopper can opt out of tracking emails for one order, from a link in any
   tracking email, without signing in.

## Acceptance criteria

- Carrier status updates are accepted and stored per order.
- GET /orders/{id} returns the latest shipment status of the order.
- The shopper is emailed when the shipment status of their order changes.
- A shopper who opted out of an order's tracking emails gets no further ones
  for that order.
MD
