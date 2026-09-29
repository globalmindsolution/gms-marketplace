#!/usr/bin/env bash
# `/acs:create-docs all` where only one set is eligible. The repo already
# ships the quality set and the principles set (their sentinels are on disk),
# and the operations set is in flight on its own delivery ticket, EVAL-1:
# started through the plugin's own `acs.py step start --doc-set operations
# --allocate`, then handed off through handoff.py (lock released, ticket still
# in_progress). fanout_batches therefore leaves exactly [["standards"]], whose
# one extra upstream read -- the principles set -- is present. A local bare
# repository stands in for GitHub.
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
mkdir -p docs/quality docs/principles
cat > docs/quality/test-strategy.md <<'MD'
# Test strategy

## Testing philosophy

Unit tests first, with pytest.

## Coverage policy

See coverage-policy.md.

## Suite inventory

- unit: `python3 -m pytest` over `tests/`.

## CI gates

- pytest with `--cov-fail-under=90` on every PR.

## Flaky-test policy

Quarantine and ticket a flaky test the same day.
MD
cat > docs/quality/coverage-policy.md <<'MD'
# Coverage policy

## Target and hard-fail rule

At least 90% line coverage; below it the pipeline fails.

## Exclusions

None.

## Measurement per stack

pytest-cov, `--cov=src`.

## Escalation

A PR below target is not merged.
MD
cat > docs/principles/principles.md <<'MD'
# Engineering principles

## Principles

1. **Fail loudly on bad input.** A function given an invalid argument raises
   `ValueError` naming the argument; it never guesses or clamps silently.
2. **Standard library first.**

## Rationale

1. A silent clamp hides a caller's bug until it reaches a customer.
2. Every dependency is an upgrade and supply-chain cost.
MD
git add -A && git commit -qm "Quality and principles doc sets"
acs_local_origin
python3 "$ACS_SCRIPTS/acs.py" step start --step create-docs --doc-set operations --allocate \
  > /dev/null 2>&1
python3 "$ACS_SCRIPTS/handoff.py" --run EVAL-1 \
  --summary "operations set: author iteration 1 not started yet; next: branch, then author" \
  > /dev/null
