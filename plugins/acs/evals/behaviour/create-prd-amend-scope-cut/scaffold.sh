#!/usr/bin/env bash
# A shipped Python product whose repo already carries an eight-section PRD hub
# linking one PRD per feature, and a roadmap with a Release versions table, all
# approved at version 1 (amend mode: the PRD is found, not created). Order tracking is a Should-have with its own milestone, v2.6.0 --
# the feature leadership is about to cut. A local bare repository stands in
# for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
mkdir -p docs/product
cat > docs/product/prd.md <<'MD'
# PRD — shop

## Vision

Let small merchants sell online without running any infrastructure.

## Problem statement

Merchants lose sales because setting up a storefront with payments takes weeks
of engineering they cannot afford.

## Target users & personas

- **Merchant** — lists products, fulfils orders.
- **Shopper** — browses and pays.

## Goals & success metrics

| Goal | Metric |
|---|---|
| G1 Checkout that converts | checkout conversion >= 3.5% of shopper sessions by 2027-06-30 |
| G2 Reliable service | 99.9% monthly availability, every calendar month from 2027-01 |

## Features (prioritized)

### Must have

- [Customer listing](features/customer-listing/prd.md) — shipped (supports G2)
- [Card checkout](features/card-checkout/prd.md) — pay by card (supports G1)

### Should have

- [Order tracking](features/order-tracking/prd.md) — follow an order (supports G1)

### Could have

- [Saved carts](features/saved-carts/prd.md) — keep a cart (supports G1)

### Won't have

- A marketplace for third-party sellers (supports G1)

## Non-functional requirements

- p95 API latency under 300 ms.
- Unit test coverage at least 90%.

## Constraints & assumptions

- One Python 3.12 service; card payments only through an external gateway.

## Out of scope

- Native mobile apps.
- Third-party sellers.
MD
cat > docs/product/roadmap.md <<'MD'
# Roadmap

### Checkout — v2.5.0

Delivers card checkout (Must) and serves G1.

### Order tracking — v2.6.0

Delivers order tracking (Should) and serves G1.

## Release versions

| Version | Milestone | Epic |
|---|---|---|
| v2.5.0 | Checkout | Card checkout |
| v2.6.0 | Order tracking | Order tracking |
MD
# One PRD per feature (ADR-0142), each with the six sections.
feature() {  # slug, name, goal, requirement
  mkdir -p "docs/product/features/$1"
  cat > "docs/product/features/$1/prd.md" <<MD
# $2

## Summary

$2: $4.

## Goals served

- $3

## Requirements

- **R1** — $4

## Acceptance criteria

- Given the feature is live, when a shopper uses it, then $4.

## Dependencies

None.

## Out of scope

Anything not named above.
MD
}
feature customer-listing "Customer listing" G2 "a merchant lists a product"
feature card-checkout "Card checkout" G1 "a shopper pays by card"
feature order-tracking "Order tracking" G1 "a shopper follows an order"
feature saved-carts "Saved carts" G1 "a shopper keeps a cart"
# Every document is versioned and approved (ADR-0122, ADR-0130), through the
# plugin's own writer: the amendment must bump the two it changes to v2,
# re-opened as proposed, and leave the rest at v1.
python3 "$ACS_SCRIPTS/acs.py" design init --status approved \
  docs/product/prd.md docs/product/roadmap.md docs/product/features/*/prd.md > /dev/null
git add -A && git commit -qm "PRD and roadmap"
acs_local_origin
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
# The run the skill resumes: a ticketless run (ADR-0127), opened here so
# its id -- and so every grader path -- is deterministic.
acs run new --prompt "Amend the PRD after the scope cut" > /dev/null
