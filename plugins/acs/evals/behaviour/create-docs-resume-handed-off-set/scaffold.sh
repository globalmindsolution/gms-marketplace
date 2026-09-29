#!/usr/bin/env bash
# A quality-set run interrupted mid-author and handed off. EVAL-1 was minted
# through the plugin's own `acs.py step start --doc-set quality --allocate`,
# its delivery branch created, and test-strategy.md half written (two of its
# five required sections, uncommitted) before handoff.py finalized the step
# interrupted and released the lock. coverage-policy.md was never started.
# Resuming by ticket id must rejoin EVAL-1 -- no new ticket -- and treat the
# truncated file as not done. A local bare repository stands in for GitHub.
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
python3 "$ACS_SCRIPTS/acs.py" step start --step create-docs --doc-set quality --allocate \
  > /dev/null 2>&1
acs_branch task/EVAL-1-product-quality-doc-set
mkdir -p docs/quality
cat > docs/quality/test-strategy.md <<'MD'
# Test strategy

## Testing philosophy

Unit tests first, with pytest; every module has a test file.

## Coverage policy

See coverage-policy.md: 90% line coverage or the pipeline fails.
MD
python3 "$ACS_SCRIPTS/handoff.py" --run EVAL-1 \
  --summary "quality set, iteration 1: the author was interrupted mid-write -- test-strategy.md is partly written (uncommitted on task/EVAL-1-product-quality-doc-set), coverage-policy.md not started; no review has run. Next: finish the author pass, then review, deliver, finish." \
  > /dev/null
