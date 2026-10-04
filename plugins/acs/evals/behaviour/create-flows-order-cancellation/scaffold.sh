#!/usr/bin/env bash
# /acs:create-flows on a ticket that changes an entity's lifecycle. The shop
# repo with its PRD (plus F4 Orders), an architecture set (tech stack, C4
# containers with the external payments gateway, the conceptual data model)
# and the orders code as built: src/shop/orders.py moves an order through
# placed -> paid -> shipped -> delivered, and src/shop/payments.py charges
# and refunds through the gateway. Nothing cancels an order yet.
#
# EVAL-1 adds cancellation, minted through new-ticket.py with `--features
# orders` (ADR-0120) and given its criteria through `acs.py ticket save`: a
# placed order is cancelled outright, a paid one is refunded first, and a
# shipped or delivered one is refused with 409. So the flow (cancel-order)
# carries messages that change the order's state, and the order's state
# machine must gain exactly the transitions those messages imply --
# placed -> cancelled and paid -> cancelled, never shipped -> cancelled.
# design.lld_types is the default: sequence, activity and state on,
# component-detail and class off, so nothing under components/ is owed.
# The documents stay local (ADR-0126): nothing is committed, the paths go to
# states.files.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
printf -- '- F4 Orders: shoppers order products, pay, and follow the order to delivery (P0)\n' \
  >> docs/product/prd.md
git add -A && git commit -qm "PRD: F4 Orders"

cat > src/shop/payments.py <<'PY'
"""Client for the external payments gateway."""


def charge(token, amount_cents, idempotency_key):
    return {"payment_id": "pay_" + idempotency_key, "status": "approved"}


def refund(payment_id):
    return {"payment_id": payment_id, "status": "refunded"}
PY
cat > src/shop/orders.py <<'PY'
"""Orders and their lifecycle: placed -> paid -> shipped -> delivered."""

from shop import payments

TRANSITIONS = {
    "placed": {"paid"},
    "paid": {"shipped"},
    "shipped": {"delivered"},
    "delivered": set(),
}


class IllegalTransition(Exception):
    pass


def _move(order, status):
    if status not in TRANSITIONS[order["status"]]:
        raise IllegalTransition("%s -> %s" % (order["status"], status))
    order["status"] = status
    return order


def place_order(customer_id, lines):
    """POST /orders"""
    return {"customer_id": customer_id, "lines": lines, "status": "placed", "payment_id": None}


def pay_order(order, token):
    """POST /orders/{id}/pay"""
    total = sum(line["quantity"] * line["unit_price_cents"] for line in order["lines"])
    order["payment_id"] = payments.charge(token, total, str(id(order)))["payment_id"]
    return _move(order, "paid")


def ship_order(order):
    """Warehouse event: the parcel left."""
    return _move(order, "shipped")


def deliver_order(order):
    """Carrier event: the parcel arrived."""
    return _move(order, "delivered")
PY
git add -A && git commit -qm "Orders: place, pay, ship, deliver"

A=docs/architecture
mkdir -p $A/hld $A/lld
cat > $A/hld/tech-stack.md <<'MD'
# Tech stack

## Languages

Python 3.

## Conventions

src layout: the shop package under src/shop, one module per feature.
MD
cat > $A/hld/c4-container.md <<'MD'
# C4 container

```mermaid
C4Container
  Person(shopper, "Shopper")
  Container(shop, "shop", "Python 3", "storefront API: customers and orders")
  System_Ext(gateway, "Payments gateway", "charges and refunds cards")
  Rel(shopper, shop, "places, pays for and follows orders")
  Rel(shop, gateway, "charge, refund")
```
MD
cat > $A/hld/data-model.md <<'MD'
# Data model

```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ ORDER_LINE : contains
```
MD
cat > $A/lld/README.md <<'MD'
# Low-level design

| Feature | PRD feature | Folder |
|---|---|---|
| customer-listing | F1 Customer listing | [customer-listing/](customer-listing/) |
MD
git add -A && git commit -qm "Architecture set: HLD and the LLD index"

python3 "$ACS_SCRIPTS/new-ticket.py" --title "Shoppers cancel an order before it ships" \
  --type story --features orders \
  --description "A shopper can cancel an order until it ships; a paid order is refunded through the payments gateway first. Part of PRD feature F4." > /dev/null
python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null <<'JSON'
{"acceptance_criteria": [
  "POST /orders/{id}/cancel on a placed order marks it cancelled and returns 200",
  "Cancelling a paid order refunds its payment through the payments gateway, then marks it cancelled",
  "Cancelling a shipped or delivered order returns 409 order_not_cancellable and changes nothing"
]}
JSON
