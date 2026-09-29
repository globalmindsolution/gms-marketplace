#!/usr/bin/env bash
# An EXISTING Python product (src/, tests/, pyproject.toml, CHANGELOG) with a
# PRD and an approved architecture set, on which the user names the
# create-project leg directly. Its pre-hook passes (it gates on settings, not
# on the tree); its own Greenfield gate (`git ls-files` minus docs/, .acs/,
# README, LICENSE, CLAUDE.md, .gitignore) lists src/, tests/, pyproject.toml
# and CHANGELOG.md, so it must refuse: straight to Finish with `failed`, all
# four scaffold booleans false, one `greenfield` finding -- and write nothing
# into the repo.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
cat > docs/architecture/hld/tech-stack.md <<'MD'
# Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| Packaging | `pyproject.toml` |
| Tests | pytest, with pytest-cov enforcing the 90% coverage target |
| Lint / format | ruff |
| CI | GitHub Actions |
| E2E | none |
MD
git add -A && git commit -qm "Tech stack"
acs_local_origin
