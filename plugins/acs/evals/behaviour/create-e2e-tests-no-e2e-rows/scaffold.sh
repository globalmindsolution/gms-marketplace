#!/usr/bin/env bash
# /acs:create-e2e-tests on a ticket whose case document owes no e2e coverage:
# EVAL-1 clamps list_customers' limit to 100 (a library change, done and left
# uncommitted on main with its unit test, ADR-0127), and the ticket's
# test-cases.md types BOTH its cases `unit` (front matter `e2e_cases: 0`). The
# repo has an e2e harness (tests/e2e/, a stdlib unittest suite driving the
# WSGI app in process) configured as the `e2e` suite, so the only thing missing
# is an e2e case. No plan exists, so the pre-hook has no evidenced no-op to
# settle and the skill runs. What the run must produce: nothing in the repo --
# no suite, no edit to test-cases.md, no commit -- and the step completed with
# outcome `no_e2e_owed`.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

# main: the WSGI front and the e2e harness that drives it.
cat > src/shop/web.py <<'PY'
"""The shop's HTTP front: a WSGI app over the shop API."""
import json
from urllib.parse import parse_qs

from shop import PAGE_SIZE, health, list_customers


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    query = parse_qs(environ.get("QUERY_STRING", ""))
    if path == "/health":
        return _send(start_response, "200 OK", "text/plain", health())
    if path == "/customers":
        offset = int(query.get("offset", ["0"])[0])
        limit = int(query.get("limit", [str(PAGE_SIZE)])[0])
        return _send(start_response, "200 OK", "application/json",
                     json.dumps(list_customers(offset, limit)))
    return _send(start_response, "404 Not Found", "text/plain", "not found")


def _send(start_response, status, content_type, body):
    data = body.encode("utf-8")
    start_response(status, [("Content-Type", content_type),
                            ("Content-Length", str(len(data)))])
    return [data]
PY
mkdir -p tests/e2e tests/unit
cat > tests/e2e/harness.py <<'PY'
"""Drive the WSGI app end to end, in process. Every e2e suite imports `get`."""
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
        status, _, body = get("/health")
        self.assertEqual((status, body), (200, "ok"))
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
printf '__pycache__/\n' >> .gitignore
git add -A
git commit -qm "HTTP front and its e2e harness"

acs_ticket "Cap the customer page size at 100" task false \
  "list_customers must clamp limit to at most 100."

# /acs:code's change and its unit test, uncommitted ...
sed -i.bak 's/"limit": limit}/"limit": min(limit, 100)}/' src/shop/__init__.py && rm -f src/shop/__init__.py.bak
cat > tests/unit/test_page_cap.py <<'PY'
import unittest

from shop import list_customers


class PageCap(unittest.TestCase):
    def test_limit_above_100_is_clamped(self):
        """TC-1"""
        self.assertEqual(list_customers(limit=500)["limit"], 100)

    def test_limit_at_or_below_100_is_kept(self):
        """TC-2"""
        self.assertEqual(list_customers(limit=100)["limit"], 100)
        self.assertEqual(list_customers(limit=7)["limit"], 7)
PY

# ... and the ticket's case document, where acs resolves it: no e2e row.
mkdir -p docs/tickets/EVAL-1
cat > docs/tickets/EVAL-1/test-cases.md <<'MD'
---
ticket: EVAL-1
cases: 2
e2e_cases: 0
---

# Test cases — EVAL-1: Cap the customer page size at 100

## Scope

`list_customers()` in `src/shop/__init__.py`. The HTTP front passes `limit`
through unchanged, so the cap is fully proven at the function.

## Cases

| ID | AC | Type | Preconditions | Steps | Expected | Suite |
| --- | --- | --- | --- | --- | --- | --- |
| TC-1 | AC-1 | unit | none | call `list_customers(limit=500)` | `limit` is 100 | `tests/unit/test_page_cap.py` |
| TC-2 | AC-1 | unit | none | call `list_customers(limit=100)` and `list_customers(limit=7)` | `limit` is 100 and 7 | `tests/unit/test_page_cap.py` |

## Traceability

| AC | Cases |
| --- | --- |
| AC-1 limit is clamped to at most 100 | TC-1, TC-2 |

## Gaps and assumptions

- No end-to-end case: the route adds no behaviour of its own to the cap.
MD
