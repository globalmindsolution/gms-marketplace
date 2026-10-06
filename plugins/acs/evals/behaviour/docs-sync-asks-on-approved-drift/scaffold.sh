#!/usr/bin/env bash
# /acs:docs-sync meeting code that differs from an APPROVED LLD document
# (ADR-0137). The customer-listing feature's living interface document,
# docs/architecture/lld/customer-listing/api/customers.md, describes
# GET /customers as it is built today -- `offset` and `limit` in, `items`,
# `offset` and `limit` out -- versioned `approved` (v1) through the plugin's
# own `acs.py design init` and committed. EVAL-1's /acs:code run then added a
# `total` field to the response, a field the approved document lacks; it is
# recorded completed through `acs.py step start` and `post-code.py`, its
# change left UNCOMMITTED on main (ADR-0127).
#
# What the run must do: the gap analyst classifies `total` as undocumented on
# an approved document, so the `lld` doc-updater may not rewrite it -- it is a
# question for the grouped ask: (a) update the document to match the code
# (bumped, back to proposed for re-approval) or (b) keep it (the code is
# wrong, a blocking finding for /acs:code). The user is unreachable, so the
# question is never auto-answered: it is recorded open, the document is left
# exactly as approved, and the step finishes interrupted with stop_reason
# needs_input. Nothing is committed.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

ACS_FEATURES=customer-listing
acs_ticket "Report the customer total" task false \
  "GET /customers also returns the total number of customers, so the admin UI can show page counts."

a=docs/architecture/lld/customer-listing/api
mkdir -p "$a"
cat > "$a/customers.md" <<'MD'
# Customers API -- REST

## Scope

GET /customers, consumed by the admin UI and partner clients.

## Surface

### GET /customers

- **Kind and status**: endpoint, EXISTING.
- **Request**: `offset` (optional integer, default 0); `limit` (optional
  integer, default 20).
- **Response**: 200 `{"items": [...], "offset": 0, "limit": 20}`.
- **Errors**: none.

## Compatibility & versioning

Unversioned; additive changes only.

## Examples

`GET /customers?offset=20&limit=20` -> 200 with the second page.
MD
python3 "$ACS_SCRIPTS/acs.py" design init --status approved --ticket EVAL-1 \
  --feature customer-listing "$a/customers.md" > /dev/null
git add -A
git commit -qm "Customers API document (approved)"

python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
python3 - <<'PY'
path = "src/shop/__init__.py"
src = open(path).read()
src = src.replace(
    'def list_customers(offset=0, limit=PAGE_SIZE):\n'
    '    return {"items": [], "offset": offset, "limit": limit}\n',
    'CUSTOMERS = []\n\n\n'
    'def list_customers(offset=0, limit=PAGE_SIZE):\n'
    '    items = CUSTOMERS[offset:offset + limit]\n'
    '    return {"items": items, "offset": offset, "limit": limit, "total": len(CUSTOMERS)}\n')
open(path, "w").write(src)
PY
cat > tests/test_customers_total.py <<'PY'
import shop


def test_list_customers_reports_the_total():
    shop.CUSTOMERS[:] = [{"id": 1}, {"id": 2}, {"id": 3}]
    page = shop.list_customers(0, 2)
    assert page["total"] == 3 and len(page["items"]) == 2
PY
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "GET /customers returns total, the number of customers (src/shop/__init__.py)",
 "states": {"docs_updated": [], "files": ["src/shop/__init__.py", "tests/test_customers_total.py"]},
 "findings": [], "errors": []}
JSON
