#!/usr/bin/env bash
# /acs:run-e2e-tests with `--suite smoke`: three suites are configured --
# `unit`, `e2e` and `smoke` -- and only `smoke` is green. PAGE_SIZE was raised
# to 50 on main while the unit and e2e suites still expect 20, so both are red;
# the smoke suite only drives GET /health. All three are stdlib unittest (no
# pytest, no socket). What the run must produce: only the smoke suite run, so a
# results artifact, a 1-of-1 pass, and NO regression ticket -- running the
# unselected red suites is what would mint one.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

sed -i.bak 's/^PAGE_SIZE = 20$/PAGE_SIZE = 50/' src/shop/__init__.py && rm -f src/shop/__init__.py.bak
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
mkdir -p tests/unit tests/e2e tests/smoke
cat > tests/unit/test_shop.py <<'PY'
import unittest

from shop import list_customers


class Shop(unittest.TestCase):
    def test_list_customers_defaults_to_20(self):
        self.assertEqual(list_customers()["limit"], 20)
PY
cat > tests/harness.py <<'PY'
"""Drive the WSGI app end to end, in process. The e2e and smoke suites import `get`."""
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
    def test_customers_default_page_is_20(self):
        status, _, body = get("/customers")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["limit"], 20)
PY
cat > tests/smoke/test_smoke.py <<'PY'
import unittest

from harness import get


class Smoke(unittest.TestCase):
    def test_health_is_up(self):
        self.assertEqual(get("/health")[::2], (200, "ok"))
PY
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "tests": {
    "unit": {
      "command": "PYTHONPATH=src python3 -m unittest discover -s tests/unit -p 'test_*.py'"
    },
    "e2e": {
      "command": "PYTHONPATH=src:tests python3 -m unittest discover -s tests/e2e -p 'test_*.py'"
    },
    "smoke": {
      "command": "PYTHONPATH=src:tests python3 -m unittest discover -s tests/smoke -p 'test_*.py'"
    }
  }
}
JSON
# Running the suites leaves bytecode behind; a real repo ignores it.
printf '__pycache__/\n' >> .gitignore
git add -A
git commit -qm "Page size 50; unit, e2e and smoke suites"
