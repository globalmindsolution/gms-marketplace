# /acs:create-impl-plan — when this is not a first run

Open this when the run arrives at a ticket that already carries something:
an interrupted prior run to reconcile against, or a published `plan.md` that
is now wrong. A first run over a ticket with no partition history reads
neither half.

Both halves answer the same question — what already exists on disk, and what
may be done to it — from the two directions a re-run can come from. The
reconcile half trusts nothing it can cheaply re-check; the revocation half
never deletes what an earlier `/acs:code` verdict already cited.

**Where the cross-references below point.** `Publish` and `Finish` are
SKILL.md's sections, and a bare "above" naming one means there.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Read `<partition>/create-impl-plan-state.json` (`runs[-1]` and `states`) and
   the phase artifacts under `steps/create-impl-plan/` to see
   where the prior run stopped.
2. Re-resolve the plan artifact (above) and read it if it exists. Trust
   nothing you cannot see in a file: a plan recorded published that is not on
   disk is not published.
3. Continue from the first unfinished phase (an execute with no verify →
   verify it; a verify with findings and no later execute → execute with
   those findings as `<context>`).
4. There is no plan artifact to reuse: the executor's authoring notes
   (`iter-<n>-authoring.md`) belong to their iteration, and a resumed run
   never re-runs an iteration whose verify is already on disk.

If `context.handoff_summary` exists, read it plus
`steps/create-impl-plan/handoff-context.md` (when present), do a
light reconcile, and continue from where it points.

### Plan revocation

The escape hatch reached when a plan already exists and is wrong — a re-run of
this skill on a planned ticket, including the one `/acs:ship` drives when
`/acs:code` ends with `stop_reason: plan_superseded`.

**Never automatic for a plan nobody challenged.** Revocation is reached only
at an iteration or run boundary — never mid-iteration — and only on a recorded
trigger: an explicit user answer recorded via `clarify.py add`, or a
`/acs:code` run whose result document records `stop_reason: plan_superseded`.
Letting the loop dissolve its own contract without that record is precisely
the rubber-stamp failure ADR 0004 exists to prevent.

1. **Copy before revise, never move.**
   `cp plan.md plan-superseded-<k>.md` inside `steps/code/`,
   `<k>` the smallest positive integer with no existing file. The copy is
   byte-identical, so every `plan.md:<line>` citation already written into an
   earlier `/acs:code` `iter-<n>-verify.md` resolves unchanged against
   `plan-superseded-<k>.md` — the operation is a copy, never a rename or
   move, and the superseded bytes are never deleted.
2. **Revise the draft and re-publish** it over the same `plan_path` (Publish
   above), so the plan the next `/acs:code` reads is the current one.
3. **Any existing `plan-approval.json` is now stale**, and that is the point:
   it records a digest, so the moment the plan's bytes change it stops
   matching, and the `code-standard`/`code-complex` leg that re-runs
   `plan-approval.py` at its next Start writes a fresh record over the new
   digest. The superseded copies are the audit trail. Nothing here re-approves
   — a run that revised a plan must not also bless it.
4. **`plan-superseded-<k>.md` is never an approval input and never a
   conformance contract** — guaranteed by `/acs:code`'s dimension 15
   activation condition that `plan_path` must equal `phases/code/plan.md`.
