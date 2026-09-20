# /acs:analyze-requirements — when the ticket is not plannable

Open this only once you have concluded that a question genuinely blocks —
that no conventional default could settle it without risking the wrong
build. SKILL.md's "User interaction" carries the rule for making that call,
and it is the rule that decides whether you ever get here: most questions an
analysis raises are assumptions, and an analysis that publishes with
`ready_for_planning: true` and a stated assumption is worth more than one
that stops for an answer nobody is there to give.

**Where the cross-references below point.** "Finish" and the front matter
are SKILL.md's.

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
2. Publish the analysis anyway when it verified — a not-ready analysis is still
   the artifact the answers come back to.
3. Write result.json with `"status": "needs_input"`, `stop_reason` "needs user
   input", `states.ready_for_planning: false`, run the Finish steps, and return
   a `<handoff status="needs_input">` whose `<questions>` carry them.

`/acs:ship` asks the user each question and re-invokes this same skill with the
answers as context; a direct invocation stops with the questions in the
completion report.
