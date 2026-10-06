---
status: "implemented"
version: 1
tickets: []
feature: "acs"
---

# API — Guard-denial audit trail

The record the file-map guard appends on every deny, and the read path and derived key over it.

## Guard-denial audit trail (MAR-578)

`<skill>-state.json` run entries carry an additive, optional `guard_events`
array (`runs[-1].guard_events: [{...}]`), appended by `record_guard_event(tdir,
skill, event)` (`acs_lib/step.py`) — creates the list when absent, persists via
the same pretty-printed `write_json`. The state file is the denied writer's
step's own (`code-state.json` is the common case, not the only one): the guard
records under the skill of the active `write`-kind agent, and the derivation
below is skill-agnostic.
It returns `False` instead of raising when there is no run entry to carry the
event — its sole caller is a deny path whose verdict must not depend on the
recording. (Its retired sibling `record_escalation_event` raised there, which
was right for an audit write whose absence was itself the signal that a lane
change went unrecorded; this recorder has the opposite obligation.)

Each event is a fixed 7-field dict: `ts, skill, iteration, tool, target, reason,
declared_count` — `iteration` is a **string** (the highest declared file-map
iteration); `target` is repo-relative when the denied path sits under
`checkout_root`, else as given, and `null` for `unreadable_payload`, where no
path is nameable; `reason` is `"outside_map"`, `"control_input"`, or
`"unreadable_payload"`; `declared_count` is the declared union's size for
`outside_map` and `0` for the other two.

Two bounds hold at every deny site. An event is recorded **only on a deny** —
every fail-open branch (not a write tool, no partition, no active write-kind agent)
records nothing — and recording **never changes the verdict**: a failed append
is one extra stderr note beside the unchanged warning, with no retry, wait or
lock. The item shape **is** declared in
`plugins/acs/schemas/skill-state.schema.json` — the retired `escalations` array
never was; run-entry items already declare
`additionalProperties: true`, so that declaration documents the entry rather
than tightening what a run entry may carry.

Read path: `acs.py guard events --ticket <id> [--skill code]` prints one
pretty-printed object, `{ok, ticket_id, skill, count, events, path}`, with
`events` in the order they were denied; it exits non-zero with a message when
the partition or that skill's state file is absent. Derived surface:
`states.review.guard_denials` = `len(runs[-1].guard_events)`, computed by
`post-<skill>.py` through `acs_lib/derive.py` and **absent, not `0`**, when
nothing was denied — a run that never tripped the guard carries no key rather
than a `0` the reader cannot distinguish from a run predating the trail.
