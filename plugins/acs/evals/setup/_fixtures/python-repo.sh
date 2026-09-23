#!/usr/bin/env bash
# The repo every /acs:setup case starts from: a small Python project whose
# main checkout IS the run directory, so everything setup writes -- the
# settings file, the ignore entries, the CI copies -- lands where a grader can
# read it. Sourced by each case's scaffold.sh; runs only under --scaffold.
#
#   * `main` exists locally, so `setup detect` can name the default branch.
#   * the remote is fixed, so the repo's identity is deterministic.
#   * pyproject.toml and tests/ make `test_command_candidates` suggest pytest.
set -euo pipefail

git init -q -b main
git remote add origin https://github.com/example/shop.git
git config user.email eval@example.com
git config user.name eval

mkdir -p src/shop tests
printf 'def health():\n    return "ok"\n' > src/shop/__init__.py
printf 'from shop import health\n\n\ndef test_health():\n    assert health() == "ok"\n' \
  > tests/test_health.py
cat > pyproject.toml <<'TOML'
[project]
name = "shop"
version = "0.1.0"

[tool.pytest.ini_options]
pythonpath = ["src"]
TOML

git add -A
git commit -qm "Initial commit"
