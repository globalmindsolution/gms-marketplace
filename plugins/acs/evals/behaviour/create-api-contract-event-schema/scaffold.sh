#!/usr/bin/env bash
# create-api-contract (event surface): the shop repo with an event bus
# (src/shop/events.py) that already publishes order.created, whose contract
# the repo keeps as a JSON Schema, schemas/events/order.created.json -- one
# file per event. Story EVAL-1 adds order.shipped. The working tree (main, uncommitted -- ADR-0127) carries
# its published analysis (api_surface: true: a new event, no HTTP change) and
# plan (owes api_contract: true), written in their SKILL.md formats and
# left uncommitted as their coordinators do with cp.
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
acs_ticket "Publish order.shipped when an order ships" story false \
  "Other services (the warehouse, email, analytics) need to know when an order ships. Publish an order.shipped event on the shop event bus, alongside the existing order.created."
printf '%s' '{"acceptance_criteria": [
  "When an order is marked shipped, an order.shipped event is published carrying the order id, the carrier and the tracking number",
  "Every order.shipped event carries a unique event_id, occurred_at and schema_version 1",
  "Publishing is at-least-once; consumers deduplicate by event_id"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

mkdir -p docs/tickets/EVAL-1
cat > docs/tickets/EVAL-1/analysis.md <<'MD'
---
ticket: EVAL-1
ready_for_planning: true
api_surface: true
needs_design_recommendation: false
---

# Analysis — EVAL-1: Publish order.shipped when an order ships

## Problem restated

Downstream services need an order.shipped event, published like the existing
order.created on the shop event bus.

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/orders.py | orders | `mark_shipped` publishes order.shipped | src/shop/orders.py:1 |
| src/shop/events.py | events | reused `publish(name, payload)` | src/shop/events.py:1 |
| schemas/events/ | contracts | a schema for the new event, as order.created has | schemas/events/order.created.json |
| tests/test_order_events.py | tests | new unit tests | tests/ holds only test_health.py |

## Questions

- C-1 payload — answered: order_id, carrier, tracking_number, shipped_at.
- C-2 envelope — answered: event_id (uuid4), occurred_at, schema_version 1, as order.created.

## Assumptions

_None._

## Risks

- A public event contract other services consume: its shape must stay
  backward compatible once published.

## Refined acceptance criteria

The three criteria on the ticket are confirmed as written.

## Verdict

Ready for planning; api_surface true (a new event, no HTTP change); no design needed.
MD
cat > docs/tickets/EVAL-1/plan.md <<'MD'
# Plan — EVAL-1: Publish order.shipped when an order ships

## Approach

`mark_shipped(order_id, carrier, tracking_number)` in `src/shop/orders.py`
publishes `order.shipped` through `src/shop/events.py`'s `publish`, with the
same envelope as order.created. A JSON Schema for the event joins
`schemas/events/`, the repo's existing convention.

## Tests

| AC | Test (tests/test_order_events.py) |
|---|---|
| AC-1 | marking an order shipped publishes order.shipped with order_id, carrier, tracking_number |
| AC-2 | the event carries a uuid event_id, occurred_at and schema_version 1 |
| AC-3 | publishing twice yields two events with distinct event_id values |

Run `python3 -m pytest -q --cov=src --cov-fail-under=90`; coverage target 90%.

## Contract
delivery_path: small
owes:
  api_contract: true
  test_cases: true
  e2e: false
  reason: "A new public event other services consume; no HTTP change"

### Executor tasks & file map
- task 1: src/shop/orders.py, tests/test_order_events.py
MD
