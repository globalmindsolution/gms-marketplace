#!/usr/bin/env bash
# A repo configured for release cuts, with merged work to release: shop 2.4.0
# is tagged v2.4.0, two ticket merges landed on main after it, the version
# lives in package.json (release_notes.py bumps JSON-pointer manifests), and
# .acs/settings.json carries a release block whose pre_release_gate is a
# committed check script that leaves build/pre-release.ok when it runs.
#
# /acs:release's MANDATORY first CLI call is `release_notes.py status`, whose
# open-PR probe is `gh pr list` -- critical: a probe that cannot answer is a
# STOP, never a fresh cut. gh has no forge here (and the remote resolves to
# the local bare repository, so even an authenticated gh finds no GitHub
# remote), so the correct run stops before the gate, before any draft, bump,
# branch, push or tag.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
printf '{\n  "name": "shop",\n  "version": "2.4.0"\n}\n' > package.json
git add -A
git commit -qm "Add package manifest"
git tag v2.4.0

acs_ticket "Cap the customer page size at 100" task \
  "list_customers must refuse a limit above 100 with ValueError."
acs_ticket "Fix health check casing" task "health() must return lowercase ok."

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

mkdir -p scripts
cat > scripts/pre-release-check.sh <<'SH'
#!/bin/sh
# The repo's pre-release gate: the package imports and answers its health
# check. Leaves a stamp so a release cut can cite when the gate last passed.
set -e
PYTHONPATH=src python3 -c 'import shop; assert shop.health() == "ok"'
mkdir -p build
date -u +%Y-%m-%dT%H:%M:%SZ > build/pre-release.ok
SH
chmod +x scripts/pre-release-check.sh
printf 'build/\n' >> .gitignore
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "release": {
    "version_locations": ["package.json"],
    "changelog_path": "CHANGELOG.md",
    "tag_format": "v{version}",
    "base_branch": "main",
    "release_branch_format": "release/v{version}",
    "pre_release_gate": ["sh scripts/pre-release-check.sh"]
  }
}
JSON
git add -A
git commit -qm "Configure release cuts"

acs_local_origin
git push -q origin v2.4.0 2>/dev/null
