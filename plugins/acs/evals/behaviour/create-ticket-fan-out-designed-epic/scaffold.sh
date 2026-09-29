#!/usr/bin/env bash
# create-ticket --fan-out: the shop repo (PRD, architecture docs) and one
# epic, EVAL-1 "Order tracking", minted by new-ticket.py and given its
# acceptance criteria through `acs.py ticket save`. Its design is DONE: the
# create-design step was run through the plugin's own writers -- `acs step
# start`, the designer's draft in the step directory, the Publish copy to
# docs/tickets/EVAL-1/design.md (left uncommitted, as create-design leaves it
# before any ticket branch exists), result.json and post-create-design.py --
# so run.json records create-design completed and the fan-out's design
# precondition holds. No child exists yet. Because docs/tickets/ now exists,
# every child new-ticket.py mints lives at docs/tickets/EVAL-<n>/ticket.md.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
acs_ticket "Order tracking" epic true \
  "Shoppers track an order from payment to delivery: carrier status updates, an order status page, and an email on every status change. PRD feature F3."
printf '%s' '{"acceptance_criteria": [
  "A shopper sees the current status and history of each of their orders",
  "A shopper is emailed on every order status change"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

step="$ACS_PARTITION/runs/EVAL-1/steps/create-design"
python3 "$ACS_SCRIPTS/acs.py" step start --step create-design --ticket EVAL-1 > /dev/null 2>&1
cat > "$step/design.md" <<'MD'
# Design — EVAL-1: Order tracking

## Context & constraints

Shoppers track an order from payment to delivery (PRD F3). Two carriers push
shipment status to us. Security: carrier callbacks are authenticated with a
per-carrier shared secret. Performance: p95 API latency under 300 ms (NFR1).

## Options considered

### Option A — carriers push signed webhooks

Each carrier calls POST /webhooks/carrier/{carrier}; we verify the signature
and store the status change. Near-real-time; one inbound endpoint to secure.

### Option B — we poll the carriers' APIs

A scheduled job asks each carrier for every open shipment. No inbound surface,
but minutes of lag and a job that grows with order volume.

## Decision & rationale

Option A: signed carrier webhooks. Real-time status with no polling load.

### Decision records

- Receive carrier status through signed webhooks.
  /acs:code commits these as ADRs under docs/adr/ as part of its
  documentation updates.

## Architecture

A `tracking` module stores status changes per order; the order status page
reads the latest; a notifier emails the shopper on each change.

```mermaid
sequenceDiagram
  participant K as Carrier
  participant T as shop tracking
  participant N as notifier
  K->>T: POST /webhooks/carrier/{carrier} (signed)
  T->>N: status changed
  N-->>K: 204
```

### Architecture conformance

Required architecture changes: docs/architecture/lld/flows.md gains the
tracking sequence above.

## Impact & risks

A forged callback would mislead shoppers; mitigated by signature checks.

## Rollout/migration

Three children, one reviewable PR each, in this order:

| Slice | Type | Scope |
|---|---|---|
| 1. Carrier status webhooks | story | POST /webhooks/carrier/{carrier}: verify the signature, store the status change |
| 2. Order status page | story | GET /orders/{id}/status returns the latest status and its history |
| 3. Status-change emails | task | email the shopper on every stored status change |

Single-step deploy per slice; no data migration beyond the new status table.
MD
mkdir -p docs/tickets/EVAL-1
cp "$step/design.md" docs/tickets/EVAL-1/design.md
printf '%s' '{"status": "completed", "summary": "design reviewer passed on iteration 1",
  "states": {"design_path": "docs/tickets/EVAL-1/design.md",
             "decision": "Receive carrier status through signed webhooks (Option A)"},
  "findings": [], "errors": []}' > "$step/result.json"
python3 "$ACS_SCRIPTS/post-create-design.py" --result-file "$step/result.json" > /dev/null
