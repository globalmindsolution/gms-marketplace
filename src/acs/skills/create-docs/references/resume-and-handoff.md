# /acs:create-docs — interrupted runs: resuming one, and handing one off

Open this when `context.reconcile` is true for a set, when the argument was a
delivery-ticket id, or when your own context is running low mid-run. A fresh
run that completes in one session reads none of it — the two halves are the
same seam from opposite sides: a run that runs low writes the handoff, and the
run that picks it up reconciles against what is actually on disk.

## Resume & reconcile

If `context.reconcile` is true for a set, verify recorded progress against
reality BEFORE continuing:

- Read `<partition>/phases/create-docs/` — the persisted
  `iter-<n>-<phase>.xml` files tell you the last completed phase and iteration.
- Re-read the actual artifacts: which of the set's files under
  `<checkout_root>/<path>/` exist and are complete; whether the ticket branch
  exists (`git branch --list`), is committed, pushed, or already has a PR
  (`gh pr list --head <branch>`).
- Distrust the record where it is cheap to re-check (a doc "written" but
  missing or truncated counts as not done).
- Continue from the first unfinished phase of the recorded iteration: an
  execute with no verify → verify it; a verify with findings and no later
  execute → the next execute, with those findings as `<context>`.

If `context.handoff_summary` exists, read it plus
`<partition>/phases/create-docs/handoff-context.md` (if present), do a light
reconcile (spot-check the claimed artifacts), and continue from where the
summary points.

Re-running `/acs:create-docs` with a set argument simply re-derives the
eligible batch: a set with an open (non-`done`) delivery ticket, or an
already-shipped doc set, is excluded from a **new** batch — it is already
accounted for, either in flight (resume it by ticket id) or done. There is no
fan-out ledger of its own: each set's own `pipeline-state.json`, written under
`flow: "product"` with the step key `create-docs`, is the complete resume
record for that set. `/acs:ship` never drives these — its `flow: "product"`
refusal (`ship/SKILL.md`) stands.

## Context pressure

Your own context carries the slice's phase bookkeeping — bounded by
`max_parallel` sets' worth of prose, which is why the cap exists. If you run
low mid-run: flush in-flight work plus soft context (mode decision, partial
verifier findings, gotchas) for each set to its own
`<partition>/phases/create-docs/handoff-context.md`, then, per set:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints (re-running this skill
with the delivery-ticket id resumes that set via the Per-set Start's resume
form).
