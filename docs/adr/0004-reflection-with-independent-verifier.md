# 0004 — Reflection trio; verifier anchors on gated contracts

**Status**: Accepted · **Date**: 2026-06-12, sharpened 2026-06-13

## Context

A model reviewing its own output rubber-stamps. A verifier judging against
the same-iteration plan certifies plan-conformant-but-wrong work.

## Decision

Each hooked skill runs plan → execute → verify with three separate agent
contexts. The verifier anchors on the **gated upstream contracts** (specs,
ticket, design) — never the same-iteration plan (it consumes only the plan's
verifier-checklist section, a floor never a ceiling) and never executor
narratives; it re-runs every cheap check itself. All findings block;
remediation loops are capped at 3 iterations. Every phase writes its own
artifact (`iter-<n>-plan.md` / `-execute.json` / `-verify.md`) — except
`/acs:code`, whose plan artifact is the single per-ticket `plan.md` from
MAR-70 onward (execute/verify artifacts are unaffected) — and, from MAR-71
(slice 1b of MAR-69) onward, whose remediation loop is execute → verify
only: the plan is authored once, before the loop, and iteration-2+ findings
are remediated by the **executor**, not by a new plan; and, from MAR-72
onward, whose plan phase has **no separate agent context at all** on
TRIVIAL/SMALL — the coordinator authors `plan.md` itself (ADR 0074) — while
this ADR's actual subject, verifier independence (the verifier never judges
its own output and anchors on gated upstream contracts as above), is
unchanged in every lane.

## Consequences

A wrong plan is caught (code judged against specs fails; the next plan must
remediate — for `/acs:code`, the next **execute** remediates); resumption
can lose at most the in-flight phase; native plan
mode is unused — planners are headless subagents (ADR context: user approval
has no meaning there).

## Amendment — v0.5.0 (the implementation-pipeline redesign)

This ADR's actual subject — **verifier independence** — is unchanged, and the
last sentence of the Decision already says so. What changed is that the three
contexts are no longer three phases inside one skill.

**plan → execute → verify became three steps.** `/acs:create-impl-plan` authors
the plan (executor + verifier of its own), `/acs:code` executes it, and
`/acs:review-code` reviews the changeset
([0099](0099-review-is-a-step-not-a-phase.md)). `/acs:code` keeps a single
`code-executor` agent; it has no planner and no verifier. The independence this
ADR decided is stronger under that split, not weaker: the reviewer is now a
different *skill* with its own gate, fresh context and its own upstream
contracts, so it cannot see the executor's narrative at all.

**The artifact paths changed.** `iter-<n>-plan.md` / `-execute.json` /
`-verify.md` are gone with the filename-prefix scheme; a phase writes into
`iter-<n>/` under its step
([0096](0096-workflow-is-a-list-not-a-graph.md)). The plan is one file, judged
and approved once, as MAR-70 already had it.

**"unchanged in every lane" now reads "unchanged on every delivery path".**
Lanes were retired by [0095](0095-static-delivery-path-routing.md) and the path
is recorded on the plan by
[0098](0098-delivery-path-recorded-on-the-plan.md); the four `code-*` legs
remain. The "3 iterations" cap is now the `ship.yaml` `loops:` entry
(`from: review-code`, `back_to: code`, `max_iterations: 3`), which is the same
number in a place a consumer can see.
