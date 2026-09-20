# /acs:analyze-requirements — resuming an interrupted run

Open this when `context.reconcile` is true, or when `context.handoff_summary`
is set. A run that starts fresh and finishes in one session reads none of it.

**Where the cross-references below point.** "Branch" and the phases are
SKILL.md's sections.

## Resume & reconcile

If `context.reconcile` is true (prior run `in_progress`/`failed`/`interrupted`/
`handed_off`), verify recorded progress against reality BEFORE continuing:

1. Read `<partition>/analyze-requirements-state.json` (`runs[-1]` and `states`) and
   the phase artifacts under `steps/analyze-requirements/` to see where
   the prior run stopped.
2. Re-resolve the analysis artifact (above) and read it if it exists. Trust
   nothing you cannot see in a file: an analysis recorded published that is not
   on disk is not published.
3. Read the clarification ledger (`clarify.py list --ticket <id>`): questions
   the prior run asked are already recorded, and answers that arrived since are
   the point of the resume.
4. Continue from the first unfinished phase — an execute with no verify →
   verify it; a verify with findings and no later execute → execute with
   those findings as `<context>`; nothing on disk → iteration 1 execute.
5. There is no plan artifact to reuse: the executor's authoring notes
   (`iter-<n>-authoring.md`) belong to their iteration, and a resumed run
   never re-runs an iteration whose verify is already on disk.

If `context.handoff_summary` exists, read it plus
`steps/analyze-requirements/handoff-context.md` (when present), do a
light reconcile, and continue from where it points.
