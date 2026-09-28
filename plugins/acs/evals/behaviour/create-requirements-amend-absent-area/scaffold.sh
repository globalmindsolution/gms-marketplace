#!/usr/bin/env bash
# Amend mode: the repo already carries a populated requirements set --
# confirmed functional files for customer listing and the health check and a
# non-functional performance file, with a README decision log -- and the code
# has since grown an orders API (src/shop/orders.py) that no area file covers.
# The one absent area is what an amend run adds; every existing file must stay
# byte-for-byte. A local bare repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_prd
acs_architecture
R=docs/requirements
mkdir -p $R/functional $R/non-functional
cat > $R/README.md <<'MD'
# Requirements

## Decision log

| Date | Run |
|---|---|
| 2026-09-01 | Brownfield bootstrap, confirmed by the product owner |
MD
cat > $R/functional/customer-listing.md <<'MD'
# Customer listing

## Behaviour

- `GET /customers` MUST return `{items, offset, limit}` {#listing-shape}
- The listing MUST default `limit` to 20 per page {#listing-page-size}
- The listing MUST start at `offset` 0 when none is given {#listing-offset}
MD
cat > $R/functional/health-check.md <<'MD'
# Health check

- `GET /health` MUST return `ok` {#health-ok}
MD
cat > $R/non-functional/performance.md <<'MD'
# Performance

- API p95 latency MUST stay under 300 ms {#p95}
MD
git add -A && git commit -qm "Confirmed requirements set"
cat > src/shop/orders.py <<'PY'
from shop import PAGE_SIZE


def list_orders(customer_id, offset=0, limit=PAGE_SIZE):
    """GET /orders?customer_id=&offset=&limit= -- one customer's orders."""
    if customer_id is None:
        raise ValueError("customer_id is required")
    return {"customer_id": customer_id, "items": [], "offset": offset, "limit": limit}
PY
cat >> README.md <<'MD'
- `GET /orders?customer_id=&offset=&limit=` lists one customer's orders.
MD
git add -A && git commit -qm "Orders API"
acs_local_origin
