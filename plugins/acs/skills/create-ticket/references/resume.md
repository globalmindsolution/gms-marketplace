# /acs:create-ticket — resuming, and handing off under context pressure

Open this when `context.reconcile` is true or `context.handoff_summary`
exists, and again when your context runs low mid-run. Steps 1-5 and Finish
are SKILL.md's.

**Resume & reconcile.**

- If `context.reconcile` is true: verify recorded progress against reality BEFORE
  continuing — re-read `<partition>/ticket.json`, the
  `steps/create-ticket/iter-*/` drafts (`draft.json`, `draft.md`), the
  `iter-*/<role>-message.xml` snapshots and `reviewer.md` reports, and any
  `iter-*/materialize.json`. Continue from the first unfinished phase: a draft with
  no review → review it; a review with findings and no later draft → run the author
  with those findings; a reviewed draft never confirmed → Step 2. Do not redo work
  that verifiably holds.
- If `context.handoff_summary` exists: read it, do a light reconcile (trust it but
  cheaply re-check the artifacts it names), and continue from where it points. Also
  read `steps/create-ticket/handoff-context.md` if present.

**Context pressure.**

If your context is running low mid-run: flush in-flight work and soft context
(user answers, confirmed decisions, the current draft's iteration, gotchas) to
`steps/create-ticket/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next / decisions>"
```

Tell the user the exact `continue_with` command it prints, then stop.
