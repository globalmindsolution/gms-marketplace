#!/usr/bin/env bash
# An EXISTING Python product with a PRD, principles and standards sets and a
# pre-commit config, but NO architecture set (no hld/tech-stack.md anywhere),
# no CI workflow and no coverage config. standardize-project/SKILL.md, Start:
# a missing architecture set is "never a stop: the run audits against what
# exists ... and records the note 'no architecture set: project-structure
# checks skipped'", and "Run /acs:create-architecture" reaches the user only
# as a recommended_follow_ups entry -- never authored, never invoked inline.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
mkdir -p docs/principles docs/standards
printf '# Engineering principles\n\n1. Small, reviewed changes.\n2. Every change is tested.\n' \
  > docs/principles/principles.md
printf '# Coding standards\n\n- PEP 8.\n- 90%% unit coverage, enforced in CI.\n' \
  > docs/standards/coding-standards.md
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
git add -A && git commit -qm "Principles, standards, pre-commit"
acs_local_origin
