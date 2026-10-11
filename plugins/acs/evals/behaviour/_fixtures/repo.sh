#!/usr/bin/env bash
# Shared building blocks for the behaviour cases: one per shipped skill, each
# asserting what the skill DID (files written, state recorded, reply given),
# not where a prompt routed. Sourced by each case's scaffold.sh, which calls
# the functions it needs; runs only under --scaffold, as the operator, in the
# run directory, before the model's first turn.
#
# Everything is written the way a real consumer repo would carry it, and acs
# state is written through the plugin's OWN writers (new-ticket.py, acs.py) --
# never forged by hand -- so a change to what the plugin writes shows up here.
#
# The plugin is found from this file's path, never from $PATH: $PATH can carry
# an INSTALLED acs build's bin/ (see ../../artifacts/README.md).
set -euo pipefail

BEHAVIOUR_FIXTURES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACS_PLUGIN="$(cd "$BEHAVIOUR_FIXTURES/../../.." && pwd)"
ACS_SCRIPTS="$ACS_PLUGIN/hooks/scripts"
# The partition acs derives from the fixed remote below.
ACS_PARTITION=".acs/state-machine/example-shop"

# The team's saved answers to acs's two document questions (ADR-0132): run
# documents are SHARED in the repo, and the three phase folders are named, so
# no case's skill has to ask where a document goes before it writes. A case
# about those questions sets ACS_DOCS_UNDECIDED=1 before acs_repo (no `docs`
# block at all), or writes its own. A scaffold that rewrites .acs/settings.json
# splices "$ACS_DOCS_ANSWERED" back in.
ACS_DOCS_ANSWERED='"docs": {"share_run_documents": true, "prd_dir": "docs/product", "architecture_dir": "docs/architecture", "development_dir": "docs/development"}'

# acs_repo: a small Python product on `main` whose checkout IS the run
# directory, remote fixed to example/shop (so acs's repo identity and
# partition path are deterministic), ticket prefix EVAL, id counter reconciled
# (the MAR-402 fixture seam: a fresh partition otherwise refuses to mint), and
# the document questions answered (ACS_DOCS_ANSWERED, above).
acs_repo() {
  git init -q -b main
  git remote add origin https://github.com/example/shop.git
  git config user.email eval@example.com
  git config user.name eval
  mkdir -p src/shop tests .acs
  cat > src/shop/__init__.py <<'PY'
PAGE_SIZE = 20


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    return {"items": [], "offset": offset, "limit": limit}
PY
  printf 'from shop import health\n\n\ndef test_health():\n    assert health() == "ok"\n' \
    > tests/test_health.py
  cat > pyproject.toml <<'TOML'
[project]
name = "shop"
version = "2.4.0"

[tool.pytest.ini_options]
pythonpath = ["src"]
TOML
  cat > README.md <<'MD'
# shop

A small storefront service.

## API

- `GET /health` returns `ok`.
- `GET /customers?offset=&limit=` lists customers, 20 per page by default.
MD
  printf '# Changelog\n\n## [2.4.0] - 2026-08-30\n\n- Customer listing.\n' > CHANGELOG.md
  if [ "${ACS_DOCS_UNDECIDED:-0}" = 1 ]; then
    printf '{\n  "ticket_prefix": "EVAL"\n}\n' > .acs/settings.json
  else
    printf '{\n  "ticket_prefix": "EVAL",\n  %s\n}\n' "$ACS_DOCS_ANSWERED" > .acs/settings.json
  fi
  printf '.acs/state-machine/\n.acs/settings.local.json\n.eval-origin.git/\n' > .gitignore
  mkdir -p "$ACS_PARTITION"
  printf '{"next": 1, "reconciled": true, "seed_source": "explicit-user", "seeded_at": "%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ACS_PARTITION/counters.json"
  git add -A
  git commit -qm "shop 2.4.0"
}

# acs_prd: the product docs a downstream skill (architecture, requirements,
# doc sets, tickets) reads as upstream -- the hub prd.md indexing one PRD per
# feature (ADR-0142), each declaring its requirement ids, so a ticket can link
# the PRD (ADR-0144).
acs_prd() {
  mkdir -p docs/product
  cat > docs/product/prd.md <<'MD'
# PRD — shop

## Vision

Let small merchants sell online without running infrastructure.

## Personas

- **Merchant** — lists products, fulfils orders.
- **Shopper** — browses, pays, tracks orders.

## Goals and success metrics

| Goal | Metric |
|---|---|
| G1 Checkout that converts | checkout conversion >= 3% |
| G2 Reliable service | 99.9% monthly availability |

## Features

- F1 [Customer listing](features/customer-listing/prd.md) (shipped; supports G2)
- F2 [Checkout with card payments](features/checkout-with-card-payments/prd.md) (P0; supports G1)
- F3 [Order tracking](features/order-tracking/prd.md) (P1; supports G1)
- F4 [Order management](features/order-management/prd.md) (P1; supports G1)

## Non-functional requirements

- NFR1 p95 API latency under 300 ms.
- NFR2 Unit test coverage at least 90%.
MD
  _acs_feature_prd customer-listing "Customer listing" G2 \
    "a merchant lists customers" "a client pages through customers"
  _acs_feature_prd checkout-with-card-payments "Checkout with card payments" G1 \
    "a shopper pays by card" "a declined card creates no order"
  _acs_feature_prd order-tracking "Order tracking" G1 \
    "a shopper sees each order's status and history" "a shopper is emailed on every status change" \
    "carrier updates move an order's status"
  _acs_feature_prd order-management "Order management" G1 \
    "a merchant refunds an order" "a merchant exports orders as CSV"
  printf '# Roadmap\n\n- Q4: checkout (F2)\n- Q1: order tracking (F3)\n' > docs/product/roadmap.md
  git add -A && git commit -qm "PRD and roadmap"
}

