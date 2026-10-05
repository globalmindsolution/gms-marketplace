# /acs:create-api-contract — when this is not a first run

Read this when `context.reconcile` or `context.handoff_summary` is set: it
verifies recorded progress against reality and says where to continue. A
first run reads none of it.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Read `steps/create-api-contract/state.json` (`invocations[-1]`, `states`) and
   the artifacts under `steps/create-api-contract/`.
2. Re-resolve `<contract_path>` and read it if it exists; check
   `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" changes diff --name-only`
   for contract-file changes a prior run left in the working tree. Trust
   nothing you cannot see in a file.
3. Continue from the first unfinished phase — a contract-author report
   (`iter-<n>/contract-author.json`) with no contract-reviewer report →
   review it; a contract-reviewer report (`iter-<n>/contract-reviewer.md`)
   with findings and no later contract-author → re-run the contract-author
   with those findings as `<context>`; nothing on disk → iteration 1
   contract-author.
4. The contract-author's authoring notes (`iter-<n>/authoring.md`) belong to
   their iteration, and a resumed run never re-runs an iteration whose
   contract-reviewer report is already on disk.
5. A sliced phase resumes slice by slice: a resumed iteration re-runs ONLY the
   slices whose report is missing — a writer slice without
   `iter-<n>/contract-author-<k>.json`, a reviewer slice without
   `iter-<n>/contract-reviewer-<slice>.md` — spawned together in one message,
   then runs the join. Every writer slice's report on disk but no
   `iter-<n>/contract-author-integration.json` → run the integration pass, then
   the join. Every report on disk but no joined file (`iter-<n>/authoring.md`
   and the draft, or `iter-<n>/contract-reviewer.md`) → run the join alone;
   never re-run a slice whose report is on disk.

If `context.handoff_summary` exists, read it plus
`steps/create-api-contract/handoff-context.md` (when present), do
a light reconcile, and continue from where it points.
