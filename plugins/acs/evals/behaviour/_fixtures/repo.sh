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

# acs_repo: a small Python product on `main` whose checkout IS the run
# directory, remote fixed to example/shop (so acs's repo identity and
# partition path are deterministic), ticket prefix EVAL, id counter reconciled
# (the MAR-402 fixture seam: a fresh partition otherwise refuses to mint).
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
  printf '{\n  "ticket_prefix": "EVAL"\n}\n' > .acs/settings.json
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

# acs_ticket TITLE TYPE [NEEDS_DESIGN] [DESCRIPTION]: mint a ticket through the
# plugin's own CLI; prints nothing. Ids run EVAL-1, EVAL-2, ... in call order.
acs_ticket() {
  local title="$1" type="$2" needs_design="${3:-false}" description="${4:-}"
  python3 "$ACS_SCRIPTS/new-ticket.py" --title "$title" --type "$type" \
    --needs-design "$needs_design" --description "$description" > /dev/null
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
