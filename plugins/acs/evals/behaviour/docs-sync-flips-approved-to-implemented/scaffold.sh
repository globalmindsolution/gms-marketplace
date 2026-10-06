#!/usr/bin/env bash
# /acs:docs-sync moving an approved LLD document to `implemented` (ADR-0137).
# EVAL-1 (feature customer-listing) stores customers in a SQLite `customers`
# table. Its data design was settled first: the feature's living physical
# schema, docs/architecture/lld/customer-listing/data/physical-schema.md,
# versioned `approved` (v1) through the plugin's own `acs.py design init` and
# committed. /acs:code then built exactly that table -- one column for one
# column, nothing more -- and is recorded completed through `acs.py step start`
# and `post-code.py`, its change left UNCOMMITTED on main (ADR-0127).
#
# What the run must do: the customer-listing gap analyst finds every element
# matching (implemented-candidate), nothing in the document needs an edit, the
# drift review passes, and Finish moves the document approved -> implemented
# with `acs.py design status --set implemented --by acs --reason "<run-id>: the
# code matches"` -- status_by/at/reason recorded, version unchanged -- and
# lists it in states.implemented. Nothing is committed.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

ACS_FEATURES=customer-listing
acs_ticket "Store customers in SQLite" task false \
  "Back list_customers with a SQLite customers table (id, name) instead of a hard-coded empty list."

d=docs/architecture/lld/customer-listing/data
mkdir -p "$d"
cat > "$d/physical-schema.md" <<'MD'
# Customer listing -- physical schema

SQLite, through the standard library's `sqlite3` module.

```mermaid
erDiagram
  customers {
    INTEGER id PK
    TEXT name "NOT NULL"
  }
```

## Tables

### customers

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | INTEGER | no | rowid | primary key |
| name | TEXT | no | -- | the customer's display name |

## Indexes and constraints

- Primary key on `id`. No secondary index: a page is read in `id` order.

## Migration outline

1. Create `customers` on first connect (`CREATE TABLE IF NOT EXISTS`); there is
   no existing data to migrate.
MD
python3 "$ACS_SCRIPTS/acs.py" design init --status approved --ticket EVAL-1 \
  --feature customer-listing "$d/physical-schema.md" > /dev/null
git add -A
git commit -qm "Customer listing physical schema (approved)"

python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
cat > src/shop/store.py <<'PY'
"""The customer store: SQLite through the stdlib sqlite3 module."""
import sqlite3


def connect(path=":memory:"):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    return db


def page(db, offset, limit):
    rows = db.execute("SELECT id, name FROM customers ORDER BY id LIMIT ? OFFSET ?",
                      (limit, offset)).fetchall()
    return [{"id": row[0], "name": row[1]} for row in rows]
PY
python3 - <<'PY'
path = "src/shop/__init__.py"
src = open(path).read()
src = src.replace(
    'def list_customers(offset=0, limit=PAGE_SIZE):\n'
    '    return {"items": [], "offset": offset, "limit": limit}\n',
    'def list_customers(offset=0, limit=PAGE_SIZE, db=None):\n'
    '    from shop import store\n'
    '    db = db or store.connect()\n'
    '    return {"items": store.page(db, offset, limit), "offset": offset, "limit": limit}\n')
open(path, "w").write(src)
PY
cat > tests/test_store.py <<'PY'
from shop import list_customers, store


def test_list_customers_pages_the_store():
    db = store.connect()
    db.executemany("INSERT INTO customers (name) VALUES (?)", [("ada",), ("bo",), ("cy",)])
    assert list_customers(1, 1, db=db)["items"] == [{"id": 2, "name": "bo"}]
PY
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "customers are stored in the SQLite customers table (src/shop/store.py); list_customers pages it",
 "states": {"docs_updated": [], "files": ["src/shop/store.py", "src/shop/__init__.py", "tests/test_store.py"]},
 "findings": [], "errors": []}
JSON
