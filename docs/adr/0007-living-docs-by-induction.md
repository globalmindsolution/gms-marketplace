# 0007 — Living architecture & requirements by induction

**Status**: Accepted · **Date**: 2026-06-13

## Context

Standing docs rot when updating them is a separate activity; per-ticket
specs are archived change-deltas, so no file states the product's current
behavior.

## Decision

Two doc sets stay current by induction, not by chore: the **architecture**
set (`architecture_path`) and the **living requirements**
(`requirements_path`, one file per feature area). Base case: bootstrapped
verified against PRD and codebase (architecture) / grown from ticket #1
(requirements). Inductive step: every changeset carries its doc delta, and
the code-verifier makes a positive, evidenced impact determination — impact
without a matching doc change in the same diff is a blocking finding.
Out-of-band drift is repaired boy-scout style (area-scoped) by the design
and code planners; widespread drift triggers a /create-architecture re-run.

## Consequences

After every merge the docs match the code; behavior-defining clarifications
graduate from the workspace ledger into the durable contract; doc updates
are reviewable parts of each PR rather than batch rewrites.

## Amendment — MAR-65

**Date**: 2026-06-28 · **Status**: Accepted (extended)

### Extended scope

The induction loop is extended to include FACTUAL claims in
`docs/product/prd.md` and `docs/product/roadmap.md`. Factual content is
reconciled by the executor as part of the change (same diff), not as a
follow-up. The code-planner assesses factual impact during planning; the
executor reconciles stale factual claims; the code-verifier enforces this as
part of its Documentation-consistency dimension (see enforcement note below).

**Factual — sync autonomously as part of the change:**
- agent/subagent counts
- feature/epic shipped-vs-planned status
- component topology
- version numbers
- file path references

### Boundary definition (factual vs intent)

Intent content — goals, NFR (non-functional requirement) targets, scope
statements, vision, and requirements rationale — remains exclusively
`/acs:create-prd`-owned. `/acs:code` may flag an intent divergence (in the
result document and PR body) but NEVER rewrites intent content. This boundary
is the normative contract encoded in `plugins/acs/skills/code/SKILL.md`
Execute step 4 and the code-executor agent.

### Divergence rationale

The original ADR-0007 scope (architecture + requirements only) treated PRD
intent as `/acs:create-prd`-owned, which is correct and unchanged. This
amendment extends the loop only to *factual* product-doc content because such
content drifts silently across code changes (demonstrated concretely: commit
`44ec46e` reconciled post-MAR-55 drift in `prd.md` out-of-band). The
extension is bounded by the factual/intent boundary above: intent ownership
does not change. No separate `/acs:create-prd` run is needed because this
change extends pipeline mechanics, not the PRD's goals or requirements.

### Enforcement note

The code-verifier's Documentation-consistency dimension (dimension 11) is
extended to make stale prd.md/roadmap.md factual claims a blocking finding.
An intent contradiction found by the changeset produces an explicit flagged
divergence (not a blocking finding). No factual impact → no-op. This makes
the inductive step enforceable for the prd/roadmap doc set.

## Amendment — MAR-162

**Date**: 2026-07-31 · **Status**: Accepted (extended)

### Narrowed scope

The base Decision's induction invariant (`:17-19`, "every changeset carries
its doc delta … impact without a matching doc change in the same diff is a
blocking finding") narrows "same diff" to "same PR/branch, own gated step,
independently diff-re-deriving." The architecture doc set and the
living-requirements doc-delta no longer have to land in the SAME commit diff
as the code change that motivated them; they must land as an additional
commit on the SAME ticket branch, in the SAME PR/review, added by
`/acs:docs-sync` — a distinct, independently-gated pipeline step that runs
after `/acs:code` (and `/acs:test`, when the post-code test step ran) and
before `/acs:create-pr` — and `docs-sync`'s own planner/executor/verifier
re-derive doc impact from `git diff <default_branch>...HEAD` themselves,
never from a hand-off summary
(`plugins/acs/skills/docs-sync/SKILL.md:65-82`).

### Ownership boundary

