#!/usr/bin/env bash
# /acs:create-data-design on a PRD feature slug with NO ticket (ADR-0128: no
# skill requires a ticket; a feature slug, a prompt or a document is enough).
# The same repo as create-data-design-orders -- the PRD (plus F4 Orders), an
# architecture set whose HLD carries the conceptual data model (CUSTOMER,
# ORDER, ORDER_LINE, PRODUCT -- no attributes) and the data conventions in
# hld/cross-cutting.md, the persistence code as built (customers and products;
# nothing stores an order yet), and lld/README.md indexing customer-listing --
# but no ticket is minted: the requirements arrive as the invocation's feature
# slug (`orders`) and prompt, which `step start` records in the run's
# requirements.md. design.lld_types is the default, so both data types --
# logical-erd and physical-schema -- are enabled. Nothing is committed: the
# documents stay local (ADR-0126, ADR-0127).
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
