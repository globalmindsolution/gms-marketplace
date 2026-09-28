#!/usr/bin/env bash
# A repo with merged work to release -- shop 2.4.0 tagged v2.4.0, two ticket
# merges on main after it, the version in package.json -- but NOT configured
# for release cuts: .acs/settings.json carries no `release` block.
#
# /acs:release "fails fast if no release block is configured": a
# coordinator-level pre-flight, BEFORE `release_notes.py` is called at all,
# with an actionable error pointing at the settings schema's `release`
# sub-schema. It must not guess a block, write one, or cut by hand.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
printf '{\n  "name": "shop",\n  "version": "2.4.0"\n}\n' > package.json
git add -A
git commit -qm "Add package manifest"
git tag v2.4.0

acs_ticket "Cap the customer page size at 100" task false \
  "list_customers must refuse a limit above 100 with ValueError."
acs_ticket "Fix health check casing" task false "health() must return lowercase ok."

cat > src/shop/__init__.py <<'PY'
PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    if limit > MAX_PAGE_SIZE:
        raise ValueError("limit must be at most %d" % MAX_PAGE_SIZE)
    return {"items": [], "offset": offset, "limit": limit}
PY
git commit -qam "EVAL-1 Cap the customer page size at 100 (#3)"
printf '\n- `GET /health` always answers in lowercase.\n' >> README.md
git commit -qam "EVAL-2 Fix health check casing (#4)"

acs_local_origin
git push -q origin v2.4.0 2>/dev/null
