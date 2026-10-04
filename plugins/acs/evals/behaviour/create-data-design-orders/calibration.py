"""Calibration plays for create-data-design-orders (see
tests/evals/check_grader_calibration.py).

IDEAL does what /acs:create-data-design's coordinator and its subagents do,
through the plugin's own writers where they exist: `acs step start`, the
`clarify.py add` answers the prompt relayed, one un-sliced survey (no feature
`data/` documents yet, so no gap analysis), ONE write designer writing both
documents and the feature README, version front matter through `acs.py design
init --status proposed` (nothing of the orders model is built), the three
reviewer slices joined with `acs.py notes merge`, the $0 checks, then
result.json with every written path in states.files and the real post-hook.
Nothing is committed: no ticket branch is checked out.
"""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
STEP = ".acs/state-machine/example-shop/runs/EVAL-1/steps/create-data-design"
L = "docs/architecture/lld"
DATA = L + "/orders/data"
ERD = DATA + "/logical-erd.md"
SCHEMA = DATA + "/physical-schema.md"
FEATURE_README = L + "/orders/README.md"

LOGICAL = """# Logical ERD -- orders

## Scope

The entities PRD feature F4 (Orders) persists for EVAL-1: an order a customer
places and its lines. Details the HLD's conceptual ORDER and ORDER_LINE
(hld/data-model.md); CUSTOMER and PRODUCT exist already.

## Entities

- **CUSTOMER** (built) -- id (PK), email, name.
- **PRODUCT** (built) -- id (PK), sku, title, price.
- **ORDER** (planned) -- id (PK), customer_id (FK), status (placed, paid, shipped,
  delivered), total, placed_at.
- **ORDER_LINE** (planned) -- id (PK), order_id (FK), product_id (FK), quantity,
  unit_price at the time of ordering.

## Relationships

- A CUSTOMER places zero or more ORDERs; an ORDER belongs to exactly one CUSTOMER.
- An ORDER contains one or more ORDER_LINEs.
- A PRODUCT is ordered as zero or more ORDER_LINEs.

## Diagram

```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ ORDER_LINE : contains
  PRODUCT ||--o{ ORDER_LINE : "is ordered as"
  CUSTOMER {
    key id PK
    text email
    text name
  }
  PRODUCT {
    key id PK
    text sku
    money price
  }
  ORDER { %% planned
    key id PK
    key customer_id FK
    text status
    money total
    instant placed_at
  }
  ORDER_LINE { %% planned
    key id PK
    key order_id FK
    key product_id FK
    count quantity
    money unit_price
  }
```
"""

PHYSICAL = """# Physical schema -- orders

## Scope

PostgreSQL 15 tables for the logical ERD of EVAL-1, following
hld/cross-cutting.md: snake_case plurals, BIGINT identity `id`, `<entity>_id`
foreign keys, `created_at`/`updated_at`, money in `_cents`.

## Tables

| Table | Column | Type | Notes |
|---|---|---|---|
| orders (planned) | id | BIGINT identity | PK |
| | customer_id | BIGINT | FK customers.id, not null |
| | status | TEXT | not null, one of placed, paid, shipped, delivered |
| | total_cents | INTEGER | not null, >= 0 |
| | created_at, updated_at | TIMESTAMPTZ | not null |
| order_lines (planned) | id | BIGINT identity | PK |
| | order_id | BIGINT | FK orders.id, not null |
| | product_id | BIGINT | FK products.id, not null |
| | quantity | INTEGER | not null, > 0 |
| | unit_price_cents | INTEGER | not null, >= 0: the price when ordered |
| | created_at, updated_at | TIMESTAMPTZ | not null |

## Indexes and constraints

- `orders (customer_id, created_at DESC)` -- a shopper's orders newest first, 20
  per page.
- `order_lines (order_id)`; `order_lines (product_id)`.
- Check constraints on `orders.status`, `orders.total_cents`,
  `order_lines.quantity` and `order_lines.unit_price_cents`.

## Diagram

```mermaid
erDiagram
  customers ||--o{ orders : "customer_id"
  orders ||--|{ order_lines : "order_id"
  products ||--o{ order_lines : "product_id"
  orders { %% planned
    bigint id PK
    bigint customer_id FK
    text status
    integer total_cents
    timestamptz created_at
    timestamptz updated_at
  }
  order_lines { %% planned
    bigint id PK
    bigint order_id FK
    bigint product_id FK
    integer quantity
    integer unit_price_cents
    timestamptz created_at
    timestamptz updated_at
  }
```

## Migration outline

1. Expand: add migration 0002, which creates `orders` and then `order_lines`
   with their keys, checks and indexes. Nothing existing changes, so no
   backfill is needed.
2. Ship the code that writes and reads orders.
3. Roll back by dropping `order_lines`, then `orders`; customers and products
   are untouched.
"""

