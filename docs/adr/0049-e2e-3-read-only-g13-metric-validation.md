# 0049 — Read-only G13 e2e-integrity metric validation, no metrics_aggregate.py panel

**Status**: Accepted · **Date**: 2026-07-12

## Context

E2E-3 (MAR-127), the final child of epic MAR-124, needed to decide how PRD
G13's two sub-metrics — "0 PRs merged with a red e2e suite while the gate is
enabled" and "100% of user-facing-surface specs declare e2e impact" — get
measured on the dogfood repo: build a standing mechanism, or read what
`/acs:merge-pr` and `/acs:code` already produce.

## Decision

**E1 — read-only validation from existing artifacts.** Sub-metric (a) is
read from every merged ticket's `merge-pr` `result.json`
`states.readiness.ci`, cross-checked against whether `"E2E suite"` is a
required context in `gh api
repos/<owner>/<repo>/branches/<default_branch>/protection --jq
.required_status_checks.contexts` (the gate-enabled signal). Sub-metric (b)
is read from merged tickets' `spec.md` Test-plan sections plus the
code-verifier's **existing, unchanged** e2e-impact dimension. No new
recorded signal, no new code — the same discipline that first validated
G1/G9/G11 by an observed live run rather than a standing dashboard number.

## Alternatives considered

- **E2 — add a read-only e2e-integrity panel to `metrics_aggregate.py`.**
  *Rejected*: new code for a ticket that explicitly frames itself as
  "measurement, not a new mechanism"; no second consumer of the panel
  exists yet. Noted as optional future work, not built by this epic.

## Consequences

- Not a standing dashboard number — someone re-runs the read-only procedure
  each release (see [testing-strategy.md](../quality/testing-strategy.md)'s
  "G13 e2e-integrity validation" section).
- Sub-metric (a)'s first recorded result carries an honest caveat: the gate
  is configured but **not yet wired** as a required check on this dogfood
  repo (no `.github/workflows/acs-e2e.yml`, no `.acs/ci/run-e2e.py`, and
  branch protection's required contexts do not include `"E2E suite"`), so
  "0 red-e2e merges while gated" holds vacuously this release; non-vacuous
  measurement is deferred to the release that wires the gate.

## Amendment — v0.5.0 (the implementation-pipeline redesign)

E1 stands as a **read-only** validation from existing artifacts, and E2 stays
rejected. One of the two artifacts it reads from has a different name.

Sub-metric (a) is unchanged: `merge-pr`'s `result.json` `states.readiness.ci`,
cross-checked against the branch protection's required contexts.

Sub-metric (b) read "merged tickets' `spec.md` Test-plan sections plus the
code-verifier's existing, unchanged e2e-impact dimension". `spec.md` is gone
with spec authoring
([0066](0066-fold-spec-authoring-into-code-ticket-json-fixed-point.md)) — the
test plan lives in `test-cases.md` and the plan's own `## Contract` block — and
the `code-verifier` agent is gone with the review's move to `/acs:review-code`
([0099](0099-review-is-a-step-not-a-phase.md)), where e2e impact is judged by
lens A against `test-cases.md` and the plan. The reading is still read-only and
still adds no recorded signal, which is the decision this ADR made.
