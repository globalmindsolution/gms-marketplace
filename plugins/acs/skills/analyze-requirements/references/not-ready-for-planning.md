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

### Not ready for planning → `needs_input`

When the analysis cannot honestly say the ticket is plannable — a question
where every default could build the wrong thing is still open (a
contradiction with the code, a design document or an ADR; a behaviour the
acceptance criteria depend on that nothing defines; a fork in scope), the
ticket contradicts the design or the requirements, or the problem itself is
undefined — set front-matter `ready_for_planning: false`, say exactly what is
missing in `## Verdict`, and finish as `needs_input`:

1. Record every outgoing question as `open` (`clarify.py add` without
   `--answer`).
2. Run Stage 3 anyway — the draft pass writes the analysis with the open
   questions in `## Questions` — and publish it when it passed the impact
   review: a not-ready analysis is still the artifact the answers come back
   to, and the next run's survey starts from it.
3. Write result.json with `"status": "needs_input"`, `stop_reason` "needs user
   input", `states.ready_for_planning: false`, run the Finish steps, and return
   a `<handoff status="needs_input">` whose `<questions>` carry them.

`/acs:ship` asks the user each question and re-invokes this same skill with the
answers as context — the re-run's ledger check finds them recorded and its
Stage 2 asks nothing already answered; a direct invocation stops with the
questions in the completion report.
