# /acs:create-api-contract — when this is not a first run

Read this when `context.reconcile` or `context.handoff_summary` is set: it
verifies recorded progress against reality and says where to continue. A
first run reads none of it.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Read `steps/create-api-contract/state.json` (`invocations[-1]`, `states`) and
   list `steps/create-api-contract/iter-*/*-message.xml` for the last completed
   phase and iteration.
2. Re-resolve `<contract_path>` and read it if it exists; re-read the
   interface documents under `lld/<feature>/api/` the reports name and check
   `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" changes diff --name-only`
   for what a prior run left in the working tree. A file recorded written but
   missing or truncated is not done. Trust nothing you cannot see in a file.
3. Continue from the first unfinished phase — no `iter-1/authoring.md` → the
   survey; a survey with no writer report → the grouped ask, then the write;
   writer reports with no reviewer report → review them; a reviewer report
   (`iter-<n>/contract-reviewer.md`) with findings and no later writer report →
   re-run the writers with those findings as `<context>`.
4. A resumed run never re-runs an iteration whose reviewer report is already
   on disk.
5. A sliced phase resumes slice by slice: re-run ONLY the slices whose own
   report is missing — a gap-analyst slice without `iter-1/gaps-<k>.md`, a
   writer slice without `iter-<n>/contract-author-<k>.json`, a reviewer slice
   without `iter-<n>/contract-reviewer-<slice>.md` — spawned together in one
   message, then run the join. Every writer slice's report on disk but no
   `iter-<n>/contract-author-integration.json` → run the integration pass,
   then the join. Every report on disk but no joined file (`iter-1/gaps.md`,
   the draft, or `iter-<n>/contract-reviewer.md`) → run the join alone; never
   re-run a slice whose report is on disk.

If `context.handoff_summary` exists, read it plus
`steps/create-api-contract/handoff-context.md` (when present), spot-check the
named artifacts, and continue from where it points.
