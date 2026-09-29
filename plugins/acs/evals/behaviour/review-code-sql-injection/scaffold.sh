#!/usr/bin/env bash
# /acs:review-code on a ticket branch whose changeset carries a SECURITY
# defect: find_customer_by_email builds its SQL by string formatting, so an
# email like `' OR '1'='1` returns every customer (SQL injection). The
# changeset's own test uses an ordinary address, so it passes -- the defect is
# visible in the diff, not in a red test. A correct review confirms a blocking
# finding on it (lens B judges security from the diff alone).
#
# Seeded only through ordinary committed repo files and the plugin's own CLIs:
# new-ticket.py mints EVAL-1, `acs.py ticket save` records its acceptance
# criteria, and `acs.py run new` records the run over it (no lock, no step).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Look up a customer by email" task false \
  "Support staff need to find a customer's record from the email address they wrote in from."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["find_customer_by_email(conn, email) returns the one customer row with that email, or None", "the lookup is safe for any email string a user can type"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

acs_branch "task/EVAL-1-look-up-a-customer-by-email"
cat > src/shop/store.py <<'PY'
import sqlite3


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, email TEXT)")
    return conn


def find_customer_by_email(conn, email):
    """The customer row with this email, or None."""
    query = "SELECT id, email FROM customers WHERE email = '%s'" % email
    return conn.execute(query).fetchone()
PY
cat > tests/test_store.py <<'PY'
from shop.store import connect, find_customer_by_email


def test_a_known_email_finds_its_customer():
    conn = connect()
    conn.execute("INSERT INTO customers (email) VALUES ('ann@example.com')")
    assert find_customer_by_email(conn, "ann@example.com") == (1, "ann@example.com")


def test_an_unknown_email_finds_nobody():
    assert find_customer_by_email(connect(), "bob@example.com") is None
PY
python3 - <<'PY'
log = open("CHANGELOG.md").read().replace(
    "## [2.4.0]", "## [Unreleased]\n\n- Look up a customer by email.\n\n## [2.4.0]")
open("CHANGELOG.md", "w").write(log)
PY
git add -A
git commit -qm "EVAL-1 Look up a customer by email"
acs run new --ticket EVAL-1 > /dev/null
