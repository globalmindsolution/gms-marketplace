#!/usr/bin/env bash
# A GREENFIELD product repo: README, LICENSE, CLAUDE.md, a PRD and an approved
# architecture set with hld/tech-stack.md -- and no build manifest, source,
# tests, CI, pre-commit or coverage config. /acs:project's evidence table
# (acs_lib.PROJECT_MODE_SENTINEL) finds none of its rows, so the mode is
# `bootstrap` and the leg is create-project, whose own greenfield scan ignores
# docs/, .acs/, README, LICENSE, CLAUDE.md and .gitignore and comes back empty.
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
printf 'MIT License\n\nCopyright (c) 2026 example\n' > LICENSE
printf '# CLAUDE.md\n\nProduct docs live under docs/. The stack is pinned in docs/architecture/hld/tech-stack.md.\n' > CLAUDE.md
printf '{"next": 1, "reconciled": true, "seed_source": "explicit-user", "seeded_at": "%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ACS_PARTITION/counters.json"
git add -A
git commit -qm "Empty product repo"

acs_prd
acs_architecture

cat > docs/architecture/hld/tech-stack.md <<'MD'
# Tech stack

Approved 2026-09-20.

| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| Packaging | `pyproject.toml` (PEP 621, setuptools backend), installed with `pip install -e .[dev]` |
| Layout | `src/shop/` (the package), `tests/` (unit tests) |
| HTTP | standard library `http.server`; no web framework |
| Tests | pytest |
| Coverage | pytest-cov, configured in `pyproject.toml`, failing below the acs coverage target (90%) |
| Lint / format | ruff, configured in `pyproject.toml` |
| Pre-commit | `.pre-commit-config.yaml` running ruff |
| CI | GitHub Actions, one workflow running install, lint and tests with coverage |
| E2E | none yet |

The first vertical slice is `GET /health` returning `ok`.
MD
git add -A && git commit -qm "Approve the tech stack"
acs_local_origin
