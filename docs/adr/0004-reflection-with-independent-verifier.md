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
