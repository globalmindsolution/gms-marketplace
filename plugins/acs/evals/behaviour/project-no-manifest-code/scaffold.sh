#!/usr/bin/env bash
# An EXISTING Python codebase the evidence table cannot classify: source under
# app/, tests, a requirements.txt -- and none of the declared evidence rows
# (acs_lib.PROJECT_MODE_SENTINEL: pyproject.toml, setup.py, package.json, ...,
# .pre-commit-config.yaml, .coveragerc). /acs:project therefore reports
# `bootstrap` and dispatches create-project, whose OWN greenfield scan finds
# app/, tests/ and requirements.txt and refuses. Documented outcome: report the
# refusal and stop -- never re-dispatch to standardize-project to get past it
# (project/SKILL.md, "The leg's own second check is not redundant").
#
# acs_repo would plant a pyproject.toml (evidence), so the repo is initialised
# here instead -- same remote, identity, ticket prefix and reconciled counters
# seam as ../_fixtures/repo.sh's acs_repo.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

git init -q -b main
git remote add origin https://github.com/example/shop.git
git config user.email eval@example.com
git config user.name eval
mkdir -p .acs "$ACS_PARTITION" app tests
printf '{\n  "ticket_prefix": "EVAL"\n}\n' > .acs/settings.json
printf '.acs/state-machine/\n.acs/settings.local.json\n.eval-origin.git/\n' > .gitignore
printf '# shop\n\nA small storefront service. Run it with `python3 -m app`.\n' > README.md
cat > app/__init__.py <<'PY'
PAGE_SIZE = 20


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    return {"items": [], "offset": offset, "limit": limit}
PY
printf 'from app import health\n\n\ndef test_health():\n    assert health() == "ok"\n' \
  > tests/test_health.py
printf 'pytest==8.3.3\n' > requirements.txt
printf '{"next": 1, "reconciled": true, "seed_source": "explicit-user", "seeded_at": "%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ACS_PARTITION/counters.json"
git add -A
git commit -qm "shop, before packaging"

acs_prd
acs_architecture
cat > docs/architecture/hld/tech-stack.md <<'MD'
# Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| Dependencies | `requirements.txt` |
| Layout | `app/` (the service), `tests/` |
| Tests | pytest |
| CI | GitHub Actions |
MD
git add -A && git commit -qm "Tech stack"
acs_local_origin
