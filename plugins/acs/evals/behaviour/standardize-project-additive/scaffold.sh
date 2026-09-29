#!/usr/bin/env bash
# An EXISTING Python product with a PRD, an architecture set (tech-stack.md
# and the hld/project-structure.md the audit compares the layout against) and
# a committed pre-commit config -- but no CI workflow, no coverage config and
# no principles or standards doc sets. What standardize-project owes: add the
# missing tooling as new files (or named appends), recommend the missing doc
# sets as follow-ups, and touch no existing source. The bare local origin
# lets it push its branch; `gh` has no forge.
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
| CI | GitHub Actions |
| E2E | none |
MD
cat > docs/architecture/hld/project-structure.md <<'MD'
# Project structure

| Path | Holds |
|---|---|
| `src/shop/` | the service package |
| `tests/` | unit tests, one module per source module |
| `docs/` | product and architecture docs |
| `.github/workflows/` | CI |
MD
cat > .pre-commit-config.yaml <<'YAML'
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: python3 -m pytest -q
        language: system
        pass_filenames: false
YAML
git add -A && git commit -qm "Tech stack, project structure, pre-commit"
acs_local_origin
