# 0040 — CODEOWNERS-derived PR reviewers (not a settings key)

**Status**: Accepted · **Date**: 2026-07-05

## Context

`/acs:create-pr` never requested PR reviewers; `docs/requirements/skills.md`
recorded this as an open `[ASSUMPTION]` ("reviewers are left to repo
conventions"). This ticket's design (clarification **C-4**) needed to settle
the reviewer-source mechanism, with the solo-author/self-review-impossible
case handled as first-class — this repo is solo-authored and has no
CODEOWNERS file, so the graceful-skip path is the one actually exercised
live.

## Decision

Reviewers are resolved via a new stdlib-only CODEOWNERS parser
(`plugins/acs/hooks/scripts/codeowners.py`), rather than a settings key. The
parser finds the repo's CODEOWNERS file (git's own precedence order:
`.github/CODEOWNERS`, `docs/CODEOWNERS`, `CODEOWNERS`), matches the PR's
changed files against the pattern rules using **last-match-wins** (git's own
CODEOWNERS semantics, not most-specific), and unions the matched owners.
`/acs:create-pr` drops the PR author from that set and requests the
remainder via `gh pr edit --add-reviewer` (both `@user` and `@org/team`
tokens pass through unchanged to the same call). When the resulting set is
empty — no CODEOWNERS file, no pattern matched, or every match was the
author — the reviewer request is skipped entirely with one `info`-severity
finding naming the exact reason; `--add-reviewer` is never called on an
empty set, and the PR is never failed.

## Alternatives considered

- **A new settings key `tracker.github.reviewers`.** An array of GitHub
  logins/team slugs, cascade-resolved local→project→user, requested verbatim
  (minus the author) on every PR. Zero new deterministic-layer surface and
  fully deterministic without any repo file, but reviewers are static per
  repo, not per changed path — it cannot route "who owns this subsystem" the
  way CODEOWNERS can, and it adds a permanent settings-surface increase for
  every consumer repo for a value most repos would leave empty. On this repo
  it degrades to the identical graceful-skip outcome the accepted option
  also produces, so it buys nothing here.
- **Hybrid: settings-key override, else CODEOWNERS-derived.** Best
  theoretical coverage, but pays the CODEOWNERS parser's full cost while
  also paying the settings-key option's settings-surface cost, for no
  repo-observable benefit over the CODEOWNERS-only option alone. Over-built
  for a completion ticket.

## Consequences

- A new deterministic-layer component, `codeowners.py`, is added: stdlib-only
  Python >= 3.9, no `acs_lib` import (pure parse+match, no workspace
  read/write, no lock), gated by a `cov_*` unit-coverage harness
  (`tests/acs/cov_codeowners.py`).
- No new settings key is added; `plugins/acs/schemas/settings.schema.json` is
  unchanged.
- The parser's happy path (owners actually resolved and requested) is
  unexercised on this dogfood repo (no CODEOWNERS file here) — validated by
  unit fixtures only; the graceful-skip path is the one this repo runs live,
  identical in shape to the existing AC-6 fallback pattern.
- A future settings-key override remains a non-foreclosed additive extension
  if a consumer repo needs one; it is not built by this ticket.
