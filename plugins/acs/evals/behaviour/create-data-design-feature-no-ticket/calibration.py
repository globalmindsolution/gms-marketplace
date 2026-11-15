"""Calibration plays for create-data-design-feature-no-ticket (see
tests/evals/check_grader_calibration.py).

IDEAL does what /acs:create-data-design's coordinator does on a run with NO
ticket (ADR-0128), through the plugin's own writers: `acs step start --args`
over the invocation (the `orders` slug and the prompt -- the run's
requirements), the feature taken from the argument, the relayed answers in the
run's own ledger (`clarify.py add`, no `--ticket`), ONE write designer writing
both documents and the feature README, version front matter through `acs.py
design init --status proposed --feature orders` with no `--ticket`, the three
reviewer slices joined with `acs.py notes merge`, then result.json with every
written path in states.files and the real post-hook. Nothing is committed.
"""

import json
import os
import subprocess
import sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
L = "docs/architecture/lld"
DATA = L + "/orders/data"
ERD = DATA + "/logical-erd.md"
SCHEMA = DATA + "/physical-schema.md"
FEATURE_README = L + "/orders/README.md"
ARGS = ('orders "Shoppers order one or more products in a single order: each order line '
        'records the product, the quantity and the unit price at the time of ordering; an '
        'order belongs to exactly one customer and records its status (placed, paid, shipped '
        'or delivered) and its total in cents; a shopper lists their own orders newest first, '
        '20 per page."')

LOGICAL = """# Logical ERD -- orders

## Scope

The entities PRD feature F4 (Orders) persists: an order a customer
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

PostgreSQL 15 tables for the logical ERD of feature orders, following
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
| %s | logical ERD and physical schema |
"""

ANSWERS = [
    ("Key strategy for orders and order_lines?", "BIGINT identity id, per hld/cross-cutting.md"),
    ("Where does the price an order was placed at live?", "Copied onto each order line as unit_price_cents"),
    ("How is the order status stored?", "A TEXT column with a CHECK constraint"),
]

DEFAULT_FILES = [L + "/README.md", FEATURE_README, ERD, SCHEMA]