README = """# orders

PRD feature F4 (Orders). HLD containers: shop.

| Ticket | Change |
|---|---|
| EVAL-1 | logical ERD and physical schema |
"""

ANSWERS = [
    ("Key strategy for orders and order_lines?", "BIGINT identity id, per hld/cross-cutting.md"),
    ("Where does the price an order was placed at live?", "Copied onto each order line as unit_price_cents"),
    ("How is the order status stored?", "A TEXT column with a CHECK constraint"),
]

DEFAULT_FILES = [L + "/README.md", FEATURE_README, ERD, SCHEMA]


def _start(ws):
    ws.skill("create-data-design")
    started = ws.acs("step", "start", "--step", "create-data-design", "--ticket", "EVAL-1")
    assert started.returncode == 0, started.stderr
    ws.sh("git status --porcelain > %s/baseline-status.txt" % STEP)
    for question, answer in ANSWERS:
        ws.sh('python3 "%s/clarify.py" add --skill create-data-design --ticket EVAL-1 '
              '--question "%s" --answer "%s"' % (SCRIPTS, question, answer))
    ws.write(STEP + "/iter-1/authoring.md",
             "## Entity inventory\n\nORDER, ORDER_LINE planned (hld/data-model.md); CUSTOMER, "
             "PRODUCT built (migrations/0001_customers_products.sql:2, :10).\n\n"
             "## Schema inventory\n\ncustomers, products (migrations/0001_customers_products.sql)."
             "\n\n## Conventions\n\nhld/cross-cutting.md ## Data conventions.\n\n"
             "## Reviewer checklist\n\n- both documents agree attribute by attribute\n")


def _write_docs(ws, logical=LOGICAL, physical=PHYSICAL, status="proposed", version=True):
    ws.write(ERD, logical)
    if physical is not None:
        ws.write(SCHEMA, physical)
    ws.write(FEATURE_README, README)
    ws.write(L + "/README.md", "| orders | F4 Orders | [orders/](orders/) |\n", append=True)
    if version:
        docs = [ERD] + ([SCHEMA] if physical is not None else [])
        init = ws.acs("design", "init", "--status", status, "--ticket", "EVAL-1",
                      "--feature", "orders", *docs)
        assert init.returncode == 0, init.stderr


def _review(ws):
    for slice_id in ("model", "conventions", "form"):
        ws.write("%s/iter-1/reviewer-%s.md" % (STEP, slice_id),
                 "## Findings\n\nnone (slice %s)\n" % slice_id)
    merged = ws.acs("notes", "merge", "--out", STEP + "/iter-1/reviewer.md",
                    *["%s/iter-1/reviewer-%s.md" % (STEP, s) for s in ("model", "conventions", "form")])
    assert merged.returncode == 0, merged.stderr


