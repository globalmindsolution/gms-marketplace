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
