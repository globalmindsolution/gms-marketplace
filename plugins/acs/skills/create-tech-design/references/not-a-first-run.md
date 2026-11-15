# Not a first run — resume & reconcile

Read when `context.reconcile` or `context.handoff_summary` is set.

- If `context.reconcile` is true (the step's
  previous invocation ended `interrupted` or `failed`; `context.prior_status`
  says which): verify recorded progress against reality BEFORE continuing —
  list `steps/create-tech-design/iter-*/*-message.xml`, re-resolve the design
  artifact (artifact-resolution reference) and re-read the draft and
  `<design_path>` if they exist, and check whether their content actually
  matches the last persisted phase output. Trust nothing you cannot see in a
  file: a design recorded published that is not on disk is not published.
  Continue from the first unfinished
  phase/iteration; never redo work that demonstrably holds, never trust work
  you cannot see in an artifact. A draft that exists is never re-seeded or
  bumped again — its front matter already carries this run's version.
- If `context.handoff_summary` exists: read it plus
  `steps/create-tech-design/handoff-context.md` (when present), do a light
  reconcile (spot-check the named artifacts), and continue from where it points.
- Continue from the first unfinished phase — a designer pass with no
  review → review it; a review with findings and no later designer pass →
  run the designer with those findings as `<context>`. The designer's
  authoring notes (`iter-<n>/authoring.md`) belong to their iteration.
- A sliced phase resumes slice by slice: re-run ONLY the slices whose own
  report is missing — the scope pass without `iter-1/authoring-scope.md`, a
  research slice without `iter-1/authoring-<id>.md` or
  `iter-1/designer-<id>.json`, a draft pass without `iter-1/designer.json`
  (or, after a research pass, `iter-1/authoring-synthesis.md`), a reviewer slice without
  `iter-<n>/reviewer-<id>.md` — in one message, then redo the join
  with `acs.py notes merge`; a joined file is always rebuilt from its slice
  files, never trusted on its own.
- A run that began before ADR-0135 left its state under
  `steps/create-design/` (draft `design.md`, `iter-<n>/design-reviewer*.md`):
  read it as the prior iteration's evidence, then continue under
  `steps/create-tech-design/` — seed the new draft from the old one exactly as
  a re-design is seeded.
