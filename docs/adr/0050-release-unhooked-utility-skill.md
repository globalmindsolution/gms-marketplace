# 0050 — `/acs:release` ships as an unhooked utility skill, not a 15th hooked apply-work skill

**Status**: Accepted · **Date**: 2026-07-12

## Context

MAR-129 needed a one-command release-cut capability: assemble/verify the
CHANGELOG section, bump both manifests + `source.ref`, and drive the
existing `release.yml` workflow. A release cut is deterministic apply-work,
repo/version-scoped rather than per-ticket, with no natural pipeline
predecessor to gate on.

## Decision

**Option A — new unhooked utility skill `/acs:release <version>`**, a
class-sibling of `/acs:test`/`/acs:metrics`/`/acs:usage`: no `HOOKED_SKILLS`
entry, no `pre-release.py`/`post-release.py` pair, no `GATES["release"]`
entry, and no `release-executor`/`-planner`/`-verifier` agent files — the
coordinator does the work directly, mirroring `plugins/acs/skills/test/SKILL.md`.

## Alternatives considered

- **Option B — new HOOKED apply-work skill (15th hooked skill).** *Rejected*:
  would require inventing a non-pipeline predecessor gate a cut does not
  naturally have (e.g. "release branch clean / manifests-in-sync"), for no
  correctness gain — durable partition/lock/native metrics come free but
  nothing needs them here.
- **Option C — fold into `/acs:merge-pr` or `/acs:create-prd`.** *Rejected*:
  `/acs:merge-pr` is per-ticket PR landing, not repo/version-scoped pre-PR
  work; `/acs:create-prd` owns product docs, not manifests/tags. Either fold
  overloads a stable, well-tested contract with an unrelated responsibility.
- **Option D — producer/triad skill.** *Rejected*: a cut is deterministic
  apply-work — there is nothing for a planner to weigh or a verifier to
  independently re-derive that the release-notes coverage report and the
  human PR reviewer do not already cover; a triad triples cost for no
  correctness gain (G14/G15).

## Consequences

- Skill count 22→23; `UNHOOKED_SKILLS` 8→9; `HOOKED_SKILLS` (14), the 14
  `pre-*.py`/14 `post-*.py` pairs, the 14-entry `GATES` dict, and the
  agent-file count (42 total, 36 reachable) are all unchanged.
- No durable workspace partition/lock/metrics "for free" — the idempotency
  probe (`release_notes.py status`) and the release PR body are the audit
  trail instead; two concurrent cut invocations are not mutually excluded by
  a lock, mitigated by the idempotency probe detecting an already-open
  release branch/PR or an already-cut tag.
