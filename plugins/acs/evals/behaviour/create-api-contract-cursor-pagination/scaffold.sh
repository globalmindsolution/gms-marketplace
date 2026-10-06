#!/usr/bin/env bash
# /acs:create-api-contract as a Design skill (ADR-0134): no plan, a feature
# whose interface is already documented. The shop repo with its PRD, an
# architecture set whose HLD carries the API landscape (integration-map.md)
# and the API conventions (cross-cutting.md), and the feature's LLD: the
# customer-listing README and its one interface document,
# lld/customer-listing/api/customers.md -- GET /customers with offset paging,
# exactly as src/shop/__init__.py builds it, versioned `implemented` v1
# through the plugin's own `acs.py design init`.
#
# EVAL-1 is the cursor-pagination story, minted with `--features
# customer-listing` and given its acceptance criteria through `acs.py ticket
# save`. Its approved analysis is in the working tree (main, uncommitted --
# ADR-0127), a folder (ADR-0133) with no `api_surface` key: nothing decides
# whether this skill runs but the user. There is NO plan -- the API is
# designed before one. The repo keeps no machine-readable contract (no
# OpenAPI, no docs/api/), and none is owed: the skill writes documents only.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd

A=docs/architecture
mkdir -p $A/hld $A/lld/customer-listing/api
cat > $A/hld/tech-stack.md <<'MD'
# Tech stack

Python 3; a JSON-over-HTTP service, `shop`.
MD
cat > $A/hld/integration-map.md <<'MD'
# Integration map

| API | Exposed by | Consumed by | Style |
|---|---|---|---|
| Customers REST (`/customers`) | shop | admin UI, partner clients | sync, JSON over HTTP |
MD
cat > $A/hld/cross-cutting.md <<'MD'
# Cross-cutting concerns

## API conventions

- Errors are `{"error": "<code>"}` with a snake_case code and an HTTP status.
- List endpoints return `{"items": [...]}` plus their paging fields; `limit`
  defaults to 20 and is capped at 100.
- Additive changes ship in place; a breaking change needs a new `/v2` path.
MD
cat > $A/lld/README.md <<'MD'
# Low-level design

| Feature | PRD feature | Folder |
|---|---|---|
| customer-listing | F1 Customer listing | [customer-listing/](customer-listing/) |
MD
cat > $A/lld/customer-listing/README.md <<'MD'
# customer-listing

PRD feature F1 (Customer listing). HLD containers: shop.

- [api/customers.md](api/customers.md) -- the Customers REST API.

| Ticket | Change |
|---|---|
MD
cat > $A/lld/customer-listing/api/customers.md <<'MD'
# Customers API -- REST

## Scope

The shop service's customer listing, consumed by the admin UI and partner
clients (hld/integration-map.md), following hld/cross-cutting.md's API
conventions. Implemented by `list_customers` in src/shop/__init__.py.

## Surface

### GET /customers

- **Kind and status**: endpoint, built.
- **Request**: `offset` (optional integer >= 0, default 0); `limit`
  (optional integer 1-100, default 20).
- **Response**: 200 `{"items": [...], "offset": 0, "limit": 20}`.
- **Errors**: none of its own.
- **Traces**: F1 Customer listing.

## Error model

_None of its own; the conventions' error envelope applies._

## Compatibility & versioning

v1, unversioned path; additive changes ship in place (hld/cross-cutting.md).

## Examples

`GET /customers?offset=20&limit=20` -> 200 `{"items": [...], "offset": 20, "limit": 20}`

## Traceability

| Item | Criterion |
|---|---|
| GET /customers | F1 Customer listing |
MD
python3 "$ACS_SCRIPTS/acs.py" design init --status implemented --feature customer-listing \
  $A/lld/customer-listing/api/customers.md > /dev/null
git add -A && git commit -qm "Architecture docs"

ACS_FEATURES=customer-listing
acs_ticket "Cursor pagination for GET /customers" story \
  "Offset paging skips or repeats customers when rows are inserted between page requests. Replace it with an opaque cursor so a client can walk every customer exactly once."
printf '%s' '{"acceptance_criteria": [
  "GET /customers accepts an optional cursor query parameter and returns the page of customers that follows it",
  "Every GET /customers response carries next_cursor, which is null on the last page",
  "A malformed cursor is rejected with HTTP 400 and error code invalid_cursor"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

D=docs/development/customer-listing/EVAL-1/analysis
mkdir -p $D
cat > $D/README.md <<'MD'
---
ticket: EVAL-1
ready_for_planning: true
---

# Analysis — EVAL-1: Cursor pagination for GET /customers

## Scope and summary

Offset paging on GET /customers skips or repeats customers when rows are
inserted between page requests. Clients need an opaque cursor that walks every
customer exactly once, while existing offset clients keep working.

## Contexts

| Context | File |
|---|---|
| Customer listing | [customer-listing.md](customer-listing.md) |

## Refined acceptance criteria

The three criteria are confirmed as written.

## Cross-cutting risks and decisions

The Customers REST API changes (GET /customers gains `cursor`, `next_cursor`
and `invalid_cursor`): an interface change, designed with
/acs:create-api-contract. Partner clients page with `offset` today.

## Questions and assumptions

- C-1 cursor encoding — answered: an opaque string.
- C-2 offset compatibility — answered: kept, deprecated; cursor wins.

## Verdict

Ready for planning.
MD
cat > $D/customer-listing.md <<'MD'
---
context: customer-listing
---

# Customer listing

## Impact map

| Path | Component | Change | Evidence |
|---|---|---|---|
| src/shop/__init__.py | shop | `list_customers` gains `cursor`, returns `next_cursor` | src/shop/__init__.py:8 |
| tests/test_customers.py | tests | new, cursor paging cases | tests/ holds only test_health.py |

## Rules and edge cases

`limit` stays 1-100, default 20 (hld/cross-cutting.md).

## Risks

Partner clients page with `offset`; it must keep working.

## Open questions

_None._

## API notes

GET /customers: new `cursor` parameter, `next_cursor` field, `invalid_cursor` error.
MD
