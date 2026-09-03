# 0079 — Standardize-project remediation loop is execute → verify only, with a frozen iteration-1 allowlist; ADR-0004 amended

**Status**: Accepted · **Date**: 2026-08-24

## Context

MAR-302 changes `/acs:standardize-project`'s remediation loop from
plan-execute-verify-every-iteration to plan-once-then-execute-verify — the
same decision class ADR-0004's existing (pre-MAR-74) in-sentence text already
records for `/acs:code` (MAR-70/MAR-71/MAR-72), and the class ADR-0077/ADR-0078
already extended to `/acs:docs-sync` (MAR-300) and `/acs:create-project`
(MAR-301). `/acs:standardize-project` is different from those two mechanical
mirrors, though: its verifier enforces additive-only diffs against an
**allowlist the planner itself produces** (`classify_additive_diff` in
`acs_lib.py`, per spec 01 and `SKILL.md`'s Additive-surface contract). Simply
removing the per-iteration planner re-spawn and routing iteration-2/3
verifier findings straight to the executor would risk implicitly widening
what the executor is allowed to touch — a finding naming a path outside the
planner-authored allowlist landing in the executor's context without ever
passing back through that allowlist would undermine the additive-only safety
guarantee (D6) this skill exists to enforce. This is a genuine
plan-conformance-trust risk, not a mechanical mirror of MAR-300/MAR-301, which
is why this ticket required `/acs:create-design` (`needs_design: true`)
rather than proceeding straight to `/acs:code`. Since MAR-74 (ADR-0073),
ADR-0004 is append-only — amendments happen via new ADR files, never in-place
edits.

## Decision

**(a) Plan-once topology.** `/acs:standardize-project`'s remediation loop is
now **execute → verify only**: the plan is authored exactly once per run,
before the loop starts, and iteration-2+ findings from the verifier route
directly to the **executor**'s `<task>` `<context>` — not to a new plan. This
amends ADR-0004's `except /acs:code` remediation-loop carve-out (already
extended to `/acs:docs-sync` by ADR-0077 and to `/acs:create-project` by
ADR-0078) to also name `/acs:standardize-project`. A resumed run reuses the
existing `iter-1-plan.md` and never spawns a second planner (D5).

**(b) Frozen iteration-1 Additive-surface allowlist (D1-A).** The planner
authors the Additive-surface allowlist exactly once, in `iter-1-plan.md`; it
is frozen and authoritative for the whole run. The executor's writable
surface is monotonically non-increasing across iterations 1-3 — it may
shrink (e.g. via a narrowing finding), but it may never grow. The verifier
reads that same literal frozen path every iteration rather than trusting a
per-iteration re-derivation (D3-a — enforced by prose and tests only; zero
new code, zero new state keys).

**(c) Narrow, class-scoped verdict split (D2-c).** This is a **named carve-out
to ADR-0004's "All findings block" clause** (`docs/adr/0004-…md:16`), scoped
explicitly and narrowly:

- `dimension="additive-only"` and `dimension="doc-set-authorship"` findings
  remain **always blocking** — no change, no carve-out touches these two.
- Dimension 4's second clause, "no unplanned extra scaffold file" — the sole
  gate on an `A`-status unplanned file (`acs_lib.py:309-310`), and therefore
  the AC-4 gate itself — remains **always blocking**.
- `dimension="recommended-follow-ups-only"` and
  `dimension="completion-report-shape"` findings remain **always blocking**.
- Only a `dimension="plan-conformance"` finding of the **missing-scaffold /
  under-coverage class** ("the plan's task breakdown expected path or
  category X and it was not scaffolded" — dimension 4's *first* clause only,
  never its second) degrades to `severity="info"` and is surfaced as a
  `recommended_follow_ups` entry — and only when **all four** of these hold,
  fail-closed otherwise (an undetermined case, or an ambiguous finding class,
  stays blocking):
  1. `dimension="plan-conformance"`;
  2. the finding is of the missing-scaffold/under-coverage class, never the
     over-scaffold "unplanned extra scaffold file" class;
  3. the remediation target lies outside the frozen iteration-1 allowlist;
  4. the target is absent from this iteration's `git diff --name-status`
     output — the mechanically decidable discriminator between dimension 4's
     two clauses (an over-scaffold finding always names a path *present* in
     the diff; an under-coverage finding always names one *absent* from it).

  `severity="info"` is the acs-messages schema's existing non-blocking
  severity value — no schema change, no new dimension name.

