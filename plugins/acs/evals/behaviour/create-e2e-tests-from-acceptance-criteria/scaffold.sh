#!/usr/bin/env bash
# /acs:create-e2e-tests with NO test-cases.md: the shop's WSGI front gained
# GET /customers for EVAL-1 (uncommitted on main, ADR-0127), the repo has an e2e harness (tests/e2e/, a
# stdlib unittest suite that drives the WSGI app in process) configured as the
# `e2e` suite, and the ticket carries two acceptance criteria describing
# end-to-end flows -- but /acs:create-test-docs never ran, so there is no case
# document. The skill's fallback: the acceptance criteria are the
# specification, each derived case carries its `AC-<n>`, and the report says no
# case document existed. The criteria are written onto the ticket through the
# plugin's own `acs.py ticket save`. What the run must produce: a suite under
# tests/e2e/ covering AC-1 and AC-2, left uncommitted (no branch, no commit), the
# step's cases_covered naming them, and no case document or product code.
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
printf '__pycache__/\n' >> .gitignore
git add -A
git commit -qm "HTTP front with /health and its e2e harness"

ACS_FEATURES=customer-listing
acs_ticket "Serve the customer listing over HTTP" task false \
  "Expose list_customers as GET /customers on the WSGI front, honouring offset and limit."
python3 - "$ACS_SCRIPTS" <<'PY'
import json, subprocess, sys
acs = [sys.executable, sys.argv[1] + "/acs.py"]
ticket = json.loads(subprocess.run(acs + ["ticket", "show", "--ticket", "EVAL-1"], check=True,
                                   capture_output=True, text=True).stdout)["ticket"]
ticket["acceptance_criteria"] = [
    "GET /customers responds 200 with Content-Type application/json and the body "
    "{\"items\": [], \"offset\": 0, \"limit\": 20}",
    "GET /customers?offset=40&limit=10 responds 200 with offset 40 and limit 10 in the body",
]
subprocess.run(acs + ["ticket", "save", "--ticket", "EVAL-1", "--from", "-"], check=True,
               input=json.dumps(ticket), capture_output=True, text=True)
PY

# /acs:code's change, uncommitted. No test-cases.md anywhere.
python3 - <<'PY'
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