# _acs_feature_prd SLUG NAME GOAL REQUIREMENT...: one feature PRD, R1..Rn in order.
_acs_feature_prd() {
  local slug="$1" name="$2" goal="$3" n=0 req
  shift 3
  mkdir -p "docs/product/features/$slug"
  {
    printf '# %s\n\n## Summary\n\n%s.\n\n## Goals served\n\n- %s\n\n## Requirements\n\n' \
      "$name" "$name" "$goal"
    for req in "$@"; do n=$((n + 1)); printf -- '- **R%d** — %s\n' "$n" "$req"; done
    printf '\n## Acceptance criteria\n\n- Each requirement is observable in the product.\n'
    printf '\n## Dependencies\n\nNone.\n\n## Out of scope\n\nAnything not named above.\n'
  } > "docs/product/features/$slug/prd.md"
}

# acs_architecture: a minimal HLD/LLD set, for the skills that read it.
# acs_moscow_prd [should|wont]: a PRD hub in the MoSCoW shape /acs:create-prd
# writes (ADR-0142) -- the eight sections, a Features index grouped Must /
# Should / Could / Won't linking one PRD per feature -- for the roadmap cases
# (ADR-0145). Order tracking is a Should-have, or, given `wont`, the
# Won't-have leadership cut it to (and Out of scope lists it).
acs_moscow_prd() {
  local tracking="${1:-should}" should wont out
  local line='- [Order tracking](features/order-tracking/prd.md) — follow an order (supports G1)'
  if [ "$tracking" = wont ]; then
    should='- None.'; wont="$line"$'\n''- A marketplace for third-party sellers (supports G1)'
    out=$'- Native mobile apps.\n- Third-party sellers.\n- Order tracking.'
  else
    should="$line"; wont='- A marketplace for third-party sellers (supports G1)'
    out=$'- Native mobile apps.\n- Third-party sellers.'
  fi
  mkdir -p docs/product
  cat > docs/product/prd.md <<MD
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

$should

### Could have

- [Saved carts](features/saved-carts/prd.md) — keep a cart (supports G1)

### Won't have

$wont

## Non-functional requirements

- p95 API latency under 300 ms.
- Unit test coverage at least 90%.

## Constraints & assumptions

- One Python 3.12 service; card payments only through an external gateway.

## Out of scope

$out
MD
  _acs_feature_prd customer-listing "Customer listing" G2 "a merchant lists a product"
  _acs_feature_prd card-checkout "Card checkout" G1 "a shopper pays by card"
  _acs_feature_prd order-tracking "Order tracking" G1 "a shopper follows an order"
  _acs_feature_prd saved-carts "Saved carts" G1 "a shopper keeps a cart"
}

# acs_roadmap [checkout-epics]: roadmap.md beside the PRD in /acs:manage-roadmap's
# shape (ADR-0145): three milestones, each with its version, features, epics and
# a `planned` status, and the Release versions table mapping each to one row.
acs_roadmap() {
  local epics="${1:-none yet}" cell="${1:-—}"
  cat > docs/product/roadmap.md <<MD
# Roadmap — shop

## Milestones

### Storefront — v2.4.0

- Status: planned
- Features: [Customer listing](features/customer-listing/prd.md)
- Epics: none yet

The product listing every merchant starts from.

### Checkout — v2.5.0

- Status: planned
- Features: [Card checkout](features/card-checkout/prd.md)
- Epics: $epics

Shoppers pay by card through the external gateway.

### Order tracking — v2.6.0

- Status: planned
- Features: [Order tracking](features/order-tracking/prd.md)
- Epics: none yet

Shoppers follow an order from payment to delivery.

## Release versions

| Version | Milestone | Epics | Status |
|---|---|---|---|
| v2.4.0 | Storefront | — | planned |
| v2.5.0 | Checkout | $cell | planned |
| v2.6.0 | Order tracking | — | planned |
MD
}

acs_architecture() {
  mkdir -p docs/architecture/hld docs/architecture/lld
  cat > docs/architecture/hld/c4-context.md <<'MD'
# C4 context

```mermaid
C4Context
  Person(shopper, "Shopper")
  System(shop, "shop", "storefront API")
  System_Ext(pay, "Payments gateway")
  Rel(shopper, shop, "browses and pays")
  Rel(shop, pay, "charges cards")
```
MD
  printf '# Flows\n\nCheckout calls the payments gateway, then records the order.\n' \
    > docs/architecture/lld/flows.md
  git add -A && git commit -qm "Architecture docs"
}

