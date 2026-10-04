# 0046 — No new settings key for e2e CI enforcement

**Status**: Accepted · **Date**: 2026-07-11

## Context

E2E-1 (MAR-125) needed a way to express "this repo's e2e suite is a required
CI merge gate," distinct from "this repo has an e2e suite the local verifier
runs" (`settings.e2e`/`suites.e2e`, already shipped). The question was
whether to introduce a dedicated enable flag (e.g. `e2e.ci: true` /
`suites.e2e.ci: true`) or express enforcement purely through the committed
workflow file plus branch protection, as the existing tests gate already
does (there is no `tests.required` flag).

## Decision

No new settings key. Enforcement is expressed entirely by the committed
`acs-e2e.yml` workflow (a git-visible, PR-reviewed opt-in record) plus the
branch-protection required check — exactly how the tests gate works today.
`suites["e2e"].command` (or the `e2e` alias) stays the single command
source. "e2e runs in the verifier" and "e2e gates merges in CI" are two
**independently** opt-in-able states without any new key: configuring
`settings.e2e` opts into the first; separately accepting `/acs:init` Step 7f
opts into the second.

## Alternatives considered

- **A dedicated additive opt-in flag** (`suites.e2e.ci: true` or `e2e.ci`) —
  *rejected*: a real `settings.schema.json` change, which is also an
  architecture/contract change to record in `lld/contracts.md`, for a flag
  whose only consumer is a human deciding whether to run `/acs:init` Step 7f
  — the tests-gate precedent shows this flag is not load-bearing for any
  code path. A legitimate declarative-vs-convention trade-off, not a
  correctness issue — declined in favor of the minimal, contract-change-free
  option.

## Consequences

- Zero schema change; no risk of violating the rebase-not-redefine
  constraint on `settings.e2e`/`suites.e2e`'s shape.
- "e2e configured" and "e2e gated in CI" are coupled only by convention (does
  the repo have `acs-e2e.yml` committed + required?), not by a single
  declarative flag a script could grep for — an accepted trade-off.
- Nothing new to document in `lld/contracts.md` beyond noting the e2e
  CI-gate artifact family alongside the existing `tests`/`enforcement`
  mentions.
