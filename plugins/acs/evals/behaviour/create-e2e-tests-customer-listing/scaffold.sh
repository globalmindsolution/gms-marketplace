#!/usr/bin/env bash
# /acs:create-e2e-tests on a ticket whose code is done: the shop's WSGI front
# gained GET /customers -- uncommitted on main, as /acs:code leaves it
# (ADR-0127) -- and the ticket's test-cases.md types two of its three cases e2e. The repo already has an e2e
# harness (tests/e2e/, a stdlib unittest suite that drives the WSGI app in
# process -- no socket, no pytest, so the suite runs on any host) and settings
# configure it as the `e2e` suite. What the run must produce: a suite file
# under tests/e2e/ covering TC-2 and TC-3 (never TC-1, which is unit), left
# uncommitted (no branch, no commit), with no product code touched.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

# main: the WSGI front with /health only, and the e2e harness that drives it.
cat > src/shop/web.py <<'PY'
"""The shop's HTTP front: a WSGI app over the shop API."""
import json
from urllib.parse import parse_qs

from shop import health


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    if path == "/health":
        return _send(start_response, "200 OK", "text/plain", health())
    return _send(start_response, "404 Not Found", "text/plain", "not found")


def _query(environ):
    return parse_qs(environ.get("QUERY_STRING", ""))


def _send(start_response, status, content_type, body):
    data = body.encode("utf-8")
    start_response(status, [("Content-Type", content_type),
                            ("Content-Length", str(len(data)))])
    return [data]
PY
mkdir -p tests/e2e
cat > tests/e2e/harness.py <<'PY'
"""Drive the WSGI app end to end, in process: a real request environ in, a
real status line, headers and body out. Every e2e suite imports `get`."""
import io
from wsgiref.util import setup_testing_defaults

from shop.web import app


def get(path, query=""):
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "QUERY_STRING": query,
               "wsgi.input": io.BytesIO(b"")}
    setup_testing_defaults(environ)
    seen = {}

    def start_response(status, headers):
        seen["status"], seen["headers"] = status, dict(headers)

    body = b"".join(app(environ, start_response)).decode("utf-8")
    return int(seen["status"].split()[0]), seen["headers"], body
PY
cat > tests/e2e/test_health_e2e.py <<'PY'
import unittest

from harness import get


class HealthE2E(unittest.TestCase):
    def test_health_returns_ok(self):
        status, headers, body = get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/plain")
        self.assertEqual(body, "ok")
PY
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "tests": {
    "e2e": {
      "command": "PYTHONPATH=src python3 -m unittest discover -s tests/e2e -p 'test_*.py'"
    }
  }
}
JSON
# Running the suites leaves bytecode behind; a real repo ignores it, and the
# skill stops on any unexpected path `git status` shows.
printf '__pycache__/\n' >> .gitignore
git add -A
git commit -qm "HTTP front with /health and its e2e harness"

ACS_FEATURES=customer-listing
acs_ticket "Serve the customer listing over HTTP" task false \
  "Expose list_customers as GET /customers on the WSGI front, honouring offset and limit."
slug="$(python3 "$ACS_SCRIPTS/acs.py" slug --text "Serve the customer listing over HTTP" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["slug"])')"

# /acs:code's change (the route and its unit test), uncommitted ...
python3 - <<'PY'
import re
path = "src/shop/web.py"
src = open(path).read()
src = src.replace("from shop import health", "from shop import PAGE_SIZE, health, list_customers")
src = src.replace(
    '    return _send(start_response, "404 Not Found"',
    '    if path == "/customers":\n'
    '        query = _query(environ)\n'
    '        offset = int(query.get("offset", ["0"])[0])\n'
    '        limit = int(query.get("limit", [str(PAGE_SIZE)])[0])\n'
    '        return _send(start_response, "200 OK", "application/json",\n'
    '                     json.dumps(list_customers(offset, limit)))\n'
    '    return _send(start_response, "404 Not Found"', 1)
open(path, "w").write(src)
PY
mkdir -p tests/unit
cat > tests/unit/test_customers.py <<'PY'
import unittest

from shop import PAGE_SIZE, list_customers


class ListCustomers(unittest.TestCase):
    def test_default_page(self):
        """TC-1"""
        self.assertEqual(list_customers(), {"items": [], "offset": 0, "limit": PAGE_SIZE})
PY

# ... and the ticket's case document, where acs resolves it (the Development
# folder, docs/development/<feature>/<ID>/ — ADR-0128).
mkdir -p docs/development/customer-listing/EVAL-1
cat > docs/development/customer-listing/EVAL-1/test-cases.md <<'MD'
---
ticket: EVAL-1
cases: 3
e2e_cases: 2
---

# Test cases — EVAL-1: Serve the customer listing over HTTP

## Scope

`GET /customers` on the WSGI front (`src/shop/web.py`), backed by
`list_customers()`.

## Cases

| ID | AC | Type | Preconditions | Steps | Expected | Suite |
| --- | --- | --- | --- | --- | --- | --- |
| TC-1 | AC-1 | unit | none | call `list_customers()` with no arguments | returns offset 0 and limit `PAGE_SIZE` (20) | `tests/unit/test_customers.py` |
| TC-2 | AC-1 | e2e | none | `GET /customers` | status 200, `Content-Type: application/json`, body `{"items": [], "offset": 0, "limit": 20}` | e2e |
| TC-3 | AC-2 | e2e | none | `GET /customers?offset=40&limit=10` | status 200, body has `offset` 40 and `limit` 10 | e2e |

## Traceability

| AC | Cases |
| --- | --- |
| AC-1 GET /customers lists customers, 20 per page by default | TC-1, TC-2 |
| AC-2 offset and limit are honoured | TC-3 |

## Gaps and assumptions

- No customer store exists yet, so `items` is always empty.
MD
