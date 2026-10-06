#!/usr/bin/env bash
# /acs:audit-design on a brownfield repo whose versioned architecture set has
# fallen behind the code. The HLD (hld/tech-stack.md marks the set) and one
# LLD feature document were written while the product had a second container,
# a `notifier` the `shop` API called with POST /notifications, and every one
# of them is `status: implemented` -- versioned through `acs.py design init`,
# never by hand. The latest commit removed the notifier and added an orders
# API (GET /orders?customer_id=) no document mentions, and the customer-listing
# LLD still says the page size defaults to 50 while the code (and the README)
# say 20. So the audit has exactly one of each kind to find:
#
#   unimplemented  the notifier container and POST /notifications -- in an
#                  `implemented` document, so a regression, not "planned"
#   undocumented   the orders API (src/shop/orders.py)
#   drifted        the customer page size: 50 in the LLD, 20 in the code
#
# EVAL-1 is the ticket that baselined the set; `acs run new` records the
# standing run the audit works under (no lock, no step), the way the
# review-code cases seed theirs.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }

acs_repo
acs_prd
acs_ticket "Baseline the architecture set" task \
  "Write the HLD and the customer-listing LLD for the shop as built."

mkdir -p src/notifier
cat > src/notifier/__init__.py <<'PY'
"""The notifier: emails a shopper when their customer record changes."""


def notify(customer_id, change):
    return {"customer_id": customer_id, "sent": True, "change": change}
PY
git add -A && git commit -qm "Notifier service"

A=docs/architecture
mkdir -p $A/hld $A/lld/customer-listing/api
cat > $A/hld/tech-stack.md <<'MD'
# Tech stack

## Languages

Python 3.

## Frameworks

pytest.

## Conventions

src layout: one package per container under src/.
MD
cat > $A/hld/c4-container.md <<'MD'
# C4 container

```mermaid
C4Container
  Person(shopper, "Shopper")
  Container(shop, "shop", "Python 3", "storefront API: health and customers")
  Container(notifier, "notifier", "Python 3", "emails a shopper when their record changes")
  Rel(shopper, shop, "browses")
  Rel(shop, notifier, "POST /notifications")
```
MD
cat > $A/hld/integration-map.md <<'MD'
# Integration map

```mermaid
flowchart LR
  lb[load balancer] -->|GET /health sync| shop
  client[shopper client] -->|GET /customers sync| shop
  shop -->|POST /notifications sync| notifier
```
MD
cat > $A/lld/customer-listing/api/customers.md <<'MD'
# Customers API

## GET /customers

Query: `offset` (default 0) and `limit` (default 50).

Response 200: `{items, offset, limit}`.
MD
acs design init --status implemented --ticket EVAL-1 \
  $A/hld/tech-stack.md $A/hld/c4-container.md $A/hld/integration-map.md > /dev/null
acs design init --status implemented --ticket EVAL-1 --feature customer-listing \
  $A/lld/customer-listing/api/customers.md > /dev/null
git add -A && git commit -qm "EVAL-1 Baseline the architecture set"

git rm -rq src/notifier
cat > src/shop/orders.py <<'PY'
from shop import PAGE_SIZE


def list_orders(customer_id, offset=0, limit=PAGE_SIZE):
    """GET /orders?customer_id=&offset=&limit= -- one customer's orders."""
    return {"customer_id": customer_id, "items": [], "offset": offset, "limit": limit}
PY
cat >> README.md <<'MD'
- `GET /orders?customer_id=&offset=&limit=` lists one customer's orders.
MD
git add -A && git commit -qm "Drop the notifier; add the orders API"
acs run new --prompt "Audit the design against the code" > /dev/null
