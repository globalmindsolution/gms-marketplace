# 0052 — Release cuts land via an exempt `release/*` PR that stops for a mandatory human merge

**Status**: Accepted · **Date**: 2026-07-12

## Context

A release cut tags and publishes an outward-facing GitHub release, reaching
every pinned and rolling consumer of the plugin — hard to cleanly un-publish
once it ships. The task's binding Security NFR mandates a human checkpoint
before that irreversible step.

## Decision

**Option A — open the exempt `release/*` PR and STOP for human merge.** The
skill produces the branch + edits (CHANGELOG section, both manifest
versions, `source.ref`) and opens the PR — already exempt from the
conventions gate via `enforcement.exempt_branches`
(`settings.schema.json:210`) — then stops. The human reviews and merges; the
existing `release.yml` CI job (`permissions: contents: write`) tags and
publishes, reused unchanged. The skill never runs `git tag` or `gh release
create` itself, never force-pushes, and never pushes directly to `main`.
Auth via `gh` only; no new secret settings key. Mirrors `/acs:ship`
deliberately stopping at `/acs:create-pr` so a human sees the change before
the irreversible step.

## Alternatives considered

- **Option B — the skill merges directly / auto-publishes.** *Rejected
  outright*, not weighed as a live trade-off: tagging + publishing a GitHub
  release is outward-facing and hard to reverse for every pinned + rolling
  consumer; auto-publish would remove the one human checkpoint every other
  apply-work skill in this pipeline preserves, and would collide with this
  repo's own solo-author self-approval reality that prior cuts have already
  had to work around.

## Consequences

- The human-merge gate is the sole checkpoint before the irreversible
  publish step; `release.yml`'s own idempotent tag-exists guard is a second,
  independent brake against a re-push after an already-tagged version.
- The privileged tag+publish step stays exclusively inside CI, never runs on
  a developer machine.
