# 0069 — Oversized-ticket split detection is a two-lever control again

**Status**: Accepted · **Date**: 2026-08-04

## Context

Epic MAR-155's create-spec removal (ADR 0066, MAR-160/161/162) deleted the
old create-spec-planner's "ticket exceeds ~4 specs → stop and split"
detector along with it, and `code-planner.md` migrated only the narrower
Spec-simplicity gate (ADR 0037-0039), which compares decomposition
*alternatives*, not decomposition *size*. The result: oversized-ticket split
detection lost its delivery-lane owner, and
`plugins/acs/skills/create-ticket/SKILL.md`'s split path kept naming the
deleted skill's "escalation" as its trigger — a live code-level reference to
a retired mechanism. PRD G4 ("≥ 80% of story/task PRs ≤ ~400 changed lines")
was left with only `/create-ticket`'s upfront rubric, which fires before any
decomposition exists — an under-estimated ticket could sail through to an
unreviewable PR with no in-pipeline signal.

Two options were weighed: re-implement a hard stop-and-split gate in
`code-planner.md` (restores the second lever, but a false positive halts a
headless `/acs:ship` run mid-flight with the ticket branch already created);
or simply retire the stale reference with no replacement (cheapest, but
downgrades a standing MUST to nothing and removes G4's only in-pipeline
signal).

## Decision

Combine both: rewrite `create-ticket/SKILL.md`'s split path to name `/code`'s
plan artifact as its oversize-evidence source (retiring the "escalation"
framing entirely — the split path is user-invoked), **and** add a
non-blocking, plan-time oversize signal to `code-planner.md`'s charter item
2, reusing the Spec-simplicity gate's proven "surface as a `<question>`,
never block, continue planning" contract and `create-ticket-planner.md`'s
existing reviewable-diff rubric (~4 tasks, ~400 changed lines, ~7 acceptance
criteria) as the threshold — no new settings key.

Oversized-ticket split detection is therefore a **two-lever control** again:

1. **Lever 1** — `/create-ticket`'s upfront PR-size rubric, before any
   decomposition exists.
2. **Lever 2** — `code-planner.md`'s plan-time oversize signal, once the
   actual decomposition is known, surfaced through the existing
   clarification ledger and never halting the run.

The signal only ever *surfaces* a question. What may end the run is the
user's own answer: on "split", `/code` writes `result.json` and the returned
`<handoff>`'s own `status` attribute as terminal `"failed"`, runs the
mandatory Finish steps, and returns `<next-step>` pointing at
`/acs:create-ticket split <id>`. On "accept one large PR", planning
continues unchanged. No new XML element, no new status value, no new
settings key.

## Consequences

**Positive**: PRD G4 regains its second, late-stage lever without Option A's
worst-case failure mode (a headless pipeline halted mid-flight with the
branch already created) — a false positive here costs one extra, easily
dismissed question, not a stopped run.

**Accepted cost**: a *correct* split outcome — the user choosing to
restructure — is logged as a terminal `"failed"` status in the run ledger
and the metrics funnel, the same as any other orderly stop `/code` already
records. `needs_input` was considered and rejected: `/ship`'s `needs_input`
branch re-invokes the same step with the answers, which would loop on a
ticket that must first be restructured into an epic.

**No new mechanism**: both additions reuse seams that already exist end to
end — the `<questions>`/clarification-ledger seam (ADR 0038) and the
existing split path (`create-ticket/SKILL.md:56-77`) — so no new subagent,
schema field, or settings key is introduced.
