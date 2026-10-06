# 0138 — `/acs:breakdown-ticket` breaks work down, `/acs:create-ticket` drafts through a type author, and `bug` is a ticket type

**Status**: Accepted · **Date**: 2026-10-05

**Amends**: [0069](0069-oversized-ticket-two-lever-split-control.md) (lever 2's
"split" answer now points at `/acs:breakdown-ticket <id>`, not
`/acs:create-ticket split <id>`; both levers stand),
[0075](0075-planning-implementation-pipeline-split-epics-never-implemented.md)
(an epic's children are minted by `/acs:breakdown-ticket <epic-id>`, not
`/acs:create-ticket <epic-id> --fan-out`; epics are still never implemented),
[0109](0109-subagents-per-skill-logic-and-no-skill-manifest.md) (`create-ticket`
leaves the inline, agentless row: it gains four type authors and a reviewer),
[0118](0118-discovery-design-development-phases.md) (the last item of §4,
"`breakdown-ticket` replacing `create-ticket --fan-out`", has landed),
[0120](0120-design-document-catalog-and-ticket-features.md) (a ticket may be a
`bug` and carries five optional bug fields; a child inherits its parent's
`features`) and [0129](0129-discovery-design-development-regroup.md) (Utility
gains `/acs:breakdown-ticket`).

## Context

`/acs:create-ticket` did three jobs in one skill, all inline:

- **Drafting a ticket.** One coordinator wrote every type from the same prose —
  an epic's scope and success metrics, a story's user value, a task's
  technical outcome — and judged its own acceptance criteria. Its
  substantiveness check (MAR-157) was the coordinator re-reading what it had
  just written, the one shape ADR-0004 and ADR-0109 exist to avoid. Nothing
  independent read a draft before the user saw it.
- **Minting an epic's children** (`<epic-id> --fan-out`,
  `references/epic-fan-out.md`, ADR-0075), after the epic's design.
- **Splitting an oversized story or task** (`split <id>`,
  `references/split-ticket.md`), the answer to ADR-0069's two levers.

The second and third are the same operation — take one container of work and
cut it into PR-sized children — reached through two flags on a skill whose
description is about making one ticket. Routing a request like "break SHOP-4
into stories" to `create-ticket` was a coin toss with "create a ticket for
SHOP-4". ADR-0118 named the fix, a `breakdown-ticket` skill, and ADR-0129 kept
a place for it under Utility.

There was also no way to say *this is a defect*. A bug was filed as a story or
a task, so its reproduction, the expected and actual behaviour and the
environment ended up in free prose, and nothing in the pipeline asked for a
regression test that reproduces it. A tracker's Bug issue type had no acs
type to map to.

## Decision

