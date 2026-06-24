# 0029 — merge-pr auto-updates a BEHIND branch then merges in the same run

**Status**: Accepted · **Date**: 2026-06-24

## Context

Today `/acs:merge-pr` treats `mergeStateStatus == BEHIND` as a report-only
readiness failure — the same outcome as any other unmet readiness dimension.
When a required-up-to-date-branch ruleset is active on the repo, an approved,
green PR repeatedly fails to land purely because its base advanced between the
review and the merge attempt. This forces a manual `gh pr update-branch` +
re-invoke cycle, the exact friction MAR-47 is chartered to remove.

The decision space has three orthogonal axes.

## Decision

**Axis 1 — Update method:** merge-update via `gh pr update-branch <number>`
(CHOSEN; no `--rebase`, no force-push) vs rebase+force-push (REJECTED: force-push
violates the safety spine; with a squash-merge default the linear-history benefit
of rebase is moot).

**Axis 2 — Trigger condition:** only when `mergeStateStatus == BEHIND` and every
other readiness dimension (ci, approvals, conflicts,
protections-other-than-BEHIND) passes (CHOSEN; narrowest carve-out) vs
always-update before every merge attempt (REJECTED: widens the carve-out,
contradicts the narrowness requirement, causes needless CI churn on every merge).

**Axis 3 — Post-update sequencing:** wait-and-merge in the same invocation
(CHOSEN; bounded CI re-poll at 15-second intervals for up to 5 minutes — C-6),
then merge when all required checks pass vs stop-and-report after the update
(REJECTED: reintroduces the two-step manual workflow the ticket is chartered to
eliminate).

### C-detail record

- **C-6** (poll parameters): poll `gh pr checks <number> --required` at
  15-second intervals; total timeout 5 minutes. On timeout → report-only:
  "branch updated but required CI still running after 5 min — re-invoke
  /acs:merge-pr to merge once CI passes".
- **C-7** (readiness verdict): when the auto-update succeeds the protections
  verdict is `"pass (was BEHIND; auto-updated via gh pr update-branch)"`. The
  4-key `states.readiness` shape (`ci`, `approvals`, `conflicts`, `protections`)
  is preserved; no `docs/architecture/lld/contracts.md` change is required.
- **C-8** (re-update cap): if the base advances again mid-poll, re-run
  `gh pr update-branch` and reset the 5-minute clock. Maximum 2 total
  update-branch attempts. After the cap: report-only "base advanced again after
  2 update attempts — re-invoke /acs:merge-pr once the base stabilizes".

### Fallback record (D4)

- **Update-branch conflict:** `gh pr update-branch` exits non-zero with a
  merge conflict. Fall back to report-only: "update-branch conflict — base
  cannot be merged into PR branch cleanly; resolve the conflict and re-invoke
  /acs:merge-pr". Force-resolving a conflict is forbidden.
- **CI poll timeout (5 min elapsed):** fall back to report-only (message above).
  Merging without a CI re-pass after an update is forbidden.

Both fallback outcomes degrade to the pre-MAR-47 report-only baseline — no
regression relative to the prior BEHIND→report-only behaviour.

### No PRD amendment (C-5/D5)

MAR-47 is mechanics-only: it changes what happens in one sub-state
(`mergeStateStatus == BEHIND` while otherwise ready), not who may invoke the
skill or what the readiness gate tests. Ownership and governance are unchanged.
Contrast MAR-42 (who may invoke — an ownership shift that required a PRD Vision
amendment). No PRD amendment is made or required.

### Applies to both paths (C-10)

This carve-out applies to **both** the ticket path and the exempt `--pr` path
(`/acs:merge-pr --pr <PRNUMBER>`), a user-confirmed extension beyond the initial
design scope. The exempt path runs the same four readiness dimensions and the
same BEHIND carve-out with identical C-6/C-8 parameters.

## Consequences

- BEHIND PRs whose only unmet dimension is `mergeStateStatus == BEHIND` land in
  a single `/acs:merge-pr` invocation on the happy path (update-branch → CI
  re-poll → merge).
- A failed CI run after update-branch is caught by the re-poll and never merged
  blind.
- Conflict and CI-timeout degrade to report-only — the pre-MAR-47 baseline. No
  regression.
- The re-update cap (2 attempts) bounds the update-branch loop on a busy base.
- The carve-out is stated at four prose surfaces (SKILL.md safety preamble,
  protections dimension, execute step, exempt-path section) plus
  `docs/requirements/skills.md` (standing behaviour) and this ADR. The contract
  test (spec 03) asserts BEHIND-only narrowness across all surfaces.
- Reversible: revert the four SKILL.md sites and the executor step to restore
  BEHIND→report-only.
