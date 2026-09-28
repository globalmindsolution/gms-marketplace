#!/usr/bin/env bash
# /acs:create-e2e-tests with no e2e harness at all: EVAL-1 added GET /customers
# to the shop's WSGI front (done and committed on its branch), and its
# committed test-cases.md types two cases e2e -- but .acs/settings.json
# configures no suite (no `suites`, no `e2e`), and the repo has no e2e tests, no
# runner config and no declared layout. The skill's own check: "if it has none,
# finish needs_input with that question -- a harness is a repo-structure
# decision, not this skill's". What the run must produce: no suite, no runner,
# no settings change, no commit, and the step finished `interrupted` with
# stop_reason `needs_input` (the ledger's spelling of a needs_input finish).
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

cat > src/shop/web.py <<'PY'
"""The shop's HTTP front: a WSGI app over the shop API."""
from shop import health


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path == "/health":
        return _send(start_response, "200 OK", "text/plain", health())
    return _send(start_response, "404 Not Found", "text/plain", "not found")


def _send(start_response, status, content_type, body):
    data = body.encode("utf-8")
    start_response(status, [("Content-Type", content_type),
                            ("Content-Length", str(len(data)))])
    return [data]
PY
printf '__pycache__/\n' >> .gitignore
git add -A
git commit -qm "HTTP front with /health"

acs_ticket "Serve the customer listing over HTTP" task false \
  "Expose list_customers as GET /customers on the WSGI front, honouring offset and limit."
acs_branch task/EVAL-1-serve-the-customer-listing-over-http

python3 - <<'PY'
path = "src/shop/web.py"
src = open(path).read()
src = src.replace('"""The shop\'s HTTP front: a WSGI app over the shop API."""\n',
                  '"""The shop\'s HTTP front: a WSGI app over the shop API."""\n'
                  'import json\nfrom urllib.parse import parse_qs\n\n')
src = src.replace("from shop import health", "from shop import PAGE_SIZE, health, list_customers")
src = src.replace(
    '    return _send(start_response, "404 Not Found"',
    '    if path == "/customers":\n'
    '        query = parse_qs(environ.get("QUERY_STRING", ""))\n'
    '        offset = int(query.get("offset", ["0"])[0])\n'
    '        limit = int(query.get("limit", [str(PAGE_SIZE)])[0])\n'
    '        return _send(start_response, "200 OK", "application/json",\n'
    '                     json.dumps(list_customers(offset, limit)))\n'
    '    return _send(start_response, "404 Not Found"', 1)
open(path, "w").write(src)
PY
git commit -qam "EVAL-1 serve the customer listing over HTTP"

mkdir -p docs/tickets/EVAL-1
cat > docs/tickets/EVAL-1/test-cases.md <<'MD'
---
ticket: EVAL-1
cases: 2
e2e_cases: 2
---

# Test cases — EVAL-1: Serve the customer listing over HTTP

## Scope

`GET /customers` on the WSGI front (`src/shop/web.py`).

## Cases

| ID | AC | Type | Preconditions | Steps | Expected | Suite |
| --- | --- | --- | --- | --- | --- | --- |
| TC-1 | AC-1 | e2e | none | `GET /customers` | status 200, `Content-Type: application/json`, body `{"items": [], "offset": 0, "limit": 20}` | e2e |
| TC-2 | AC-2 | e2e | none | `GET /customers?offset=40&limit=10` | status 200, body has `offset` 40 and `limit` 10 | e2e |

## Traceability

| AC | Cases |
| --- | --- |
| AC-1 GET /customers lists customers, 20 per page by default | TC-1 |
| AC-2 offset and limit are honoured | TC-2 |
MD
git add -A
git commit -qm "EVAL-1 test cases"
