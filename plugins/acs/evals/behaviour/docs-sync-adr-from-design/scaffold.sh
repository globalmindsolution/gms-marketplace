#!/usr/bin/env bash
# /acs:docs-sync on an ADR-worthy change: EVAL-1 (needs_design true) moves the
# customer listing from a hard-coded empty list onto a SQLite store through
# the stdlib sqlite3 module. Its approved design (docs/tickets/EVAL-1/design.md,
# committed on the ticket branch the way the Build phase carries it) records
# one accepted decision under `### Decision records`, and the repo keeps ADRs
# in docs/adr/ (0001, 0002, NNNN-slug.md). /acs:code's step is recorded
# completed through the plugin's own writers (`acs.py step start`, then
# `post-code.py`), with no doc updated. The doc-updater charter: "when the
# ticket has a binding design carrying accepted decision records, commit those
# records as ADRs under <adr_dir>". What the run must produce: a NEW ADR,
# docs/adr/0003-*.md, committed on the SAME ticket branch, the existing ADRs
# untouched.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

mkdir -p docs/adr
cat > docs/adr/0001-record-architecture-decisions.md <<'MD'
# 1. Record architecture decisions

Date: 2026-06-02

## Status

Accepted

## Context

We need to record the architectural decisions made on this project.

## Decision

We will use Architecture Decision Records, one file per decision in
docs/adr/, numbered NNNN-title.md. An accepted ADR is never edited; a later
ADR supersedes it.

## Consequences

Every significant decision has a durable, reviewable record.
MD
cat > docs/adr/0002-serve-http-with-stdlib-wsgi.md <<'MD'
# 2. Serve HTTP with the stdlib WSGI interface

Date: 2026-07-14

## Status

Accepted

## Context

shop is a small service and should run anywhere Python runs.

## Decision

The HTTP front is a plain WSGI app built on the standard library only.

## Consequences

No web framework dependency; routing is hand-written in src/shop/web.py.
MD
git add -A
git commit -qm "ADRs 0001 and 0002"

acs_ticket "Store customers in SQLite" task true \
  "Back list_customers with a SQLite store instead of a hard-coded empty list."
acs_branch task/EVAL-1-store-customers-in-sqlite

# The Build phase carries the approved design onto the ticket branch.
mkdir -p docs/tickets/EVAL-1
cat > docs/tickets/EVAL-1/design.md <<'MD'
# Design — EVAL-1: Store customers in SQLite

Status: approved

## Context & constraints

`list_customers()` returns a hard-coded empty list. Customers must persist
across restarts. Constraint: no new third-party dependency (ADR 0002's
stdlib-only stance).

## Options considered

1. **SQLite through the stdlib `sqlite3` module** — zero dependencies, a
   single file, transactional.
2. **A JSON file rewritten on every change** — trivial, but no concurrent
   writers and no partial reads.
3. **PostgreSQL** — the scalable choice, but a server to run and a driver
   dependency.

## Decision & rationale

Option 1. It persists customers with no new dependency, and paging maps
directly onto `LIMIT`/`OFFSET`.

### Decision records

- **Store customers in SQLite through the stdlib sqlite3 module** — accepted.
  Commit as an ADR under docs/adr/ with the documentation updates.

## Architecture

`src/shop/store.py` owns the connection and the `customers` table;
`list_customers()` reads a page from it.

## Impact & risks

A single-writer database: fine for one process, revisit before running
several.

## Rollout/migration

The table is created on first connect; there is no existing data to migrate.
MD
git add -A
git commit -qm "EVAL-1 design"

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
git add -A
git commit -qm "EVAL-1 store customers in SQLite"
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "customers are stored in SQLite (src/shop/store.py); list_customers pages the store",
 "states": {"branch": "task/EVAL-1-store-customers-in-sqlite", "docs_updated": []},
 "findings": [], "errors": []}
JSON
