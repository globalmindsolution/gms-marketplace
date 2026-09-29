#!/usr/bin/env bash
# An EXISTING Python product that already meets every expectation
# standardize-project audits: an architecture set (tech-stack.md and a
# project-structure.md the layout matches), principles and standards sets, a
# CI workflow, a pre-commit config and a coverage config failing below 90%;
# no e2e suite configured, so the e2e dimension is N/A. SKILL.md, Inputs &
# mode: "a second run against an already-standardized repo finds nothing left
# to scaffold and reports zero gaps" -- the audit still runs and Finish still
# records a result, but no file is added and no existing set is recommended.
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
| Tests | pytest, with coverage (`.coveragerc`) enforcing the 90% target |
| Pre-commit | `.pre-commit-config.yaml` running the unit tests |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |
| E2E | none: the service has no UI and no cross-service flow yet |
MD
cat > docs/architecture/hld/project-structure.md <<'MD'
# Project structure

| Path | Holds |
|---|---|
| `src/shop/` | the service package |
| `tests/` | unit tests |
| `docs/` | product, architecture, principles and standards docs |
| `.github/workflows/` | CI |
MD
mkdir -p docs/principles docs/standards .github/workflows
printf '# Engineering principles\n\n1. Small, reviewed changes.\n2. Every change is tested.\n' \
  > docs/principles/principles.md
printf '# Coding standards\n\n- PEP 8, enforced in review.\n- 90%% unit coverage, enforced in CI.\n' \
  > docs/standards/coding-standards.md
cat > .github/workflows/ci.yml <<'YAML'
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pytest coverage
      - run: python3 -m coverage run -m pytest tests && python3 -m coverage report
YAML
cat > .pre-commit-config.yaml <<'YAML'
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: python3 -m pytest -q tests
        language: system
        pass_filenames: false
YAML
printf '[run]\nsource = src\n\n[report]\nfail_under = 90\n' > .coveragerc
git add -A && git commit -qm "Docs, CI and tooling"
acs_local_origin