- **Architecture doc set** (`architecture_path`: HLD, `lld/flows/` sequence
  diagrams) and **living requirements** (`requirements_path`) — production
  moves from `/acs:code`'s execute step 4 to `/acs:docs-sync`'s executor
  (`docs-sync-executor.md`). The invariant itself (both doc sets stay
  current by induction) is unchanged; only the producing step moves.
- **Functional/non-functional requirements classification rubric** and the
  `.evidence.md` sidecar routing rule now live in `docs-sync-executor.md`'s
  charter, no longer in `code/SKILL.md` step 4 or `code-executor.md`.
- **ADR authoring** (`adr_path`, when set) — accepted decision records are
  now committed by `/acs:docs-sync`'s executor. Because accepted decision
  records are not derivable from `git diff`, `docs-sync`'s input contract
  gains the ticket's binding design as a **sixth input**
  (`docs-sync/SKILL.md:60-76`), so architecture-doc production and ADR
  commits are both design-grounded rather than diff-guessed.
- **MAR-65 product-doc factual reconciliation** (`docs/product/prd.md` /
  `docs/product/roadmap.md` factual staleness) — **explicitly unchanged**:
  it stays inside `/acs:code`'s execute step 4 (retitled "Reconcile
  product-doc facts"), enforced as a blocking finding by
  `code-verifier.md` dimension 11's sub-check (c). MAR-65's obligations
  continue exactly as this file already states them above — this amendment
  does not supersede or narrow the MAR-65 amendment.
- **Boy-scout drift repair** — detection, citation, and scheduling are
  unchanged: the code planner still compares the touched area's docs
  against the current code, cites the disagreement (doc section vs
  `file:line`), and records the item in the plan's `## Documentation map`
  (`code-planner.md`). What changed is only **who performs the repair**, via
  three explicit hops: (1) the code planner flags the item in the plan's
  Documentation map as a Boy-scout drift item; (2) the code executor, which
  reads that plan, copies the item verbatim into the execute report's
  `problems` field instead of repairing it in the TDD loop
  (`code/SKILL.md` execute step 4 and `code-executor.md`'s mirror); (3)
  `/acs:docs-sync` — whose input contract already makes every execute
  report's `problems` field a mandatory input
  (`docs-sync/SKILL.md:60-76`) — performs the repair as an additional
  commit on the same branch/PR. No new input, artifact, settings key, or
  gate was introduced for this routing.

### Divergence rationale

ADR 0007's base problem statement — "Standing docs rot when updating them is
a separate activity" — is a documented, non-hypothetical risk: the MAR-65
amendment above cites commit `44ec46e` as a real out-of-band drift instance
that originally motivated extending the induction loop. This amendment is
therefore a deliberate, acknowledged partial departure from that rationale
for the sake of not making `/acs:docs-sync`'s existence a dead letter —
mitigated, not eliminated, by staying on the same PR/branch and by the
two-layer enforcement net named below.

### Enforcement note

Two-layer safety net:

1. **Primary, blocking layer** — `/acs:docs-sync`'s own verifier
   (`docs-sync-verifier.md`) independently re-derives doc impact from the
   six-input contract (`docs-sync/SKILL.md:60-82`) and blocks: "ALL findings
   block; zero findings = pass" (`docs-sync/SKILL.md:134`).
2. **Secondary, advisory layer** — `code-verifier.md` dimension 11's
   per-commit doc-sync, living-requirements, and architectural-impact
   sub-checks ((a), (b), (d)) are still performed and reported, at
   `severity="info" dimension="documentation"`, but never gate
   `verifier_passed` for those three sub-checks — a second, independent net
   in case `docs-sync`'s verifier misses something. These advisory findings
   surface in both the verify report and `/acs:code`'s result document:
   carried into `result.json`'s `findings` array and named on the
   Completion report's `**Findings**` line, while excluded from
   `review.findings_open` and never affecting `verifier_passed`.

Sub-check (c), the MAR-65 product-doc-consistency check, is OUTSIDE this
two-layer net's scope entirely — it has its own single, unchanged, blocking
enforcement inside `/acs:code`, per the Ownership boundary above.