class _Run(object):
    """The ticketless run `step start --args` opens over the invocation."""

    def __init__(self, ws):
        ws.skill("create-data-design")
        started = ws.acs("step", "start", "--step", "create-data-design", "--args", ARGS)
        assert started.returncode == 0, started.stderr
        context = json.loads(started.stdout)
        assert context.get("ticket_id") is None, context.get("ticket_id")
        self.ws = ws
        self.run_id = context["run_id"]
        self.step = os.path.relpath(
            os.path.join(context["partition"], "steps", "create-data-design"), ws.path)
        ws.sh("git status --porcelain > %s/baseline-status.txt" % self.step)

    def answers(self):
        for question, answer in ANSWERS:
            self.ws.sh('python3 "%s/clarify.py" add --skill create-data-design '
                       '--question "%s" --answer "%s" > /dev/null' % (SCRIPTS, question, answer))

    def write_docs(self, status="proposed", ticket=None, physical=PHYSICAL):
        ws = self.ws
        ws.write(ERD, LOGICAL)
        if physical is not None:
            ws.write(SCHEMA, physical)
        ws.write(FEATURE_README, README % self.run_id)
        ws.write(L + "/README.md", "| orders | F4 Orders | [orders/](orders/) |\n", append=True)
        docs = [ERD] + ([SCHEMA] if physical is not None else [])
        flags = ["--ticket", ticket] if ticket else []
        init = ws.acs("design", "init", "--status", status, *flags, "--feature", "orders", *docs)
        assert init.returncode == 0, init.stderr

    def review(self):
        slices = ("model", "conventions", "form")
        for slice_id in slices:
            self.ws.write("%s/iter-1/reviewer-%s.md" % (self.step, slice_id),
                          "## Findings\n\nnone (slice %s)\n" % slice_id)
        merged = self.ws.acs("notes", "merge", "--out", self.step + "/iter-1/reviewer.md",
                             *["%s/iter-1/reviewer-%s.md" % (self.step, s) for s in slices])
        assert merged.returncode == 0, merged.stderr

    def finish(self, files=None):
        ws = self.ws
        result = {"status": "completed",
                  "summary": "logical ERD and physical schema for orders; review passed on iteration 1",
                  "states": {"feature": ["orders"],
                             "files": DEFAULT_FILES if files is None else files,
                             "types": ["logical-erd", "physical-schema"],
                             "gaps": {"undocumented": 0, "unimplemented": 0, "drifted": 0},
                             "entities": 4},
                  "findings": [], "errors": []}
        ws.write(self.step + "/result.json", json.dumps(result, indent=2))
        done = subprocess.run([sys.executable, os.path.join(SCRIPTS, "post-create-data-design.py"),
                               "--result-file", self.step + "/result.json"],
                              cwd=ws.path, env=ws.env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr


REPLY = ("## /acs:create-data-design · orders · completed\n\n- **Results**: no ticket -- the "
         "orders feature's logical ERD (CUSTOMER, PRODUCT, ORDER, ORDER_LINE) and physical "
         "schema (orders, order_lines, an index on customer_id, created_at for newest-first "
         "paging, a three-step migration outline in prose) under "
         "docs/architecture/lld/orders/data/, both proposed v1; no migration code written; left "
         "as local uncommitted changes for you to review.\n"
         "- **Next**: /acs:create-flows orders, or /acs:create-ticket to cut the implementation ticket")


def IDEAL(ws):
    run = _Run(ws)
    run.answers()
    run.write_docs()
    ws.sh('python3 "%s/acs.py" design check %s %s' % (SCRIPTS, ERD, SCHEMA))
    run.review()
    run.finish()
    ws.reply = REPLY


def _asked_for_a_ticket(ws):
    """The pre-ADR-0128 refusal: no ticket id -> ask for one and stop."""
    ws.skill("create-data-design")
    ws.reply = "I need a ticket id to run /acs:create-data-design -- run /acs:create-ticket first."


def _minted_a_ticket(ws):
    """Detoured through a ticket to have somewhere to record the feature."""
    ws.sh('python3 "%s/new-ticket.py" --title "Orders" --type story --features orders '
          '> /dev/null' % SCRIPTS)
    run = _Run(ws)
    run.answers()
    run.write_docs(ticket="EVAL-1")
    run.review()
    run.finish()
    ws.reply = REPLY


def _invented_a_ticket_in_the_front_matter(ws):
    """No ticket minted, but the version front matter names one anyway."""
    run = _Run(ws)
    run.answers()
    run.write_docs(ticket="EVAL-1")
    run.review()
    run.finish()
    ws.reply = REPLY


def _slug_only(ws):
    """Took the feature from the slug but ignored the prompt's requirements:
    nothing serves the newest-first per-customer listing."""
    run = _Run(ws)
    run.answers()
    run.write_docs(physical=PHYSICAL.replace("customer_id, created_at DESC", "created_at DESC"))
    run.review()
    run.finish()
    ws.reply = REPLY


def _wrote_a_migration(ws):
    IDEAL(ws)
    ws.write("migrations/0002_orders.sql",
             "CREATE TABLE orders (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY);\n")


def _committed(ws):
    IDEAL(ws)
    ws.sh("git add docs && git commit -qm 'orders data design'")


def _never_finished(ws):
    run = _Run(ws)
    run.answers()
    run.write_docs()


BAD = {
    "asked for a ticket and stopped": _asked_for_a_ticket,
    "minted a ticket to have one": _minted_a_ticket,
    "invented a ticket in the front matter": _invented_a_ticket_in_the_front_matter,
    "ignored the prompt's requirements": _slug_only,
    "wrote a migration file": _wrote_a_migration,
    "committed the documents": _committed,
    "never ran the post-hook": _never_finished,
}
