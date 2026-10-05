# /acs:analyze-requirements — resuming an interrupted run

Open this when `context.reconcile` is true, or when `context.handoff_summary`
is set. A run that starts fresh and finishes in one session reads none of it.

**Where the cross-references below point.** "Working tree", "Three stages", "The
controller loop" and the phases are SKILL.md's sections.

## Resume & reconcile

If `context.reconcile` is true (the previous invocation ended `interrupted` or
`failed`; `context.prior_status` says which), verify recorded progress against
reality BEFORE continuing. You do NOT work out which stage the prior run
reached: the controller's `loop.json` holds the loop's position, and it was
written from the artifacts, not from a session's memory (ADR-0114).

1. Ask the controller where the loop is:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" analysis next
   ```

   - `plan` — the prior invocation never declared its lanes, or its loop
     ended (`completed` / `failed`) and this invocation starts afresh. Run
     the skill from the survey.
   - `survey`, `synthesize`, `draft` or `review` — that action was handed out
     and never recorded. Re-run ONLY the agents whose evidence is missing —
     a lane or judge slice with no `<result>` snapshot at the path the action
     prints, or no report — in one message; an agent whose snapshot and
     report are on disk is never re-run. Then call the action's `record`
     verb; if anything is still missing, the controller answers `blocked`
     with `kind: "machinery"` and names the file, and no iteration is spent.
   - `clarify`, or `blocked` with `kind: "needs_input"` — the questions are
     the point of the resume: run Stage 2 against the ledger (step 3), then
     `record-clarify`.
   - `publish` — the review passed and nothing is recorded as published: run
     the action's `commands`. `publish` is idempotent: re-publishing the same
     bytes changes nothing in the working tree.
   - `completed` / `failed` — the prior invocation reached the end but did
     not finish the step: go straight to Finish with what `next` reports.

2. Re-resolve the analysis artifact (SKILL.md, "Analysis artifact
   resolution") and read it if it exists — its `README.md` first. Trust nothing you cannot see in a
   file: an analysis recorded published that is not on disk is not published,
   and `record-publication` refuses it. A published analysis from an EARLIER
   run is Stage 1's reuse input, not this run's output.
3. Read the clarification ledger (`clarify.py list`, `--ticket <id>` on a
   ticket run): questions
   the prior run asked are already recorded, and answers that arrived since are
   the point of the resume. Ask, in ONE grouped ask, only the questions with
   no entry (a follow-up round the prior run already asked is not asked
   again), then `acs.py requirements refine` any confirmed refinement (or
   the feature) not yet in the run's `## Refined` requirements.
4. There is no plan artifact to reuse: the authoring notes
   (`iter-<n>/authoring.md`) belong to their iteration, and the controller
   never hands out a survey or a review it has already recorded.

If `context.handoff_summary` exists, read it plus
`steps/analyze-requirements/handoff-context.md` (when present) for the soft
context — answers, settled sections, gotchas — then run `acs.py analysis next`
and continue from the action it prints.
