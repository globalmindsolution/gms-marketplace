#!/usr/bin/env bash
# /acs:review-code on a ticket whose changeset -- uncommitted on main, as
# /acs:code leaves it (ADR-0127) -- carries a REAL, obvious
# defect: `page_bounds` documents 1-based pages and computes 0-based bounds, so
# page 1 returns customers 20-39 and the first page is unreachable. The
# changeset's own test only checks a page's LENGTH, so it passes -- the defect
# is visible in the diff and against the ticket's acceptance criteria, not in a
# red test. A correct review confirms a blocking finding on it.
#
# Seeded only through ordinary repo files and the plugin's own CLIs:
# new-ticket.py mints EVAL-1, `acs.py ticket save` records its acceptance
# criteria, and a `code` step opened with `acs.py step start` and closed with
# post-code.py brackets the change (no lock left held).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Add 1-based page numbers to the customer listing" task false \
  "Merchants page through customers by page number, starting at page 1."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["list_customers_page(customers, page=1) returns the first per_page customers", "list_customers_page(customers, page=2) returns the next per_page customers", "page numbers start at 1"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

# /acs:code's step, opened before the change it leaves behind: its start
# records the run's baseline (ADR-0127) on the clean tree, so the change
# below is the run's changeset, uncommitted on main as /acs:code leaves it.
acs step start --step code --ticket EVAL-1 > /dev/null 2>&1
cat > src/shop/__init__.py <<'PY'
PAGE_SIZE = 20


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    return {"items": [], "offset": offset, "limit": limit}


def page_bounds(page, per_page=PAGE_SIZE):
    """Slice bounds for a 1-based page number."""
    start = page * per_page
    return start, start + per_page


def list_customers_page(customers, page=1, per_page=PAGE_SIZE):
    """One page of customers; page 1 is the first page."""
    start, end = page_bounds(page, per_page)
    return customers[start:end]
PY
cat > tests/test_pagination.py <<'PY'
from shop import list_customers_page


def test_a_page_holds_per_page_customers():
    customers = list(range(50))
    assert len(list_customers_page(customers, page=2, per_page=10)) == 10
PY
python3 - <<'PY'
import re
readme = open("README.md").read().replace(
    "- `GET /customers?offset=&limit=` lists customers, 20 per page by default.",
    "- `GET /customers?offset=&limit=` lists customers, 20 per page by default.\n"
    "- `GET /customers?page=` lists one page of customers; pages start at 1.")
open("README.md", "w").write(readme)
log = open("CHANGELOG.md").read().replace(
    "## [2.4.0]", "## [Unreleased]\n\n- Page numbers for the customer listing.\n\n## [2.4.0]")
open("CHANGELOG.md", "w").write(log)
PY
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed", "summary": "implemented; nothing committed (ADR-0127)",
 "findings": [], "errors": []}
JSON
