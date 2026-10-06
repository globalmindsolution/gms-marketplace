#!/usr/bin/env bash
# breakdown-ticket on an epic: the shop repo (PRD, architecture docs) and one
# epic, EVAL-1 "Order tracking", minted by new-ticket.py and given its
# acceptance criteria through `acs.py ticket save`. Its tech design is DONE
# and APPROVED: the create-tech-design step was run through the plugin's own
# writers -- `acs step start`, the designer's draft in the step directory with
# its version front matter (`acs.py design init`), the Publish copy to
# docs/architecture/lld/order-tracking/EVAL-1/tech-design.md (left uncommitted,
# as create-tech-design leaves it before any ticket branch exists), result.json
# and post-create-tech-design.py -- and the team's approval through `acs.py
# design status --set approved` (what /acs:set-doc-status runs), so run.json
# records create-tech-design completed and the design the breakdown reads is
# approved. No child exists yet. Every child new-ticket.py mints
# lives in the workspace only (ADR-0128: no ticket file in the repo).
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
ACS_FEATURES=order-tracking
acs_ticket "Order tracking" epic true \
  "Shoppers track an order from payment to delivery: carrier status updates, an order status page, and an email on every status change. PRD feature F3."
printf '%s' '{"acceptance_criteria": [
  "A shopper sees the current status and history of each of their orders",
  "A shopper is emailed on every order status change"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

step="$ACS_PARTITION/runs/EVAL-1/steps/create-tech-design"
published=docs/architecture/lld/order-tracking/EVAL-1/tech-design.md
python3 "$ACS_SCRIPTS/acs.py" step start --step create-tech-design --ticket EVAL-1 > /dev/null 2>&1
cat > "$step/tech-design.md" <<'MD'
# Tech design — EVAL-1: Order tracking

## Decision & options

**Decision:** receive carrier status through signed webhooks (Option A).

### Context

Shoppers track an order from payment to delivery (PRD F3). Two carriers push
shipment status to us.

### Options considered

#### Option A — carriers push signed webhooks

Each carrier calls POST /webhooks/carrier/{carrier}; we verify the signature
and store the status change. Near-real-time; one inbound endpoint to secure.

#### Option B — we poll the carriers' APIs

A scheduled job asks each carrier for every open shipment. No inbound surface,
but minutes of lag and a job that grows with order volume.

### Rationale

Option A: real-time status with no polling load.

### Decision records

- Receive carrier status through signed webhooks.
  /acs:docs-sync writes these as ADRs under docs/architecture/adr/ once the
  changeset exists.

## HLD views affected

- [hld/c4-context.md](../../../hld/c4-context.md) — unversioned: the two
  carriers join as external systems pushing status — change required.

## LLD

The feature's LLD folder `docs/architecture/lld/order-tracking/`.

### API

none yet — run /acs:create-api-contract EVAL-1: POST /webhooks/carrier/{carrier}
and GET /orders/{id}/status.

### Data

none yet — run /acs:create-data-design EVAL-1: the order status history table.

### Flows

none yet — run /acs:create-flows EVAL-1: carrier callback, stored change,
shopper email.

### Components

none yet — run /acs:create-flows EVAL-1: a `tracking` module and a notifier.

## NFRs

Security: carrier callbacks are authenticated with a per-carrier shared
secret. Performance: p95 API latency under 300 ms (NFR1).

## Risks

A forged callback would mislead shoppers; mitigated by signature checks.

### Rollout & migration

Three children, one reviewable PR each, in this order:

| Slice | Type | Scope |
|---|---|---|
| 1. Carrier status webhooks | story | POST /webhooks/carrier/{carrier}: verify the signature, store the status change |
| 2. Order status page | story | GET /orders/{id}/status returns the latest status and its history |
| 3. Status-change emails | task | email the shopper on every stored status change |

Single-step deploy per slice; no data migration beyond the new status table.

## Open questions

none
MD
python3 "$ACS_SCRIPTS/acs.py" design init --status proposed --ticket EVAL-1 \
  --feature order-tracking "$step/tech-design.md" > /dev/null
mkdir -p docs/architecture/lld/order-tracking/EVAL-1
cp "$step/tech-design.md" "$published"
printf '%s' '{"status": "completed", "summary": "reviewer passed on iteration 1",
  "states": {"design_path": "docs/architecture/lld/order-tracking/EVAL-1/tech-design.md",
             "decision": "Receive carrier status through signed webhooks (Option A)"},
  "findings": [], "errors": []}' > "$step/result.json"
python3 "$ACS_SCRIPTS/post-create-tech-design.py" --result-file "$step/result.json" > /dev/null
python3 "$ACS_SCRIPTS/acs.py" design status --set approved --by "Ana Lima <ana@example.com>" \
  "$published" > /dev/null
