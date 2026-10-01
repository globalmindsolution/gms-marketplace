# /acs:analyze-requirements — when the ticket is not plannable

Open this only once a question genuinely blocks. There are two ways to get
here, both decided in SKILL.md's Stage 2:

- **The user is reachable** and a question is still open after the grouped
  ask and its ONE follow-up round — the user was asked twice and the answer
  that would settle it has not come.
- **The user is not reachable**, and the question is one no conventional
  default could settle without risking the wrong build (a group-(a) question
  the survey marked as blocking).

Most questions an analysis raises never get here: a reachable user answers
them in the one grouped ask, and with nobody to ask, a conventional default is
an assumption — an analysis that publishes with `ready_for_planning: true` and
a stated assumption is worth more than one that stops for an answer nobody is
there to give. An unanswered refined-criterion or needs_design proposal never
gets here either: it stays an open ledger entry and `/acs:create-impl-plan`
plans against the ticket as written.

**Where the cross-references below point.** "Stage 2", "Stage 3", "Finish" and
the front matter are SKILL.md's.

### Not ready for planning → `interrupted` / `needs_input`

When the analysis cannot honestly say the ticket is plannable — a question
where every default could build the wrong thing is still open (a
contradiction with the code, a design document or an ADR; a behaviour the
acceptance criteria depend on that nothing defines; a fork in scope), the
ticket contradicts the design or the requirements, or the problem itself is
undefined — set front-matter `ready_for_planning: false`, say exactly what is
missing in `## Verdict`, and finish `interrupted` with
`stop_reason: needs_input`:

1. Record every outgoing question as `open` (`clarify.py add` without
   `--answer`).
2. Report Stage 2 with `acs.py analysis record-clarify --blocking-open`, and
   follow the controller through Stage 3 anyway — the draft pass writes the
   analysis with `ready_for_planning: false` (the `draft` action carries the
   reason as `not_ready`) and the open questions in `## Questions`, and the
   `publish` action publishes it once it passed the impact review: a
   not-ready analysis is still the artifact the answers come back to, and
   the next run's survey starts from it. The loop then ends `blocked` with
   `kind: "needs_input"` instead of `completed`; no iteration is spent on the
   question itself.
3. Write result.json with `"status": "interrupted"`,
   `"stop_reason": "needs_input"` and `states.ready_for_planning: false`, run
   the Finish steps, and return a `<handoff status="needs_input">` whose
   `<questions>` carry them. `needs_input` is a STOP REASON, never a status:
   the post-hook admits only `completed | failed | interrupted` (plus
   `in_progress`, which does not finalize) and refuses anything else.

`/acs:ship` asks the user each question and re-invokes this same skill with the
answers as context — the re-run plans a fresh loop (`acs.py analysis next`
answers `plan` once the needs_input invocation is finished), its survey
starts from the published analysis, its ledger check finds the answers
recorded and its Stage 2 asks nothing already answered; a direct invocation stops with the
questions in the completion report.