**(d) Class-scoped executor-refusal conversion.** An executor refusal for an
out-of-frozen-allowlist finding converts to a `recommended_follow_ups` entry
**only** when the underlying verifier finding is of that same degradable
`plan-conformance` missing-scaffold class, judged from the verifier's own
prior `<finding>` — **never** from the executor's self-report. Every other
refusal class — including an over-scaffold `plan-conformance` finding, or any
`additive-only` / `doc-set-authorship` / `recommended-follow-ups-only` /
`completion-report-shape` finding — remains a genuine run failure. This is
explicitly **not** an unconditional conversion; the coordinator's route is a
strict subset of the verifier's own four-condition conjunction above, and
fails closed on any undetermined case.

**(e) Residual ADR-0004 tension, accepted and bounded, not closed.**
ADR-0004 requires the verifier to anchor on gated upstream contracts, never
the same-iteration plan. This verifier's dimension 1 (additive-only) anchors
on the planner-authored allowlist — freezing that plan pre-loop converts it
into an upstream contract for iterations 2-3, exactly as MAR-71/ADR-0077/
ADR-0078 already established for their own plan-once skills. The residual
iteration-1 trust — the allowlist itself is trusted at the moment the
iteration-1 planner writes it, with no independent re-derivation — is an
**accepted, named, bounded** limitation, not a closed one: a future,
mechanically-derived allowlist (computed from the repo's own gap analysis
rather than authored freehand by the planner) is its closure path, tracked as
follow-up rather than in scope here. This freeze **bounds, and does not
close, the trust gap.**

## Explicitly NOT touched

- **The artifact-naming clause stays `/acs:code`-only.** `standardize-project`
  does not rename its plan artifact to `plan.md`; it keeps
  `phases/standardize-project/iter-<n>-plan.md` (`n` always 1, written once,
  never rewritten on a later iteration).
- **ADR-0004's actual subject — verifier independence** for
  `additive-only`/`doc-set-authorship` — is unchanged: the verifier
  re-runs `git diff --name-status` independently every iteration, never
  trusting the executor's self-report.
- **`classify_additive_diff` (`acs_lib.py:294-325`) is untouched** — the
  additive-only diff-status enforcement itself is not this ADR's subject; it
  is independently re-run every iteration exactly as before.
- **ADR-0063's reversal for `audience-style` stands untouched.** ADR-0079
  reuses ADR-0057's carve-out *mechanism* (a `severity="info"` non-blocking
  finding, `0057:40-42,48,75`) but is unmistakably **non-reversing** of
  ADR-0063: ADR-0063 reversed ADR-0057's carve-out because "a
  surfaced-but-ignorable finding does not enforce" a criterion that was
  itself a flaky, subjective register judgment (`0063:16`, `:66-69`). D2-c
  avoids that failure mode because its degradation condition (conditions 1-4
  above) is a **mechanically decidable fact** — the remediation target is
  outside the frozen allowlist and absent from this iteration's diff — never
  a register judgment call. This is why D2-c is safe where a hypothetical
  blanket "plan-conformance is advisory" carve-out would not be.

## Consequences

- ADR-0004 itself is never edited — this ADR amends it via the append-only
  ADR convention (`docs/adr/README.md`: "New ADRs are appended by the
  pipeline with the next sequence number").
- A `/acs:standardize-project` run that needs 2 or 3 iterations spawns
  exactly one planner subagent across the whole run; the iteration cap (max
  3, fixed in every lane — this skill has no lane-conditional planner) is
  unchanged in value, but now counts execute+verify rounds rather than
  plan+execute+verify triads.
- The additive-only guarantee (D6) is unchanged and independently re-verified
  every iteration; the verifier still rejects any `R`, `D`, or
  out-of-allowlist `M` status exactly as today.
- A verifier finding on iteration 2+ that would require touching a path
  outside the iteration-1 allowlist is never silently added to the
  executor's writable surface — it is either degraded to
  `recommended_follow_ups` under the narrow four-condition conjunction above,
  or it fails the run.
- No settings key, schema, state-file shape, or artifact-path change
  (zero-migration): `severity="info"` and the `plan-conformance` dimension
  name both already exist; the plan artifact keeps its `iter-<n>-plan.md`
  name and path.
