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
# doc sets, tickets) reads as upstream.
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

- F1 Customer listing (shipped)
- F2 Checkout with card payments (P0)
- F3 Order tracking (P1)

## Non-functional requirements

- NFR1 p95 API latency under 300 ms.
- NFR2 Unit test coverage at least 90%.
MD
  printf '# Roadmap\n\n- Q4: checkout (F2)\n- Q1: order tracking (F3)\n' > docs/product/roadmap.md
  git add -A && git commit -qm "PRD and roadmap"
}

# acs_architecture: a minimal HLD/LLD set, for the skills that read it.
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

# acs_ticket TITLE TYPE [NEEDS_DESIGN] [DESCRIPTION] [FEATURES]: mint a ticket
# through the plugin's own CLI; prints nothing. Ids run EVAL-1, EVAL-2, ... in
# call order. FEATURES (comma-separated PRD feature slugs; default
# $ACS_FEATURES, which a scaffold sets before the call) is what files the
# ticket's documents (ADR-0128): the Development docs under
# docs/development/<feature>/EVAL-<n>/, the design records under
# docs/architecture/lld/<feature>/EVAL-<n>/. No ticket file enters the repo.
acs_ticket() {
  local title="$1" type="$2" needs_design="${3:-false}" description="${4:-}"
  local features="${5:-${ACS_FEATURES:-}}"
  local extra=()
  if [ -n "$features" ]; then
    extra=(--features "$features")
  fi
  python3 "$ACS_SCRIPTS/new-ticket.py" --title "$title" --type "$type" \
    --needs-design "$needs_design" --description "$description" "${extra[@]+"${extra[@]}"}" > /dev/null
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
