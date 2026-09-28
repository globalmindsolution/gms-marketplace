#!/usr/bin/env bash
# An EXISTING Python product that is standardized in every respect but one:
# architecture set (tech-stack.md, project-structure.md), principles and
# standards sets, a CI workflow, a pre-commit config and a coverage config
# failing below 90% -- and an e2e suite configured in .acs/settings.json
# (suites.e2e, written through acs's own `setup apply`) whose workflow path
# .github/workflows/acs-e2e.yml is ALREADY taken by the team's own
# hand-written workflow. standardize-project/SKILL.md, Inputs & mode: "Set
# AND .github/workflows/acs-e2e.yml already present => standardize-project
# does NOT overwrite the existing file; the conflict becomes a
# recommended_follow_ups entry instead of an in-place modification."
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
| E2E | pytest suite under `e2e/`, run against a local server |
| CI | GitHub Actions |
MD
cat > docs/architecture/hld/project-structure.md <<'MD'
# Project structure

| Path | Holds |
|---|---|
| `src/shop/` | the service package |
| `tests/` | unit tests |
| `e2e/` | end-to-end tests |
| `docs/` | product, architecture, principles and standards docs |
| `.github/workflows/` | CI |
MD
mkdir -p docs/principles docs/standards e2e .github/workflows
printf '# Engineering principles\n\n1. Small, reviewed changes.\n2. Every change is tested.\n' \
  > docs/principles/principles.md
printf '# Coding standards\n\n- PEP 8, enforced by the pre-commit hook.\n- 90%% unit coverage.\n' \
  > docs/standards/coding-standards.md
printf 'def test_health_over_http():\n    assert True\n' > e2e/test_health_e2e.py
cat > .github/workflows/ci.yml <<'YAML'
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pytest pytest-cov
      - run: python3 -m pytest --cov=src --cov-fail-under=90 tests
YAML
cat > .github/workflows/acs-e2e.yml <<'YAML'
# team e2e workflow: boots the service on :8080, then runs e2e/ against it
name: e2e
on: [pull_request]
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pytest
      - run: python3 -m http.server 8080 & python3 -m pytest -q e2e
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
git add -A && git commit -qm "Docs, CI, e2e suite and tooling"

python3 "$ACS_SCRIPTS/acs.py" setup apply --answers - >/dev/null <<'JSON'
{"settings": {"suites": {"e2e": {"command": "python3 -m pytest -q e2e"}}}, "ci": []}
JSON
git add -A && git commit -qm "Configure the e2e suite for acs"
acs_local_origin
