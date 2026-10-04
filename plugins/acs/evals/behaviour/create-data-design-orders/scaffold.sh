#!/usr/bin/env bash
# /acs:create-data-design on a ticket that adds persisted data. The shop repo
# with its PRD (plus F4 Orders), an architecture set whose HLD carries the
# conceptual data model (CUSTOMER, ORDER, ORDER_LINE, PRODUCT -- no
# attributes) and the data conventions in hld/cross-cutting.md, and the
# persistence code as built: migrations/0001_customers_products.sql creates
# customers and products, and nothing stores an order yet. lld/README.md
# indexes the one feature already designed (customer-listing).
#
# EVAL-1 is the orders story, minted through new-ticket.py with `--features
# orders` (ADR-0120) and given its acceptance criteria through `acs.py ticket
# save`. No branch and no docs/tickets/ folder: the data design is
# Design-phase work, and with no ticket branch checked out it commits nothing
# and records what it wrote in states.files. design.lld_types is the default,
# so both data types -- logical-erd and physical-schema -- are enabled.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
printf -- '- F4 Orders: shoppers order several products at once and see their past orders (P0)\n' \
  >> docs/product/prd.md
git add -A && git commit -qm "PRD: F4 Orders"

mkdir -p migrations
cat > migrations/0001_customers_products.sql <<'SQL'
-- 0001: customers and products (applied in production).
CREATE TABLE customers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE products (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sku TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- down
-- DROP TABLE products; DROP TABLE customers;
SQL
git add -A && git commit -qm "Customers and products schema"

A=docs/architecture
mkdir -p $A/hld $A/lld
cat > $A/hld/tech-stack.md <<'MD'
# Tech stack

## Languages

Python 3.

## Storage

PostgreSQL 15. Schema changes are plain numbered SQL files under migrations/,
applied in order.
MD
cat > $A/hld/data-model.md <<'MD'
# Data model

Conceptual entities and relationships; attributes live in the low-level
data design of each feature.

```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ ORDER_LINE : contains
  PRODUCT ||--o{ ORDER_LINE : "is ordered as"
```
MD
cat > $A/hld/cross-cutting.md <<'MD'
# Cross-cutting concerns

## Data conventions

- Tables are snake_case plurals (`customers`, `order_lines`).
- Every table has a `BIGINT` identity primary key named `id`; a foreign key is
  `<entity>_id`.
- Every table carries `created_at` and `updated_at` (`TIMESTAMPTZ`).
- Money is stored as integer cents in a column ending `_cents`.
- No soft delete.

## Migration policy

One numbered SQL file per change under migrations/, expand then contract, and
every migration states how it rolls back.
MD
cat > $A/lld/README.md <<'MD'
# Low-level design

| Feature | PRD feature | Folder |
|---|---|---|
| customer-listing | F1 Customer listing | [customer-listing/](customer-listing/) |
MD
git add -A && git commit -qm "Architecture set: HLD and the LLD index"

python3 "$ACS_SCRIPTS/new-ticket.py" --title "Shoppers place multi-item orders" --type story \
  --features orders --description "Shoppers order one or more products in a single order and can list their past orders. This is PRD feature F4." > /dev/null
python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null <<'JSON'
{"acceptance_criteria": [
  "A shopper places an order of one or more products; each order line records the product, the quantity and the unit price at the time of ordering",
  "An order belongs to exactly one customer and records its status (placed, paid, shipped or delivered) and its total in cents",
  "A shopper lists their own orders newest first, 20 per page"
]}
JSON
