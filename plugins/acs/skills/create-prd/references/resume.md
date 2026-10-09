# /acs:create-prd — resuming an interrupted run

Open this when `context.reconcile` is true, or when `context.handoff_summary`
exists. A run that starts fresh and finishes in one session reads none of it.
Versions, Delivery, Finish and User interaction are SKILL.md's sections.

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Re-read `steps/create-prd/iter-*/*-message.xml`, the role reports
   (`iter-1/surveyor.json` or, for a sliced survey, `iter-1/surveyor-<id>.json`
   and `iter-1/authoring-<id>.md` per slice; `iter-<n>/author-hub.json` and `iter-<n>/author-feature-<slug>.json` with each
   feature's `steps/create-prd/features/<slug>/notes.md`;
   `iter-<n>/reviewer-<slice>.md` per reviewer slice and the joined
   `iter-<n>/reviewer.md`), the slice plans (`iter-<n>/<role>-slices.json`) and
   `steps/create-prd/state.json` to see which phases completed, and
   `steps/create-prd/versions-before.json` (Versions below) — once written it is
   never rewritten, so a resume compares against the run's true start.
2. Re-read `<repo>/<prd>`, `<repo>/<roadmap>` and every feature PRD under
   `<features_dir>` — does their content match what the recorded author
   results claim?
3. Continue from the first unfinished phase. If the reviewed docs already pass,
   skip straight to Delivery and Finish.
4. Pick up at the first missing role: no `iter-1/authoring.md` → survey; a
   survey whose open questions the ledger does not yet answer → ask them (User
   interaction); an author result with no review → review it; a review with
   findings and no later author result → author with those findings as
   `<context>`. An author round with a `hub` report and a feature wave missing
   some `author-feature-<slug>.json` re-runs only those features (rule 5). A resume never re-runs the surveyor once its notes exist; the
   authoring notes (`iter-<n>/authoring.md`) belong to their iteration.
5. A sliced phase resumes slice by slice: read its `iter-<n>/<role>-slices.json`
   and re-run ONLY the slices whose own report is missing (a surveyor slice
   without `iter-1/authoring-<id>.md` and `iter-1/surveyor-<id>.json`, a
   reviewer slice without `iter-<n>/reviewer-<id>.md`, a feature author without
   `iter-<n>/author-feature-<slug>.json`), all of them in ONE
   message — and the floor again when `iter-<n>/reviewer-floor.md` is missing — then run the join (`acs.py notes merge`) over EVERY slice file of
   the plan. A slice whose report exists is never re-run; re-joining slice
   files that are all present is idempotent.

If `context.handoff_summary` exists, read it (and
`steps/create-prd/handoff-context.md` if present), do a light reconcile
of the same checks, and continue from where it points.
