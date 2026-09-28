#!/usr/bin/env bash
# /acs:run-e2e-tests when the failure it finds is already ticketed. The e2e
# suite's command byte-compiles src/ before it runs any test, and
# src/shop/web.py has a syntax error, so the suite fails before a single test
# runs: there is no parseable failing-test id, and the C-1 fallback key is the
# literal `e2e:__suite__`. An earlier standing run already minted EVAL-1 for
# that exact key (through new-ticket.py, status open), so the dedup lookup
# finds it. What the run must produce: EVAL-1 comment-bumped with this run's
# fresh evidence (its original description kept), NO second ticket, and the
# results artifact. The `unit` suite does not import web.py and stays green.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

# A half-finished edit: the closing parenthesis of the /customers response is
# missing, so the module does not compile.
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
                     json.dumps(list_customers(offset, limit))
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

    def test_list_customers_defaults_to_page_size(self):
        self.assertEqual(list_customers()["limit"], PAGE_SIZE)
PY
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
cat > tests/e2e/test_customers_e2e.py <<'PY'
import json
import unittest

from harness import get


class CustomersE2E(unittest.TestCase):
    def test_customers_default_page(self):
        status, _, body = get("/customers")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["limit"], 20)
PY
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "suites": {
    "unit": {
      "command": "PYTHONPATH=src python3 -m unittest discover -s tests/unit -p 'test_*.py'"
    },
    "e2e": {
      "command": "python3 -m compileall -q src && PYTHONPATH=src python3 -m unittest discover -s tests/e2e -p 'test_*.py'"
    }
  }
}
JSON
# Running the suites leaves bytecode behind; a real repo ignores it.
printf '__pycache__/\n' >> .gitignore
git add -A
git commit -qm "HTTP front, unit and e2e suites"

# The ticket an earlier standing run minted for this very failure.
python3 "$ACS_SCRIPTS/new-ticket.py" --title "e2e: suite regression" --type task \
  --description "$(printf '%s\n\n%s\n\n%s' \
    'acs-regression-key: e2e:__suite__' \
    'The e2e suite fails before any test runs: src/shop/web.py does not compile.' \
    'First seen on the standing run of 2026-09-27.')" > /dev/null
