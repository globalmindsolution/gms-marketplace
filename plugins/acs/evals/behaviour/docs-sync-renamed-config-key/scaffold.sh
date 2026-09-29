#!/usr/bin/env bash
# /acs:docs-sync on a renamed configuration key documented in TWO places: the
# shop reads its page size from the environment, and EVAL-1 renamed the
# variable from SHOP_PAGE_SIZE to SHOP_CUSTOMERS_PAGE_SIZE (a hard rename: the
# old name is no longer read). README.md's Configuration section and
# docs/configuration.md's table both still document SHOP_PAGE_SIZE. /acs:code's
# step is recorded completed through the plugin's own writers (`acs.py step
# start`, then `post-code.py`), with no doc updated. What the run must
# produce: BOTH docs naming SHOP_CUSTOMERS_PAGE_SIZE as the setting, committed
# as new commit(s) on the SAME ticket branch, and both listed in
# docs_committed.
#
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo

cat > src/shop/config.py <<'PY'
"""Runtime configuration, read from the environment."""
import os


def page_size():
    """Customers per page for GET /customers."""
    return int(os.environ.get("SHOP_PAGE_SIZE", "20"))
PY
cat >> README.md <<'MD'

## Configuration

- `SHOP_PAGE_SIZE` — customers per page (default 20).

See [docs/configuration.md](docs/configuration.md) for every setting.
MD
mkdir -p docs
cat > docs/configuration.md <<'MD'
# Configuration

shop reads its settings from environment variables at startup.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SHOP_PAGE_SIZE` | `20` | Customers per page for `GET /customers`. |

Set a variable in the service's environment and restart it to apply.
MD
git add -A
git commit -qm "Environment configuration and its docs"

acs_ticket "Rename SHOP_PAGE_SIZE to SHOP_CUSTOMERS_PAGE_SIZE" task false \
  "The page-size variable is renamed to SHOP_CUSTOMERS_PAGE_SIZE so it names what it pages. The old name is no longer read."
acs_branch task/EVAL-1-rename-shop-page-size-to-shop-customers-page-size

python3 "$ACS_SCRIPTS/acs.py" step start --step code --ticket EVAL-1 > /dev/null 2>&1
sed -i.bak 's/"SHOP_PAGE_SIZE"/"SHOP_CUSTOMERS_PAGE_SIZE"/' src/shop/config.py && rm -f src/shop/config.py.bak
cat > tests/test_config.py <<'PY'
from shop.config import page_size


def test_page_size_reads_the_renamed_variable(monkeypatch):
    monkeypatch.setenv("SHOP_CUSTOMERS_PAGE_SIZE", "50")
    assert page_size() == 50


def test_the_old_name_is_ignored(monkeypatch):
    monkeypatch.delenv("SHOP_CUSTOMERS_PAGE_SIZE", raising=False)
    monkeypatch.setenv("SHOP_PAGE_SIZE", "50")
    assert page_size() == 20
PY
git add -A
git commit -qm "EVAL-1 rename SHOP_PAGE_SIZE to SHOP_CUSTOMERS_PAGE_SIZE"
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed",
 "summary": "page_size() reads SHOP_CUSTOMERS_PAGE_SIZE; SHOP_PAGE_SIZE is no longer read",
 "states": {"branch": "task/EVAL-1-rename-shop-page-size-to-shop-customers-page-size", "docs_updated": []},
 "findings": [], "errors": []}
JSON
