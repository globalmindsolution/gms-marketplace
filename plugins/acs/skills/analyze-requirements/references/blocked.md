# /acs:analyze-requirements — when the gate refuses or the controller says `blocked`

Open this when `step start` exits non-zero, when an epic reaches this step
anyway, or when `acs.py analysis next` — or the `next` a `record-*` verb
prints — returns `action: "blocked"`. A run that never stops reads none of
it.

**Where the cross-references below point.** "Stage 2" is SKILL.md's.

## The gate refused

`pre-analyze-requirements.py` checks only the safety
brakes: a ticket, when the invocation names one, resolves to a live, unlocked
partition and is not an epic — an epic is designed and fanned out, never
analyzed as one ticket. Nothing
upstream is required: no predecessor-completed check exists, because the
pipeline order lives in `workflows/ship.yaml`, not in this gate — this skill
works from the requirements themselves and reads the design and product docs
only when they exist, whether `/acs:ship` invoked it or a user did.

**Epics are refused by the gate.** Every ticket that reaches this step has
`ticket.type != "epic"`. If an epic reaches it anyway (a bypassed or
best-effort pre-gate on some runtime), STOP and surface the same message the
gate would have raised: design the epic with `/acs:create-tech-design <id>`, break
it down with `/acs:breakdown-ticket <id>`, then run `/acs:analyze-requirements` on a child.

## The controller returned `blocked`

Read `kind` and `reason`:

- `machinery` — a `<result>` snapshot is missing or malformed, carries the
  wrong `skill`/`phase`/`iteration`/`slice`, or an artifact the action owes is
  missing. The reason names the file. Re-run ONLY the agent(s) whose evidence
  is missing — once, with the reason quoted in the task — then call the same
  `record` verb again. On a host that does not fire SubagentStop, write the
  `<task>` and `<result>` to the snapshot path yourself before recording.
  Still blocked → finish `failed` with the reason in `errors`.
- `agent_failed` — an agent returned `status="failed"`. Supply what its
  `<error>`s say is missing and re-run it once; otherwise finish `failed`.
- `needs_input` — a question only the user can settle. When an agent
  returned `needs_input`, `retry` is `clarify`: take the questions in
  `reason` through Stage 2 (ledger first, one grouped ask), then
  `record-clarify`; the draft pass then re-runs on the SAME iteration. If the
  question cannot be settled, record it with `record-clarify --blocking-open`
  and open `references/not-ready-for-planning.md`. After a `--blocking-open`
  run the loop still drafts, reviews and publishes the not-ready analysis,
  and ends `blocked` with `kind: "needs_input"` and `retry: null` — finish
  `interrupted` with `stop_reason: "needs_input"`.
