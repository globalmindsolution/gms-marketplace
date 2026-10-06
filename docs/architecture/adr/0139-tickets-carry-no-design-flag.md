# 0139 — Tickets carry no design flag: a tech design runs when the user asks for one

**Status**: Accepted · **Date**: 2026-10-06

**Amends**: [0008](0008-conditional-steps-as-ticket-data.md) (`needs_design`
leaves the ticket flags that gate a skill; `docs_only` and the rest stand),
[0101](0101-gating-skills-that-are-not-workflow-steps.md) (§3: `create-tech-design`
stays in `SUBJECT_GATES`, but its precondition is no longer a flag on the
ticket), [0128](0128-requirements-from-any-container.md) (a run's requirements
no longer carry `needs_design`, and the gate no longer reads it from them),
[0133](0133-analysis-is-a-folder-by-bounded-context.md) (the analysis
`README.md` front matter loses `needs_design_recommendation`),
[0135](0135-create-tech-design.md) (§1: the "same `needs_design` brake" is gone)
and [0138](0138-breakdown-ticket-and-typed-ticket-authors.md) (children carry no
`needs_design`, a converted ticket is patched to `{"type": "epic"}` only, the
epic author makes no design recommendation, and an epic's Next reads
`/acs:create-tech-design <id>` *when you want a design*).

## Context

`needs_design` is the last classification a ticket still carried. ADR-0008 made
it a declared, user-confirmed flag that gated `/acs:create-design` "from both
sides"; MAR-76 made it epic-only (always `true` on an epic, never offered on a
story, task or bug); ADR-0128 moved the read to the run's requirements, so
`/acs:analyze-requirements` could refine it; ADR-0133 put a
`needs_design_recommendation` in the analysis front matter; ADR-0135 kept it as
`/acs:create-tech-design`'s brake. The other axes it once sat beside — `size`,
`stakes` and the lane derived from them — left tickets with ADR-0095: a change
is classified once, from its plan, as `create-impl-plan`'s `delivery_path`.

The flag no longer decides anything the user does not decide anyway. The user
runs `/acs:create-tech-design` by hand when a change deserves a team-reviewed
design; `ship.yaml` never names it (ADR-0101 §3). So the flag only ever said
*no*: a story the user wanted designed was refused until someone ran
`acs.py requirements refine` with `{"needs_design": true}` to flip it, and an
analysis that recommended `false` had to be overruled the same way. On an epic
it was always `true`, so it said nothing there either. Meanwhile every ticket,
every child minted by `/acs:breakdown-ticket`, every analysis and every refined
requirements file carried it, and the readers that wanted to know whether a
design *exists* asked whether one was *required* instead.

## Decision

1. **A ticket carries no design flag.** `needs_design` leaves
   `ticket.schema.json` and `tickets-index.schema.json` (`required` and
   `properties`), `tickets.new_ticket_doc`, the index entry and `ticket.md`'s
   front-matter order (`artifacts._FRONT_MATTER_ORDER`).
   `new-ticket.py --needs-design` is removed: argparse rejects it (exit 2).
   `/acs:create-ticket` neither asks for it nor confirms it, its epic author
   makes no recommendation, and `/acs:breakdown-ticket`'s children carry none; a
   story or task it converts is patched to `{"type": "epic"}`.
2. **The analysis says nothing about design.** `/acs:analyze-requirements`
   drops `needs_design_recommendation` and every design-significance judgment
   and question — from its survey, its grouped ask, its templates and its Next
   line. Its `README.md` front matter is `ticket` (or `feature`) and
   `ready_for_planning` (plus ADR-0122's version keys on a Discovery analysis).
3. **Requirements carry no design flag.** `needs_design` leaves
   `requirements.REFINE_KEYS`, `requirements.md`'s `## Ticket` and `## Refined`
   blocks, `requirements.summary()` (the step-start `context.requirements` and
   `acs.py requirements show`) and `recorded_needs_design`.
   `acs.py requirements refine` given a `needs_design` key **refuses** with a
   `GateError` naming ADR-0139.
4. **`/acs:create-tech-design` runs when the user asks.** `gate_create_tech_design`
   stays in `SUBJECT_GATES` but loses its brake on the flag: it admits any
   ticket — epic, story, task or bug — a prompt or documents. It still refuses
   an invocation with no requirements at all (no ticket, document or prompt and
   no current run), and whatever resolving the ticket refuses: a ticket with no
   partition, a corrupt `ticket.json`, a done and archived ticket.
   `_refuse_recorded_no_design` is deleted.
5. **A design is found, not required.** `gates.design_requirement` becomes
   `design_source(ctx, tdir, ticket, rdir)`, returning `(exists, dir, source)`:
   the ticket's own tech design when one exists (`source: own`), else its
   parent epic's (`source: parent`), else none. It looks the document up the way
   `acs.py artifacts show design` does — `tech-design.md`, a legacy `design.md`
   still read. The step-start context carries `context.design = {exists, dir,
   source}` for every run, a ticketless one included (its own design folder).
   `/acs:create-impl-plan`, the planner, `/acs:code`, `/acs:create-test-docs`
   and `/acs:review-code` read the tech design when `context.design.exists`, and
   otherwise proceed without one — no advisory, no warning.
6. **The one stale classification line goes.** `create-impl-plan`'s `SKILL.md`
   no longer lists `size` and `stakes` as ticket fields; classification is the
   plan's `delivery_path` (ADR-0095, ADR-0098).

## Consequences

- **Old state still loads.** `additionalProperties` stays `true` on both ticket
  schemas, so a `ticket.json` or index entry that still carries `needs_design`
  validates and the key is ignored. A run whose `requirements-refined.json`
  still holds `needs_design` reads as if it did not. An analysis `README.md`
  published with `needs_design_recommendation` still passes `analysis
  record-draft` and `front_matter_check --require`: unknown front-matter keys
  are ignored, as ADR-0134 made them for `api_surface`.
- **Breaking.** `new-ticket.py --needs-design` exits 2, and `acs.py requirements
  refine` refuses a `needs_design` key. A script that passed either drops it.
  There is nothing to migrate in a workspace.
- **A design is the user's call.** Run `/acs:create-tech-design <id>` (or with a
  prompt or documents) when a change deserves one; nothing asks for it and
  nothing refuses it for want of a flag. An epic's run ends with *Next:
  `/acs:create-tech-design <id>` (when you want a design) →
  `/acs:breakdown-ticket <id>`*. The epic refusal of `/acs:ship` and
  `/acs:code` stands.
- **Readers ask whether a design exists.** A story whose parent epic has a tech
  design gets that design in its plan, as before; a story with neither plans
  without one, silently. `/acs:breakdown-ticket` still warns, never blocks, on
  an epic whose tech design is not `approved` (ADR-0138).
- ADR-0012's touched-area participant (MAR-164) named its population
  "`needs_design: false` tickets"; that population is now every ticket the user
  did not run `/acs:create-tech-design` on. Its four edges are unchanged.
- The `needs_design` routing and behaviour evals, graders and calibration
  fixtures are rephrased or assert the key's absence;
  `tests/acs/test_needs_design_epic_only.py` is deleted, its still-valid cases
  carried to the new truth.
