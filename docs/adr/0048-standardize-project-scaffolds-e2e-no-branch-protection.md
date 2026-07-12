# 0048 — `/acs:standardize-project` additively scaffolds the e2e gate, never wires branch protection

**Status**: Accepted · **Date**: 2026-07-11

## Context

E2E-1 ships `acs-e2e.yml` + `run-e2e.py` (ADR 0045) and wires them into a
fresh repo via `/acs:init` Step 7f (ADR 0047), but an already-existing repo
that never ran `/acs:init` with e2e configured has no path to adopt the same
gate without hand-authoring the workflow. `/acs:standardize-project`
(MAR-121) is the brownfield audit → additive-scaffold skill that already
scaffolds missing CI/tooling config under a verifier-enforced additive-only
allowlist (`classify_additive_diff`) — E2E-2 had to decide whether and how it
participates in the e2e-gate story.

## Decision

`/acs:standardize-project`'s e2e readiness-tooling audit dimension gains a
concrete scaffold action: when `settings.e2e`/`suites.e2e` is set AND no
`.github/workflows/acs-e2e.yml` exists yet, additively copy E2E-1's committed
`acs-e2e.yml` + `run-e2e.py` templates verbatim into the audited repo,
landing as `A`-status files under the existing additive-only allowlist
categories 1 ("new CI workflow file(s)") and 2 ("…e2e runner scaffold
config") — mirroring how greenfield `/acs:create-project` already scaffolds
CI. When a CI workflow file already occupies
`.github/workflows/acs-e2e.yml`, the additive-only rule forbids overwrite:
the existing file is left untouched and the conflict becomes a
`recommended_follow_ups` entry, never a silent skip or a forced overwrite.
`standardize-project` NEVER wires branch protection itself — the gap is
surfaced as a `recommended_follow_ups` entry pointing at `/acs:init` to
complete the required-check wiring.

## Alternatives considered

- **`/acs:standardize-project` also wires branch protection at the end of
  its run** — *rejected*: branch protection is a repo-config mutation,
  invisible to the independent verifier's `git diff --name-status` check,
  which is this skill's entire safety guarantee (one reviewed PR,
  additive-only, verifier-checked). Adding a mutation the verifier cannot
  gate would break the additive-only / one-PR / independent-verifier
  contract the skill is built on; the only option consistent with that
  contract is the chosen one.

## Consequences

- A repo that runs `/acs:standardize-project` and gets the e2e workflow
  scaffolded still needs a separate `/acs:init` re-run (or a manual admin
  `gh api` step) to make the check a required merge gate — two commands
  instead of one. Mitigated by a `recommended_follow_ups` entry pointing at
  `/acs:init`.
- The e2e scaffold introduces no new settings key and no allowlist-mechanism
  change: `classify_additive_diff` already treats every `A`-status path as
  compliant regardless of allowlist contents, so the two new files need zero
  verifier code change to be covered.
- An existing `.github/workflows/acs-e2e.yml` is never touched by this
  skill, preserving the additive-only guarantee even in the conflict case.
