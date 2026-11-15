#!/usr/bin/env bash
# create-api-contract (event surface) as a Design skill (ADR-0134): the shop
# repo with an event bus (src/shop/events.py) that already publishes
# order.created, whose machine-readable contract the repo keeps as a JSON
# Schema, schemas/events/order.created.json -- one file per event -- and whose
# design is documented in lld/order-tracking/api/order-events.md (versioned
# `implemented` v1 through `acs.py design init`). Story EVAL-1 adds
# order.shipped. Its approved analysis (a folder, ADR-0133, with no
# `api_surface` key) is in the working tree (main, uncommitted -- ADR-0127);
# there is NO plan. The skill writes documents only: the new event belongs in
# order-events.md, and its JSON Schema is /acs:code's to write later, from a
# plan item -- never this skill's.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
cat > src/shop/events.py <<'PY'
"""The shop event bus: every event is published through `publish`."""
import datetime
import uuid

PUBLISHED = []


def publish(name, payload):
    event = {"event": name, "event_id": str(uuid.uuid4()),
             "occurred_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "schema_version": 1, "payload": payload}
    PUBLISHED.append(event)
    return event
PY
cat > src/shop/orders.py <<'PY'
from shop.events import publish


def create_order(order_id, customer_id):
    return publish("order.created", {"order_id": order_id, "customer_id": customer_id})
PY
mkdir -p schemas/events
cat > schemas/events/order.created.json <<'JSON'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/shop/events/order.created.json",
  "title": "order.created",
  "type": "object",
  "required": ["event", "event_id", "occurred_at", "schema_version", "payload"],
  "properties": {
    "event": {"const": "order.created"},
    "event_id": {"type": "string", "format": "uuid"},
    "occurred_at": {"type": "string", "format": "date-time"},
    "schema_version": {"const": 1},
    "payload": {
      "type": "object",
      "required": ["order_id", "customer_id"],
      "properties": {
        "order_id": {"type": "string"},
        "customer_id": {"type": "string"}
      }
    }
  }
}
JSON
cat >> README.md <<'MD'

## Events

Published on the shop event bus (`shop.events.publish`). Each event's
contract is a JSON Schema in `schemas/events/<event>.json`:

- `order.created` — a shopper placed an order.
MD
git add -A
git commit -qm "Event bus with order.created and its schema"

A=docs/architecture
mkdir -p $A/hld $A/lld/order-tracking/api
cat > $A/hld/integration-map.md <<'MD'
# Integration map

| API | Exposed by | Consumed by | Style |
|---|---|---|---|
| Order events (`order.*` on the shop event bus) | shop | warehouse, email, analytics | async, at-least-once |
MD
cat > $A/hld/cross-cutting.md <<'MD'
# Cross-cutting concerns

## Event conventions

- Every event carries the envelope `event`, `event_id` (uuid4), `occurred_at`
  (RFC 3339) and `schema_version`, and its fields under `payload`.
- Delivery is at-least-once; consumers deduplicate by `event_id`.
- Each event's machine-readable contract is a JSON Schema in
  `schemas/events/<event>.json`.
MD
cat > $A/lld/README.md <<'MD'
# Low-level design

| Feature | PRD feature | Folder |
|---|---|---|
| order-tracking | F3 Order tracking | [order-tracking/](order-tracking/) |
MD
cat > $A/lld/order-tracking/README.md <<'MD'
# order-tracking

PRD feature F3 (Order tracking). HLD containers: shop.

- [api/order-events.md](api/order-events.md) -- the order events.

| Ticket | Change |
|---|---|
MD
cat > $A/lld/order-tracking/api/order-events.md <<'MD'
# Order events -- event bus

## Scope

The `order.*` events the shop publishes on its event bus
(`shop.events.publish`), consumed by the warehouse, email and analytics
(hld/integration-map.md), following hld/cross-cutting.md's event conventions.
Machine-readable contracts: schemas/events/.

## Surface

### event order.created

- **Kind and status**: event, built (src/shop/orders.py:4).
- **Request**: none; published when an order is created.
- **Response**: the envelope (`event_id`, `occurred_at`, `schema_version` 1)
  and the payload `order_id`, `customer_id` (schemas/events/order.created.json).
- **Errors**: none; at-least-once delivery.
- **Traces**: F3 Order tracking.

## Error model

_No error responses: delivery is at-least-once and consumers deduplicate by
`event_id`._

## Compatibility & versioning

`schema_version` 1; only additive payload fields within a version.

## Examples

`{"event": "order.created", "event_id": "0b6f...", "occurred_at": "2026-10-01T09:00:00Z", "schema_version": 1, "payload": {"order_id": "o-1", "customer_id": "c-9"}}`

## Traceability

| Item | Criterion |
|---|---|
| order.created | F3 Order tracking |
MD
python3 "$ACS_SCRIPTS/acs.py" design init --status implemented --feature order-tracking \
  $A/lld/order-tracking/api/order-events.md > /dev/null
git add -A && git commit -qm "Architecture docs"

ACS_FEATURES=order-tracking
acs_ticket "Publish order.shipped when an order ships" story \
  "Other services (the warehouse, email, analytics) need to know when an order ships. Publish an order.shipped event on the shop event bus, alongside the existing order.created."
printf '%s' '{"acceptance_criteria": [
  "When an order is marked shipped, an order.shipped event is published carrying the order id, the carrier and the tracking number",
  "Every order.shipped event carries a unique event_id, occurred_at and schema_version 1",
  "Publishing is at-least-once; consumers deduplicate by event_id"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

D=docs/development/order-tracking/EVAL-1/analysis
mkdir -p $D
cat > $D/README.md <<'MD'
---
ticket: EVAL-1
ready_for_planning: true
---

# Analysis — EVAL-1: Publish order.shipped when an order ships

## Scope and summary

Downstream services need an order.shipped event, published like the existing
order.created on the shop event bus. No HTTP change.

## Contexts

| Context | File |
|---|---|
| Order events | [order-events.md](order-events.md) |

## Refined acceptance criteria

The three criteria are confirmed as written.

## Cross-cutting risks and decisions

The order events interface gains order.shipped: an interface change, designed
with /acs:create-api-contract. A public event other services consume: its
shape must stay backward compatible once published.

## Questions and assumptions

- C-1 payload — answered: order_id, carrier, tracking_number, shipped_at.
- C-2 envelope — answered: as order.created, schema_version 1.

## Verdict

Ready for planning.
MD
cat > $D/order-events.md <<'MD'
---
context: order-events
---

# Order events

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/orders.py | orders | `mark_shipped` publishes order.shipped | src/shop/orders.py:1 |
| src/shop/events.py | events | reused `publish(name, payload)` | src/shop/events.py:1 |
| schemas/events/ | contracts | a schema for the new event, as order.created has | schemas/events/order.created.json |

## Rules and edge cases

At-least-once delivery; consumers deduplicate by event_id.

## Risks

Other services consume the event; its shape is public once published.

## Open questions

_None._

## API notes

New event order.shipped on the shop event bus; no HTTP surface.
MD
