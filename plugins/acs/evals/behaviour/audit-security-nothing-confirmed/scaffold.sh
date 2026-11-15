#!/usr/bin/env bash
# /acs:audit-security on a repo with nothing to confirm and no threat model:
#
#   look-alike  src/shop/stats.py builds two queries with f-strings -- but the
#               only thing interpolated is TABLE, a module constant, and the one
#               user-supplied value (order_id) is a bound parameter. An auditor
#               may raise it as SQL injection; an adjudicator prompted to refute
#               it can (the input is not attacker-controlled), so it belongs
#               under Refuted -- never at a severity
#   no threat   docs/architecture is an architecture set (hld/tech-stack.md and
#   model       a container view) with no hld/data-flow.md and no
#               hld/cross-cutting.md, so the threat-model slice is skipped, with
#               the reason pointing at the data-flow view /acs:setup enables
#
# No secret, no dependency (pyproject.toml declares none), no route. `acs run
# new` records the standing run the audit works under (no ticket, no lock, no
# step); `acs step start --step audit-security` resumes it, so the workspace
# paths the graders read are fixed.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }

acs_repo

cat > src/shop/stats.py <<'PY'
"""Order statistics for the merchant dashboard."""
import sqlite3

TABLE = "orders"


def count_orders(conn: sqlite3.Connection) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]


def order_by_id(conn, order_id):
    return conn.execute(f"SELECT id, product FROM {TABLE} WHERE id = ?", (order_id,)).fetchone()
PY
A=docs/architecture
mkdir -p $A/hld
cat > $A/hld/tech-stack.md <<'MD'
# Tech stack

## Languages

Python 3.

## Data

SQLite, one `orders` table.
MD
cat > $A/hld/c4-container.md <<'MD'
# C4 container

```mermaid
C4Container
  Person(merchant, "Merchant")
  Container(shop, "shop", "Python 3", "storefront and merchant dashboard")
  ContainerDb(db, "orders", "SQLite")
  Rel(merchant, shop, "views order statistics")
  Rel(shop, db, "reads")
```
MD
git add -A
git commit -qm "Merchant order statistics; the HLD"
acs run new --prompt "Audit the repository for security weaknesses" > /dev/null