def _finish(ws, files=None, types=("logical-erd", "physical-schema")):
    result = {"status": "completed",
              "summary": "logical ERD and physical schema for orders; review passed on iteration 1",
              "states": {"feature": ["orders"],
                         "files": DEFAULT_FILES if files is None else files,
                         "types": list(types),
                         "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0},
                         "entities": 4},
              "findings": [], "errors": []}
    ws.write(STEP + "/result.json", json.dumps(result, indent=2))
    done = subprocess.run([sys.executable, os.path.join(SCRIPTS, "post-create-data-design.py"),
                           "--result-file", STEP + "/result.json"],
                          cwd=ws.path, env=ws.env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


REPLY = ("## /acs:create-data-design · EVAL-1 · completed\n\n- **Results**: logical ERD (CUSTOMER, "
         "PRODUCT, ORDER, ORDER_LINE) and physical schema (orders, order_lines, an index on "
         "customer_id, created_at for newest-first paging, a three-step migration outline in "
         "prose) under docs/architecture/lld/orders/data/, both proposed v1; no migration code "
         "written; left uncommitted for /acs:analyze-requirements' publish.\n"
         "- **Next**: /acs:create-flows EVAL-1")


def IDEAL(ws):
    _start(ws)
    _write_docs(ws)
    ws.sh('python3 "%s/acs.py" design check %s %s' % (SCRIPTS, ERD, SCHEMA))
    ws.sh('python3 "%s/mermaid_lint.py" %s %s' % (SCRIPTS, ERD, SCHEMA))
    ws.sh('python3 "%s/structure_lint.py" --sections "Scope; Entities; Relationships; Diagram" '
          '--ordered %s' % (SCRIPTS, ERD))
    ws.sh('python3 "%s/structure_lint.py" --sections "Scope; Tables; Indexes and constraints; '
          'Diagram; Migration outline" --ordered %s' % (SCRIPTS, SCHEMA))
    _review(ws)
    _finish(ws)
    ws.reply = REPLY


def _wrote_a_migration(ws):
    """Designed it, then 'helped' by writing the migration it outlined."""
    IDEAL(ws)
    ws.write("migrations/0002_orders.sql",
             "CREATE TABLE orders (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY);\n")


def _also_drew_a_flow(ws):
    """Wrote outside its own folder: a flow belongs to /acs:create-flows."""
    IDEAL(ws)
    ws.write(L + "/orders/flows/place-order.md", "# Place order\n")


def _wrote_into_the_hld(ws):
    """Put the design beside the HLD instead of in the feature's data/ folder."""
    _start(ws)
    ws.write("docs/architecture/hld/orders-logical-erd.md", LOGICAL)
    ws.write("docs/architecture/hld/orders-physical-schema.md", PHYSICAL)
    _review(ws)
    _finish(ws, files=["docs/architecture/hld/orders-logical-erd.md",
                       "docs/architecture/hld/orders-physical-schema.md"])


def _detailed_the_hld_in_place(ws):
    """Wrote the feature documents, then added attributes to the HLD's
    conceptual model as well -- never hld/."""
    IDEAL(ws)
    ws.write("docs/architecture/hld/data-model.md",
             "\n  ORDER {\n    bigint id PK\n  }\n", append=True)


def _no_front_matter(ws):
    _start(ws)
    _write_docs(ws, version=False)
    _review(ws)
    _finish(ws)


def _marked_implemented(ws):
    """Stamped a design of tables nobody has built as `implemented`."""
    _start(ws)
    _write_docs(ws, status="implemented")
    _review(ws)
    _finish(ws)


def _skipped_the_physical_schema(ws):
    """physical-schema is enabled (the default) -- and was not written."""
    _start(ws)
    _write_docs(ws, physical=None)
    _review(ws)
    _finish(ws, files=[L + "/README.md", FEATURE_README, ERD], types=("logical-erd",))


def _ddl_in_the_outline(ws):
    """The migration outline as a DDL script: migration code by another name."""
    _start(ws)
    _write_docs(ws, physical=PHYSICAL.split("## Migration outline")[0]
                + "## Migration outline\n\n```sql\nCREATE TABLE orders (\n  id BIGINT "
                "GENERATED ALWAYS AS IDENTITY PRIMARY KEY\n);\n```\n")
    _review(ws)
    _finish(ws)


def _recorded_no_files(ws):
    """Wrote both documents but left states.files empty, so the publish that
    commits them later has nothing to commit."""
    _start(ws)
    _write_docs(ws)
    _review(ws)
    _finish(ws, files=[])


def _never_finished(ws):
    _start(ws)
    _write_docs(ws)


BAD = {
    "fired the skill and did nothing": lambda ws: ws.skill("create-data-design"),
    "wrote a migration file": _wrote_a_migration,
    "also wrote a flow outside the data folder": _also_drew_a_flow,
    "wrote the documents outside the feature folder": _wrote_into_the_hld,
    "edited the HLD conceptual model": _detailed_the_hld_in_place,
    "no version front matter": _no_front_matter,
    "status implemented for a design nothing implements": _marked_implemented,
    "skipped the physical schema although enabled": _skipped_the_physical_schema,
    "migration outline written as DDL": _ddl_in_the_outline,
    "states.files left empty": _recorded_no_files,
    "never ran the post-hook": _never_finished,
}
