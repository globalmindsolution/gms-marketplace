#!/usr/bin/env bash
# A shipped Python product with a PRD and an architecture set create-docs
# recognises (hld/tech-stack.md), but NO principles set: standards' one extra
# upstream read is absent, which is grounding N/A for the run, never a block.
# A local bare repository stands in for GitHub.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"
acs_repo
acs_prd
acs_architecture
cat > docs/architecture/hld/tech-stack.md <<'MD'
# Tech stack

## Languages

- Python 3.12 (package `shop`, src layout).

## Frameworks

- pytest for unit tests, with pytest-cov for coverage.

## Conventions

- Tests live in `tests/`, one `test_*.py` per module.
MD
git add -A && git commit -qm "Tech stack"
acs_local_origin
