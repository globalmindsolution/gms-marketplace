# Resume & reconcile — a run that is not fresh

Read when `context.reconcile` is true or `context.handoff_summary` exists.

- If `context.reconcile` is true (the step's
  previous invocation ended `interrupted` or `failed`; `context.prior_status`
  says which): verify recorded progress against reality
  BEFORE continuing — list `steps/docs-sync/iter-*/*-message.xml`,
  re-read `steps/docs-sync/state.json` if it exists, and check whether
  its `states.files` actually match the working tree
  (`acs.py changes diff --name-only`). Continue from the first unfinished phase/iteration; never redo
  work that demonstrably holds.
- If `context.handoff_summary` exists: read it plus
  `steps/docs-sync/handoff-context.md` (when present), do a
  light reconcile, and continue from where it points.
- There is no plan artifact to reuse: a doc-updater with no drift-reviewer →
  review it; a drift-reviewer with findings and no later doc-updater → the
  doc-updater with those findings as `<context>`. The doc-updater's authoring
  notes (`iter-<n>/authoring.md`) belong to their iteration.
- Both phases run sliced, so a phase can be half-done. A resumed iteration
  re-runs ONLY the slices whose report is missing: a doc area with no
  `iter-<n>/doc-updater-<area>.json` (check the working tree for its doc files
  first — a doc edit already on disk is kept, never redone), an integration pass that was
  due and has no `iter-<n>/doc-updater-integration.json` (run after the
  areas, as always), or a drift-review slice with
  no `iter-<n>/drift-reviewer-<slice>.md` — spawned together in one message.
  In iteration 1 a feature's gap analyst whose `iter-1/gaps-<feature>.md` is
  missing is one of them, re-joined into `iter-1/gaps.md` before the `lld`
  doc-updater runs (`references/lld.md`).
  Then re-join with `acs.py notes merge` before moving on; a joined file with
  a slice report missing beside it is not a finished phase.
- A run that stopped `needs_input` on an approved-drift question
  (`references/lld.md`): read the answers with `clarify.py list`, then
  re-spawn the `lld` doc-updater with them in `<context>` for the same
  iteration and continue with the integration pass and the review.
