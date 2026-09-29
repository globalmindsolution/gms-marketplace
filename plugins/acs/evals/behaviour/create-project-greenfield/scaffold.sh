#!/usr/bin/env bash
# A GREENFIELD product repo: a PRD and an approved architecture set (with the
# hld/tech-stack.md create-project derives its scaffold from), and NO source,
# build manifest, tests or CI -- so /acs:project's declared evidence table
# finds nothing and dispatches the create-project leg, and that leg's own
# greenfield scan (`git ls-files` minus docs/, .acs/, README, .gitignore)
# comes back empty.
#
# acs_repo would plant src/, tests/ and a pyproject.toml, so the repo is
# initialised here instead -- same remote, identity, ticket prefix and
# reconciled counters seam as ../_fixtures/repo.sh's acs_repo.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

git init -q -b main
git remote add origin https://github.com/example/shop.git
git config user.email eval@example.com
git config user.name eval
mkdir -p .acs "$ACS_PARTITION"
printf '{\n  "ticket_prefix": "EVAL"\n}\n' > .acs/settings.json
printf '.acs/state-machine/\n.acs/settings.local.json\n.eval-origin.git/\n' > .gitignore
printf '# shop\n\nA small storefront service. Nothing is built yet: see docs/.\n' > README.md
printf '{"next": 1, "reconciled": true, "seed_source": "explicit-user", "seeded_at": "%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ACS_PARTITION/counters.json"
git add -A
git commit -qm "Empty product repo"

acs_prd
acs_architecture

# The file create-project's Start looks for: without it the leg takes the
# no-architecture fallback and has to ask for a stack, which an eval run
# cannot answer.
cat > docs/architecture/hld/tech-stack.md <<'MD'
# Tech stack

Approved 2026-09-20.

| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| Packaging | `pyproject.toml` (PEP 621, setuptools backend), installed with `pip install -e .[dev]` |
| Layout | `src/shop/` (the package), `tests/` (unit tests) |
| HTTP | standard library `http.server` for now; no web framework |
| Tests | pytest |
| Coverage | pytest-cov, configured in `pyproject.toml`, failing below the acs coverage target (90%) |
| Lint / format | ruff (`ruff check`, `ruff format --check`), configured in `pyproject.toml` |
| Pre-commit | `.pre-commit-config.yaml` running ruff |
| CI | GitHub Actions, one workflow running install, lint and tests with coverage |
| E2E | none yet: the API has no user-facing UI; no e2e harness |

The first vertical slice is `GET /health` returning `ok`.
MD
git add -A && git commit -qm "Approve the tech stack"
acs_local_origin
