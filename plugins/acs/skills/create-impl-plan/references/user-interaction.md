# User interaction — open proposals, the split answer, and no one to ask

Read this when the analysis left ledger entries `open`, when the planner's
notes carry the oversize question, or when you cannot reach the user.

**Entries the analysis left open are proposals, not blockers.**
The analysis README's front matter `ready_for_planning: true` is
`/acs:analyze-requirements`'s verdict that the ticket can be planned as written;
the ledger entries it recorded and left `open` alongside that verdict —
refined-criteria rewrites, missing-criterion suggestions, a design
recommendation — are for the user to take or leave, and that skill's own
contract is that with no answer this skill plans against the requirements as
written. So never re-ask them and never return `needs_input` for them: plan
against the requirements' acceptance criteria as written, name each such entry in
the plan's Risks section as `C-<n> open — planned as written`, and pass them
to the plan reviewer in `<context>` so the plan is judged against the requirements, not
the proposal. The 2026-09-14 measurement lost a run to the alternative: a
completed analysis with two open proposals, a plan run that asked instead of
planning, and no one to answer. What you ask about is what your own survey
finds genuinely ambiguous (SKILL.md's User interaction), the oversize question, and
nothing else.

**Split-answer termination (ADR 0069).** When the planner's authoring notes carry
the open oversize question, record the user's answer with `clarify.py add`,
the same as any other question above. On "accept one large PR": continue
planning against the current decomposition — nothing else changes. On
"split": the run ends in an orderly way — run the mandatory Finish steps
below first (so `acs step finish` closes the run entry like any
other terminal run), writing
`steps/create-impl-plan/result.json` with `status: "failed"` and
`summary` "user chose to split; restructure required before
implementation", and only then return `<handoff status="failed">` whose
`<next-step>` reads `/acs:create-ticket split <id> per
steps/create-impl-plan/plan.md` — it is the handoff element's own
`status` attribute, not only `result.json`'s field, that must read `failed`.
The `<summary>` (≤1 KB) must also restate the split instruction in prose, not
only `<next-step>`: under `/acs:ship` the failed branch surfaces `<summary>`
verbatim and prints only generic resume commands, without promising to
surface `<next-step>`. No new XML element and no new status value —
the SubagentStop hook's message check already admits `failed` and `<next-step>`.

If you genuinely cannot reach the user (a non-interactive run): do not guess.
Record the outgoing questions as `open` (`clarify.py add` without `--answer`),
write the result document with `"status": "interrupted"` and
`"stop_reason": "needs_input"` (`needs_input` is a stop reason, not a status —
the post-hook refuses any status but `completed | failed | interrupted`), run
the Finish steps, and return a `<handoff status="needs_input">` whose
`<questions>` carry them.
