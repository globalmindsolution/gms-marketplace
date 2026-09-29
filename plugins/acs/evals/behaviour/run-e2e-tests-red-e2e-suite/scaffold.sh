#!/usr/bin/env bash
# /acs:run-e2e-tests as a standing run against the repo: two configured suites,
# `unit` (green) and `e2e` (red). The e2e suite was written ahead of a change
# that has not landed -- it expects GET /customers to default to 50 per page,
# and the product still pages by 20 -- so exactly one test fails, with a
# parseable test id. Both suites are stdlib unittest (no pytest, no socket):
# the e2e suite drives the WSGI app in process, so the verdict is the same on
# every host. What the run must produce: a results artifact under test-runs/,
# one regression ticket minted for the e2e failure (the first id the counter
# gives, EVAL-1) carrying its `acs-regression-key: e2e:...` marker, and none
# for the passing unit suite.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

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
mkdir -p tests/unit tests/e2e
cat > tests/unit/test_shop.py <<'PY'
import unittest

from shop import PAGE_SIZE, health, list_customers


class Shop(unittest.TestCase):
    def test_health(self):
        self.assertEqual(health(), "ok")

    def test_list_customers_honours_offset_and_limit(self):
        self.assertEqual(list_customers(40, 10), {"items": [], "offset": 40, "limit": 10})

    def test_list_customers_defaults_to_page_size(self):
        self.assertEqual(list_customers()["limit"], PAGE_SIZE)
PY
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
cat > tests/e2e/test_customers_e2e.py <<'PY'
import json
import unittest

from harness import get


class CustomersE2E(unittest.TestCase):
    def test_health_returns_ok(self):
        status, _, body = get("/health")
        self.assertEqual((status, body), (200, "ok"))

    def test_customers_default_page_is_50(self):
        """TC-2: GET /customers lists 50 per page by default."""
        status, _, body = get("/customers")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["limit"], 50)
PY
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "suites": {
    "unit": {
      "command": "PYTHONPATH=src python3 -m unittest discover -s tests/unit -p 'test_*.py'"
    },
    "e2e": {
      "command": "PYTHONPATH=src python3 -m unittest discover -s tests/e2e -p 'test_*.py'"
    }
  }
}
JSON
# Running the suites leaves bytecode behind; a real repo ignores it.
printf '__pycache__/\n' >> .gitignore
git add -A
git commit -qm "HTTP front, unit and e2e suites"
