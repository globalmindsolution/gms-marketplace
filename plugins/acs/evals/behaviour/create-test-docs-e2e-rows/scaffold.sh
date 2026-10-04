#!/usr/bin/env bash
# create-test-docs (e2e rows): the shop repo with an HTTP front
# (src/shop/web.py, /health only) and an e2e harness that drives it in process
# (tests/e2e/, a stdlib unittest suite), configured as the `e2e` suite in
# .acs/settings.json. Task EVAL-1 wires GET /customers; two of its criteria
# are HTTP behaviour. The working tree (main, uncommitted -- ADR-0127) carries the published plan (SKILL.md's
# format, left uncommitted as the planning coordinator does with cp) owing test
# cases AND e2e.
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
mkdir -p tests/e2e
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
        status, _headers, body = get("/health")
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
git commit -qm "HTTP front with /health and its e2e harness"
ACS_FEATURES=customer-listing
acs_ticket "Serve the customer listing over HTTP" task false \
  "Expose list_customers as GET /customers on the WSGI front, honouring offset and limit, so the storefront can page through customers."
printf '%s' '{"acceptance_criteria": [
  "An HTTP GET /customers against the running WSGI app returns 200 with a JSON body listing customers, 20 per page by default",
  "An HTTP GET /customers?offset=40&limit=10 against the running WSGI app returns the page at offset 40 with limit 10",
  "list_customers rejects a negative offset with ValueError"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null

mkdir -p docs/development/customer-listing/EVAL-1
cat > docs/development/customer-listing/EVAL-1/plan.md <<'MD'
# Plan — EVAL-1: Serve the customer listing over HTTP

Planned from the ticket's criteria and the codebase (no analysis published).

## Approach

`src/shop/web.py` routes GET /customers to `list_customers(offset, limit)`
and returns its JSON; `list_customers` in `src/shop/__init__.py` raises
`ValueError` on a negative offset.

## Tests

- Unit (tests/unit/test_customers.py): the negative-offset `ValueError`.
- End to end (the configured `e2e` suite, tests/e2e/ through harness.py): the
  two HTTP criteria, driven through the running WSGI app.

Run `python3 -m pytest -q --cov=src --cov-fail-under=90`; coverage target
90%. Run the e2e suite with its configured command.

## Contract
delivery_path: small
owes:
  api_contract: false
  test_cases: true
  e2e: true
  reason: "README already documents GET /customers; this wires the existing function to the WSGI front, and two criteria are HTTP behaviour"

### Executor tasks & file map
- task 1: src/shop/web.py, src/shop/__init__.py, tests/unit/test_customers.py
MD
