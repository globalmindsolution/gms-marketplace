# 0045 — Dedicated `acs-e2e.yml` + `run-e2e.py` CI workflow pair

**Status**: Accepted · **Date**: 2026-07-11

## Context

MAR-124 (E2E-1/MAR-125) needed a CI mechanism to turn `settings.e2e`/
`suites["e2e"]` — already the local verifier's opt-in e2e suite — into a
required GitHub Actions merge gate. The existing `acs-tests.yml` +
`run-tests.py` pair already proves the pattern (stdlib-only runner, no acs
install on the CI box, reads the committed `.acs/settings.json`), so the
question was whether e2e reuses that pair, extends it, or gets its own.

## Decision

Ship a dedicated `acs-e2e.yml` + `run-e2e.py` pair, cloned from the
tests-gate shape (job name `E2E suite`; `on: pull_request [opened, reopened,
synchronize]`; `permissions: contents: read`; `concurrency:
cancel-in-progress: true`). `run-e2e.py` resolves the e2e command via
`suites["e2e"]` or the raw `e2e` alias, runs `setup` → `command` → `teardown`
(teardown always, in a `finally`), and exits with `command`'s status. The e2e
required check stays fully **independent** of the tests check — a repo can
gate on one, both, or neither.

## Alternatives considered

- **Extend `acs-tests.yml`/`run-tests.py` to also run e2e** — *rejected*:
  couples the coverage gate and the e2e gate, so a repo wanting
  e2e-without-tests (or vice versa) cannot opt out of one independently; a
  slow e2e run would gate the otherwise-fast tests check.
- **A generalized `run-suite.py --suite <name>` parametrized over
  `settings.suites`** — *deferred, not built*: larger surface than this
  ticket scopes and no second consumer exists yet (YAGNI); noted as a future
  generalization.

## Consequences

- One more template pair to maintain going forward, symmetric to the
  tests-gate precedent it mirrors.
- The e2e required check is independently opt-in-able in CI, matching the
  independently opt-in-able local-verifier behavior `settings.e2e` already
  has.
- E2E-2 (`/acs:standardize-project`, MAR-126) reuses this exact pair verbatim
  for brownfield repos rather than duplicating it.