# acs_ticket TITLE TYPE [DESCRIPTION] [FEATURES]: mint a ticket through the
# plugin's own CLI; prints nothing. A ticket carries no design flag (ADR-0139).
# Ids run EVAL-1, EVAL-2, ... in call order. FEATURES (comma-separated PRD feature slugs; default
# $ACS_FEATURES, which a scaffold sets before the call) is what files the
# ticket's documents (ADR-0128): the Development docs under
# docs/development/<feature>/EVAL-<n>/, the design records under
# docs/architecture/lld/<feature>/EVAL-<n>/. No ticket file enters the repo.
acs_ticket() {
  local title="$1" type="$2" description="${3:-}"
  local features="${4:-${ACS_FEATURES:-}}"
  local extra=()
  if [ -n "$features" ]; then
    extra=(--features "$features")
  fi
  python3 "$ACS_SCRIPTS/new-ticket.py" --title "$title" --type "$type" \
    --description "$description" "${extra[@]+"${extra[@]}"}" > /dev/null
}

# acs_api_contract_customers: the API contract /acs:create-api-contract
# designs for the cursor-pagination story EVAL-1 in the Design phase
# (ADR-0134), as its coordinator leaves it, uncommitted: the living interface
# document docs/architecture/lld/customer-listing/api/customers.md, versioned
# `approved` for EVAL-1 through `acs.py design init`, and the run record
# docs/architecture/lld/customer-listing/EVAL-1/api-contract.md linking it.
# Documents only: no machine-readable contract.
acs_api_contract_customers() {
  local a=docs/architecture/lld/customer-listing
  mkdir -p "$a/api" "$a/EVAL-1"
  cat > "$a/api/customers.md" <<'MD'
# Customers API -- REST

## Scope

GET /customers, consumed by the admin UI and partner clients.

## Surface

### GET /customers

- **Kind and status**: endpoint, CHANGED.
- **Request**: `cursor` (optional opaque string, planned); `limit` (optional
  integer 1-100, default 20); `offset` (optional, deprecated; ignored when
  `cursor` is given).
- **Response**: 200 `{"items": [...], "limit": 20, "next_cursor": "Y3VzdC0yMA"}`;
  `next_cursor` is `null` on the last page.
- **Errors**: 400 `{"error": "invalid_cursor"}` when `cursor` is not a cursor
  this API issued.
- **Traces**: AC-1, AC-2, AC-3.

## Error model

| Code | HTTP | When | New or existing |
|---|---|---|---|
| `invalid_cursor` | 400 | `cursor` is not a cursor this API issued | new |

## Compatibility & versioning

Backward compatible, in place: `offset` clients keep working, deprecated (C-2).

## Examples

`GET /customers?cursor=Y3VzdC0yMA&limit=20` -> 200 with the next page.
`GET /customers?cursor=%%%` -> 400 `{"error": "invalid_cursor"}`.

## Traceability

| Item | Criterion |
|---|---|
| GET /customers `cursor` | AC-1 |
| GET /customers `next_cursor` | AC-2 |
| `invalid_cursor` | AC-3 |
MD
  python3 "$ACS_SCRIPTS/acs.py" design init --status approved --ticket EVAL-1 \
    --feature customer-listing "$a/api/customers.md" > /dev/null
  cat > "$a/EVAL-1/api-contract.md" <<'MD'
---
ticket: EVAL-1
items: 1
interfaces: ["docs/architecture/lld/customer-listing/api/customers.md"]
---

# API contract — EVAL-1: Cursor pagination for GET /customers

## Scope & sources

GET /customers gains a `cursor` query parameter, a `next_cursor` response
field and an `invalid_cursor` error. Sources: the ticket, the analysis,
src/shop/__init__.py, README.md's API section.

## Interfaces

| Document | Version | Status | Items |
|---|---|---|---|
| docs/architecture/lld/customer-listing/api/customers.md | 1 | approved | GET /customers CHANGED |

## Compatibility & versioning

Backward compatible, in place (C-2).

## Traceability

| Item | Criterion |
|---|---|
| GET /customers `cursor` | AC-1 |
| GET /customers `next_cursor` | AC-2 |
| `invalid_cursor` | AC-3 |

## Gaps

None.
MD
}

# acs_branch NAME: a new branch off main, checked out. Commit onto it yourself.
acs_branch() {
  git checkout -q -b "$1" main
}

# acs_local_origin: a bare repository inside the run directory standing in for
# GitHub, so `git push` and `git fetch` work while the remote URL -- and so
# acs's repo identity -- stays https://github.com/example/shop.git. `gh` still
# has no network: a skill that needs the forge meets a classified failure,
# which is what a case about it asserts.
acs_local_origin() {
  git init -q --bare .eval-origin.git
  git config "url.$PWD/.eval-origin.git.insteadOf" https://github.com/example/shop.git
  git push -q origin main 2>/dev/null
}
