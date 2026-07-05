# 0042 — Dynamic mid-flight lane correctness

**Status**: Accepted · **Date**: 2026-07-05

## Context

`/acs:code` ships an in-loop, upward-only escalation mechanism (MAR-57):
a ticket whose create-time `size`/`stakes` under-estimate its real
implementation surface can be raised to a higher lane mid-flight. Two of its
guarantees were still implicit riders rather than validated capabilities:
escalation events were logged only as a free-text "coordinator note in the
run state" (`plugins/acs/skills/code/SKILL.md:187-188`, prior text) — no
schema field, no defined shape, no location contract, so "0 silent lane
changes" was unverifiable; and the signal set that triggers escalation mixed
one deterministic path (glob match) with two judgment paths (verifier-finding
text, explicit request) with no normative line drawn on which is
unit-testable.

This decision record covers the **D1** (durable escalation-event audit
trail) and **D2** (frozen three-trigger signal set) portions of the parent
epic's design (MAR-105). It does not cover the epic's D3 (user-confirmed
de-escalation), D4 (`verify_depth` re-selection hardening), or D5 (metrics
surface) — those land as later, additive decisions in this same file.

## Decision

### D1 — Escalation-event audit trail

Escalation events are appended to an additive `escalations` array on the
current `/code` run's entry in `code-state.json`
(`runs[-1].escalations: [{...}]`), written by a new `acs_lib.py` helper,
`record_escalation_event(tdir, skill, event)`. Each event is a fixed
13-field dict: `ts, from_lane, to_lane, from_size, from_stakes, to_size,
to_stakes, trigger, source, ceiling_before, ceiling_after, direction,
confirmation_ref`. Every automatic (upward) event has `direction: "up"` and
`confirmation_ref: null`. Step (f) of the on-trigger escalation sequence
(`code/SKILL.md`) now calls this helper, strictly **after** the
`save_ticket`/`update_pipeline`/`update_index` persistence and the ceiling
raise — never before or interleaved — so an audit-write failure is
detectable (a lane change with no matching event is itself the signal).

**Alternatives considered:**
- A dedicated per-partition `escalation-log.json` (new schema, writer,
  reader, lock surface) — rejected: disproportionate for events that
  originate in exactly one skill, and diverges from this repo's
  additive-to-existing-files discipline (MAR-56 added fields to existing
  files, not a new one).
- Mirroring events onto `pipeline-state.json` — rejected: that file's
  `update_pipeline` overwrites `lane` (a latest-value store, not an append
  log); bolting an event list onto it would give the file two inconsistent
  writer contracts.

### D2 — Frozen three-trigger signal set, glob-only deterministic spine

The signal set is normatively frozen at exactly the three shipped triggers:
(a) a verifier finding signaling higher stakes/size, (b) a
`high_stakes_paths` glob match via `recommend_stakes(changed_paths,
settings)`, and (c) an explicit user/agent escalation request. Trigger (b)
is the **sole deterministic, unit-tested** signal (`TestRecommendStakes`).
Triggers (a) and (c) remain coordinator judgment paths, contract-tested as
prose, never unit-tested as pure functions. No new deterministic scope
helper (e.g. a `recommend_size`-style file/spec-count heuristic) is
introduced this release.

**Alternatives considered:**
- Adding a second deterministic signal for scope (a changed-file-count or
  touched-spec-count threshold with its own pure helper) — rejected: ADR
  0030 already rejected LOC-only/proxy routing ("LOC is a proxy, not a
  dimension") as an alternative; a file-count threshold risks the identical
  critique, plus introduces a new arbitrary, user-tunable threshold with no
  principled default.

## Consequences

- `code-state.json` run entries gain an optional `escalations` array; the
  schema (`skill-state.schema.json`) already permits this via
  `additionalProperties: true` on run-entry items — no schema file edit was
  required. Old `code-state.json` files without the key remain valid.
- The seven existing lane/axis helpers (`derive_lane`, `verify_depth`,
  `VERIFY_ITERATION_CAP`, `lane_rank`, `escalate_lane`, `guard_axes`,
  `recommend_stakes`) are unchanged; `record_escalation_event` is a pure
  I/O append, not a re-implementation of any routing logic.
- "Larger scope" (as distinct from higher stakes) has no deterministic
  signal this release — a fast-lane ticket whose file/spec count balloons
  without touching a `high_stakes_paths` glob relies purely on judgment
  (triggers (a)/(c)).
- Any future deterministic scope signal requires a new PRD/design decision,
  not a silent addition inside this or a later escalation ticket.
