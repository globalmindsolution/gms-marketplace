#!/usr/bin/env bash
# A shipped Python product whose repo already carries an eight-section PRD and
# a roadmap with a Release versions table (amend mode: the PRD is found, not
# created). Order tracking is a Should-have with its own milestone, v2.6.0 --
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

- **Must**: customer listing (shipped; G2), card checkout (G1)
- **Should**: order tracking (G1)
- **Could**: saved carts (G1)
- **Won't**: a marketplace for third-party sellers

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
git add -A && git commit -qm "PRD and roadmap"
acs_local_origin