1. **A new Utility skill, `/acs:breakdown-ticket`.** It takes an epic, or a
   story or task too large for one PR, by its ticket id; documents or a
   prompt beside the id join the run's requirements as in any skill
   (ADR-0128). It reads the ticket and its requirements, the feature
   analysis (`README.md` and the bounded contexts the ticket touches, ADR-0133),
   the tech design (`acs.py artifacts show design` → `tech-design.md`, a legacy
   `design.md` still read, ADR-0135) and, when the run has one, the plan's
   oversize-split signal (ADR-0069). It proposes the children — each with a
   title, a type (`story`, `task` or `bug`), acceptance criteria, `features`
   (the parent's unless narrowed), `needs_design: false` and a size from
   create-ticket's rubric — in **one** grouped confirmation, then mints them
   with `new-ticket.py --parent`, saves their acceptance criteria with
   `acs.py ticket save` and syncs them through create-ticket's existing
   tracker-sync reference (shared, not copied). It absorbs
   `create-ticket/references/epic-fan-out.md` and `split-ticket.md`: a story
   or task being split is first converted to an epic that **keeps its id**,
   description and PRD trace (`acs.py ticket save` with
   `{"type": "epic", "needs_design": true}`), as the split did. It warns —
   never blocks — when the epic's tech design is not `approved` (ADR-0135).
   It runs inline, spawns no subagent, and has its own
   `pre-`/`post-breakdown-ticket.py` hooks mirroring create-ticket's; its
   gate, `gate_breakdown_ticket`, needs a ticket and refuses a missing or
   archived partition, a `done` ticket and a `bug` — a defect is fixed in one
   PR, and a related bug or task is a new ticket from `/acs:create-ticket`.
   Its result records `ticket_id`, `type` (always `epic` after the run),
   `converted_from`, `children`, `minted` and `design_status`. 30 skills.
2. **`/acs:create-ticket` drafts through one type author and a reviewer.** The
   coordinator keeps, inline: parsing the input, the sizing rubric that picks
   the type, every question to the user (one grouped ask), the confirmation
   gate, materialisation (`new-ticket.py`, `acs.py ticket save`) and tracker
   sync. Between the type decision and the confirmation it spawns ONE author
   for the chosen type — `create-ticket-epic-author`,
   `create-ticket-story-author`, `create-ticket-task-author` or
   `create-ticket-bug-author` (kind `write`; each writes only the draft
   `steps/create-ticket/iter-<n>/draft.json` and `draft.md` through
   `acs.py write`, ADR-0136, and never mints a ticket or touches the tracker)
   — then `create-ticket-reviewer` (kind `judge`), which checks the draft:
   acceptance criteria concrete and testable, the PRD trace and `features`,
   the type's own completeness, an honest size, and no invented facts. At most
   **two iterations**; the user confirms the reviewed draft. The rules every
   type shares — acceptance-criteria quality, PRD tracing, features,
   grounding — live once, in `skills/create-ticket/references/authoring-rules.md`,
   which every author reads; each author file carries only its own type's
   template and rules:
   - **epic** — problem and outcome, scope in and out, success metrics, a
     `needs_design` recommendation, and a candidate breakdown *outline* only;
   - **story** — the user-facing value (As a / I want / so that, or an
     equivalent) and acceptance criteria in Given/When/Then;
   - **task** — the technical outcome and a done-when checklist, no user story;
   - **bug** — steps to reproduce, expected and actual behaviour, the
     environment or version, a severity (`critical`, `high`, `medium` or
     `low`, separate from priority), the suspected area with citations, and an
     acceptance criterion that a regression test reproduces the bug and passes
     after the fix.
   `--fan-out` and `split …` now **refuse**, naming `/acs:breakdown-ticket`,
   for one release. An epic's run ends with *Next:
   `/acs:create-tech-design <id>` (when `needs_design`) →
   `/acs:breakdown-ticket <id>`*.
3. **`bug` is a ticket type.** `TICKET_TYPES`, the `type` enums of
   `ticket.schema.json` and `tickets-index.schema.json`,
   `new-ticket.py --type bug`, a `bug-default` description template beside
   `epic`/`story`/`task-default`, and the forge's `TYPE_OPTIONS["bug"] = "Bug"`
   (a Project with no Bug option takes the existing "option missing" finding
   path). A bug gains five optional string fields, `BUG_FIELDS`, validated by
   the schema, `new-ticket.py` and `acs.py ticket save` — which refuse them on
   any other type — and rendered in `ticket.md`'s front-matter order:
   `severity`, `reproduction`, `expected`, `actual` and `environment`. In the pipeline a
   bug runs like a story — `/acs:ship` drives it, it is never refused as an
   epic — with two additions: `/acs:analyze-requirements` reproduces it first
   and records the reproduction, or an open question saying it could not; and
   `/acs:create-impl-plan` makes the first test of the first slice a failing
   reproduction test named for the bug, which the plan reviewer checks.
   Nothing else changes.
4. **A child inherits its parent's `features`.** `new-ticket.py --parent`
   copies the parent's `features` to the child; an explicit `--features`
   overrides them. `--parent` still refuses a parent that is not an epic: a
   story or task reaches it only after breakdown-ticket has converted it.

## Consequences

- **Making a ticket and breaking work down are two commands.**
  `/acs:create-ticket` makes one ticket; `/acs:breakdown-ticket` cuts one into
  children. Each skill's description, routing cases and behaviour cases say
  one thing, and the confusable prompts between them have their own routing
  cases.
- **A draft is judged before the user sees it.** create-ticket is a write →
  judge skill now: twelve such loops instead of eleven, the authors on the
  `executor` tier and the reviewer on the `verifier` tier. The scaffold gains
  `models.create-ticket.{epic-author,story-author,task-author,bug-author,reviewer}`;
  no other setting is added. 40 agent files, all reachable.
- **A bug is filed as a bug.** Its reproduction, expected and actual
  behaviour, environment and severity are fields, synced to a tracker's Bug
  type, and the pipeline asks for the reproduction before the analysis and
  for the failing test before the fix.
- **Children land in the right feature folders without retyping.** A child's
  documents go to its parent's `lld/<feature>/` and
  `<development_dir>/<feature>/` folders unless the breakdown narrows them.
- **Breaking.** `/acs:create-ticket <epic-id> --fan-out` and
  `/acs:create-ticket split <id>` refuse. The pointer names
  `/acs:breakdown-ticket <id>`, which does what both did. The refusal is kept
  for one release and then the flags are gone; an old ticket, partition or
  tracker issue needs no migration, and an older `ticket.json` without the bug
  fields still validates.
- Behaviour cases pin the new skill and the new type:
  `breakdown-ticket-epic-into-children` (children inherit `features`, one
  confirmation, minted), `breakdown-ticket-split-oversized-story` and
  `create-ticket-bug-report` (the bug fields and the regression acceptance
  criterion); create-ticket's fan-out and split cases move to the new skill.
