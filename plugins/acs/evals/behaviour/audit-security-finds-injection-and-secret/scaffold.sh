#!/usr/bin/env bash
# /acs:audit-security on a small Flask service with two real weaknesses and a
# dependency manifest nothing can scan:
#
#   injection   src/shop/orders_api.py:14 -- GET /orders/search interpolates the
#               `q` query parameter into an f-string that cursor.execute runs
#               with no bound parameters (CWE-89), on a route with no login
#   secret      config/production.ini:3 -- a hard-coded payments API token
#               (CWE-798). The token is made up and has no provider's prefix, so
#               no forge's secret scanning reacts to it; the audit must still
#               report it as live and never write its value anywhere
#   dependencies requirements.txt pins flask and requests, and the repo has no
#               scanner (no pip-audit, no osv-scanner in its tooling) -- and an
#               eval run has no network, so even a host-installed scanner cannot
#               reach its advisory database. The category is uncovered, never
#               "clean", and no CVE may be named from memory
#
# There is no architecture set, so the threat-model slice is skipped. `acs run
# new` records the standing run the audit works under (no ticket, no lock, no
# step); `acs step start --step audit-security` resumes it, so the workspace
# paths the graders read are fixed.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }

acs_repo

cat > src/shop/orders_api.py <<'PY'
"""GET /orders/search?q= -- a shopper searches orders by product name."""
import sqlite3

from flask import Flask, request

app = Flask(__name__)
DATABASE = "shop.db"


@app.route("/orders/search")
def search_orders():
    q = request.args.get("q", "")
    cursor = sqlite3.connect(DATABASE).cursor()
    cursor.execute(f"SELECT id, product, total FROM orders WHERE product LIKE '%{q}%'")
    return {"items": cursor.fetchall()}
PY
mkdir -p config
# Built from two halves so the literal never sits in this repo's history for its
# own secret scan to flag; the file the audit reads holds the whole value.
seeded="shpay_7f3c9a1e""5b2d8f604c1a9e7b3d5f2a8c"
cat > config/production.ini <<INI
[payments]
endpoint = https://payments.example.com/v1
api_token = ${seeded}
timeout_seconds = 10
INI
printf 'flask==2.0.1\nrequests==2.25.1\n' > requirements.txt
git add -A
git commit -qm "Order search and the payments client config"
acs run new --prompt "Audit the security of the repository" > /dev/null
