#!/usr/bin/env bash
# Re-run after a major architectural shift. The repo carries an architecture
# doc set (hld/tech-stack.md marks it) written when the product had a second
# container -- an `export-worker` pushing a nightly CSV export through a Redis
# queue. Its hld/ predates hld/cross-cutting.md and hld/integration-map.md,
# and beside it sits low-level design the skill does not own (ADR-0118):
# lld/contracts.md and two flows, list-customers and nightly-export. The
# latest commit removed the worker and Redis and added an orders API
# (GET /orders?customer_id=), so the HLD now describes a container that no
# longer exists and misses an interface that does. A local bare repository
# stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_prd
mkdir -p src/export_worker
cat > src/export_worker/__init__.py <<'PY'
"""Nightly export: push every customer as CSV onto the Redis `exports` queue."""
QUEUE = "exports"


def run(redis, customers):
    for row in customers:
        redis.rpush(QUEUE, ",".join(str(v) for v in row))
PY
git add -A && git commit -qm "Nightly export worker"

A=docs/architecture
mkdir -p $A/hld $A/lld/flows
cat > $A/hld/overview.md <<'MD'
# Overview

## System context

The `shop` API serves shoppers; the `export-worker` pushes a nightly customer
export through Redis.

## Goals

G1 checkout that converts; G2 reliable service.

## Quality attributes

p95 API latency under 300 ms; 99.9% availability.

## Constraints

Python 3; one repository.

Flows: [list-customers](../lld/flows/list-customers.md),
[nightly-export](../lld/flows/nightly-export.md)
MD
cat > $A/hld/c4-context.md <<'MD'
# C4 context

```mermaid
C4Context
  Person(shopper, "Shopper")
  System(shop, "shop", "storefront API and export worker")
  Rel(shopper, shop, "browses")
```
MD
cat > $A/hld/c4-container.md <<'MD'
# C4 container

```mermaid
C4Container
  Container(api, "shop", "Python 3", "storefront API")
  Container(worker, "export-worker", "Python 3", "nightly customer export")
  ContainerQueue(redis, "Redis", "queue", "exports")
  Rel(worker, redis, "RPUSH exports")
```
MD
cat > $A/hld/c4-component.md <<'MD'
# C4 component

```mermaid
C4Component
  Component(listing, "list_customers", "shop")
  Component(exporter, "export_worker.run", "export-worker")
```
MD
cat > $A/hld/data-model.md <<'MD'
# Data model

```mermaid
erDiagram
  CUSTOMER {
    string id
  }
```
MD
cat > $A/hld/deployment.md <<'MD'
# Deployment

```mermaid
flowchart LR
  lb[load balancer] --> shop
  cron[nightly cron] --> worker[export-worker]
  worker --> redis[(Redis)]
```
MD
cat > $A/hld/tech-stack.md <<'MD'
# Tech stack

## Languages

Python 3.

## Frameworks

pytest; redis-py for the export queue.

## Conventions

src layout.
MD
cat > $A/hld/project-structure.md <<'MD'
# Project structure

## Directory layout

```mermaid
flowchart TD
  root --> src/shop
  root --> src/export_worker
  root --> tests
```
MD
cat > $A/lld/contracts.md <<'MD'
# Contracts

## Contracts

- `GET /health` returns `ok`.
- `GET /customers?offset=&limit=` returns `{items, offset, limit}`; limit
  defaults to 20.
- `exports` Redis queue: one CSV line per customer, pushed nightly by
  export-worker (see nightly-export).
MD
cat > $A/lld/flows/list-customers.md <<'MD'
# list-customers

```mermaid
sequenceDiagram
  participant Shopper
  participant shop
  Shopper->>shop: GET /customers?offset=0&limit=20
  shop-->>Shopper: page of customers
```
MD
cat > $A/lld/flows/nightly-export.md <<'MD'
# nightly-export

```mermaid
sequenceDiagram
  participant cron
  participant export-worker
  participant Redis
  cron->>export-worker: run
  export-worker->>Redis: RPUSH exports
```
MD
git add -A && git commit -qm "Architecture doc set"

git rm -rq src/export_worker
cat > src/shop/orders.py <<'PY'
from shop import PAGE_SIZE


def list_orders(customer_id, offset=0, limit=PAGE_SIZE):
    """GET /orders?customer_id=&offset=&limit= -- one customer's orders."""
    return {"customer_id": customer_id, "items": [], "offset": offset, "limit": limit}
PY
cat >> README.md <<'MD'
- `GET /orders?customer_id=&offset=&limit=` lists one customer's orders.
MD
git add -A && git commit -qm "Drop the export worker and Redis; add the orders API"
acs_local_origin
