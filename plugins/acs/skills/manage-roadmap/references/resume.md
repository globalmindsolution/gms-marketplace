# /acs:manage-roadmap — resuming an interrupted run

Open this when `context.reconcile` is true, or when `context.handoff_summary`
exists. A run that starts fresh and finishes in one session reads none of it.

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Re-read `steps/manage-roadmap/iter-*/*-message.xml`, the role reports
   (`iter-1/surveyor.json`, `iter-<n>/author.json`, `iter-<n>/reviewer.md`,
   `iter-<n>/floor.md`), the notes `iter-<n>/authoring.md` and
   `steps/manage-roadmap/version-before.json` — once written it is never
   rewritten, so a resume compares against the run's true start.
2. Re-read `<roadmap>`: does it match what the last author result claims?
3. Pick up at the first missing role: no `iter-1/authoring.md` → survey; a
   survey whose open questions the ledger does not yet answer → ask them (User
   interaction); an author result with no status refresh, version step or
   review → run those; a review with findings and no later author result →
   author with those findings as `<context>`. A resume never re-runs the
   surveyor once its notes exist.
4. A `status` run has no agents: re-run `acs.py roadmap status --write` —
   it is idempotent — and go to Finish.
5. If the last review passed, skip straight to Delivery and Finish.

If `context.handoff_summary` exists, read it (and
`steps/manage-roadmap/handoff-context.md` if present), do a light reconcile of
the same checks, and continue from where it points.
