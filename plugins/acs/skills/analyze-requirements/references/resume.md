# /acs:analyze-requirements — resuming an interrupted run

Open this when `context.reconcile` is true, or when `context.handoff_summary`
is set. A run that starts fresh and finishes in one session reads none of it.

**Where the cross-references below point.** "Branch", "Three stages", the
passes and the phases are SKILL.md's sections.

## Resume & reconcile

If `context.reconcile` is true (the previous
invocation ended `interrupted` or `failed`; `context.prior_status` says
which), verify recorded progress against reality BEFORE continuing:

1. Read `steps/analyze-requirements/state.json` (`invocations[-1]` and `states`) and
   the phase artifacts under `steps/analyze-requirements/` to see where
   the prior run stopped.
2. Re-resolve the analysis artifact (above) and read it if it exists. Trust
   nothing you cannot see in a file: an analysis recorded published that is not
   on disk is not published. A published analysis from an EARLIER run is
   Stage 1's reuse input, not this run's output.
3. Read the clarification ledger (`clarify.py list --ticket <id>`): questions
   the prior run asked are already recorded, and answers that arrived since are
   the point of the resume.
4. Decide which STAGE the prior run reached, from the files alone, asking the
   three questions in order — the first "no" is where you continue:

   | Question | Evidence on disk | If no, continue with |
   |---|---|---|
   | **Survey report present?** | `iter-1/authoring.md` with a `## Questions for the user` section, and its report — `iter-1/analyst-survey.json`, or every `iter-1/analyst-<area>.json` of a sliced survey plus, then, `iter-1/authoring-synthesis.md` and `iter-1/analyst-synthesis.json` | **Stage 1**: the survey pass; for a sliced survey, only the missing slices (below), then the merge, then the synthesis pass if its notes are missing, then the final merge |
   | **Answers recorded?** | every item of the notes' `## Questions for the user` (the `<!-- slice: synthesis -->` block when sliced) has a ledger entry — answered, assumed, or recorded open after the follow-up round — and every confirmed criterion / `needs_design` is in the ticket | **Stage 2**: ledger first, then ONE grouped ask of only the questions with no entry (a follow-up round the prior run already asked is not asked again), then the `ticket save` of any confirmed amendment not yet in the ticket |
   | **Draft present?** | `steps/analyze-requirements/analysis.md` and `iter-<n>/analyst.json` | **Stage 3**: the draft pass for iteration 1 |

   Inside Stage 3, continue from the first unfinished phase — an analyst
   report (`iter-<n>/analyst.json`) with no impact review → run the impact
   reviewer on it; an impact review (`iter-<n>/impact-reviewer.md`) with
   findings and no later analyst report → run the draft pass with those
   findings as `<context>` (through Stage 2 first when a finding is a question
   for the user); a passing review with nothing published → the deterministic
   checks, then Publish.

   A sliced phase resumes slice by slice: re-run ONLY the slices whose report
   is missing — a judge slice with no `iter-<n>/impact-reviewer-<slice>.md`,
   a survey slice with no `iter-1/authoring-<area>.md` — in one message, then
   join with `acs.py notes merge` as SKILL.md's Stage 1 and Parallelism
   sections say. A slice whose report is on disk is never re-run, and the
   joined file is written only once every slice's report exists.
5. There is no plan artifact to reuse: the analyst's authoring notes
   (`iter-<n>/authoring.md`) belong to their iteration, a resumed run never
   re-runs a survey whose notes are on disk, and it never re-runs an iteration
   whose impact review is already on disk.

If `context.handoff_summary` exists, read it plus
`steps/analyze-requirements/handoff-context.md` (when present) — it names the
stage reached — do a light reconcile against the table above, and continue
from where it points.
