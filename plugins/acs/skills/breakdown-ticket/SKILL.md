---
name: breakdown-ticket
description: Break one epic — or a story or task too big for one reviewable PR — into PR-sized child tickets. Reads the ticket's requirements, its feature analysis, its tech design and a plan's oversize split seams, proposes every child (title, type story/task/bug, acceptance criteria, features, size) in ONE grouped confirmation, then mints them under the parent and syncs them to the tracker; a story or task being split becomes an epic that keeps its id. Use after an epic's tech design, or when a plan or the user says a ticket is too large — whenever asked to break down, split, decompose or fan out an existing ticket into child stories or tasks. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "<ticket-id> [documents…] [prompt]"
disallowed-tools: Edit, NotebookEdit
---

# /acs:breakdown-ticket

You are the coordinator of /acs:breakdown-ticket. Take ONE existing ticket — an
epic (after its tech design, when it has one), or a story or task too large for one reviewable PR — and
cut it into PR-sized children: propose them, confirm them with the user ONCE,
mint them under the parent, and sync them to the tracker. A story or task being
split first becomes an epic that keeps its id (ADR-0069, ADR-0138). This skill
replaced `/acs:create-ticket <epic-id> --fan-out` and `/acs:create-ticket split
<id>`; it creates no ticket of its own and never rewrites the parent's
requirements.

You do ALL of it yourself, inline, and **spawn no subagent**: the children come
from documents another skill already reviewed (the tech design, the plan, the
analysis), the user's one confirmation is the quality gate, and minting is a
fixed sequence of commands.

Notation: `<partition>` = `context.partition`, `<id>` = `context.ticket_id`,
`<repo>` = `context.checkout_root`. Substitute real values in every command.

## Start

MANDATORY first action — run exactly, with `<ID>` the ticket id in `$ARGUMENTS`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step breakdown-ticket --ticket <ID> --args "$ARGUMENTS"
```

- `$ARGUMENTS` names the ticket and, optionally, documents (a plan path such as
  `steps/create-impl-plan/plan.md`, a design) and a prompt (focus notes: "split
  per the plan", "keep the migration separate"). No ticket id → there is nothing
  to break down: tell the user to capture the work first with
  `/acs:create-ticket`, and stop.
- If `acs step start` exits non-zero: STOP and surface its stderr verbatim. Its
  gate refuses a missing, archived or done ticket and a `bug` (a bug is fixed in
  one PR; related work is a new ticket through `/acs:create-ticket`).
- Parse the context JSON. Bind: `partition`, `ticket_id`, `ticket`,
  `requirements`, `settings`, `reconcile`, `handoff_summary`, `checkout_root`,
  `post_hook`.
- `references` — **References: `context.references` lists this run's documents found in the standard layout — read the ones relevant to this step before working; never search the repo for them.**
- **The mode follows the parent's type.** `epic` → **fan-out**: mint its
  children; the epic's own record is not re-analyzed or rewritten — only its
  `children` grow. `story` or `task` → **split**: the ticket is converted to an
  epic keeping its id, description, priority and PRD trace, then its children are
  minted (Materialize, step 1). Either way no `--allocate`: the partition exists
  and no new id is minted for the parent.

## Resume & reconcile

- If `context.reconcile` is true: re-read the parent with `python3
  "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" ticket show --ticket <id>`, every
  child it lists (`ticket show --ticket <child-id>`: each must exist with
  `parent` = `<id>`), and `steps/breakdown-ticket/iter-*/materialize.json`. Continue from the first
  unfinished step. **Never re-mint a child the parent's `children` already
  lists**, and never re-convert a ticket that is already an epic.
- If `context.handoff_summary` exists: read it and
  `steps/breakdown-ticket/handoff-context.md`, spot-check what they name, and
  continue from where they point.

## Inputs — read what exists, fall back to the ticket

Resolve the run's documents with `python3
"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show --ticket <id>`, and
read, in this order:

1. **The requirements** — `requirements.path`: the parent's description and
   acceptance criteria. Every parent criterion must be covered by at least one
   child (the coverage table below). Never read `ticket.json` for criteria.
2. **The feature analysis** — `feature_analysis`
   (`<prd_dir>/features/<feature>/analysis/`, ADR-0133): its `README.md`, then
   only the context files the parent touches (a legacy single `analysis.md`
   whole); and the parent's own run analysis when `artifacts` lists one.
3. **The tech design** — `artifacts["tech-design.md"]` (a legacy `design.md` is
   still read), and its status: `acs.py design check <path>`. A ticket carries
   no design flag (ADR-0139): with no design, derive from the other inputs and
   warn nothing. When a design exists but is not `approved`
   (`/acs:set-doc-status approved <feature>` approves it, ADR-0135), carry ONE
   warning line into the confirmation and a `design_not_approved` finding into
   the result — **warn, never block**: the user may break down an unapproved
   epic.
4. **The plan's oversize signal** — the plan `$ARGUMENTS` names, else
   `artifacts["plan.md"]`: its split seams (ADR-0069), recorded by the planner
   when the decomposition exceeded one PR. On a split this is usually the
   evidence the user is acting on.
5. **The parent's own description** — an epic drafted by `create-ticket` carries
   a candidate breakdown outline under `## Notes`; a hint, never binding.

## Deriving the children

Cut children at PR-sized seams, in this order of evidence:

- **From the design.** The built-in template (`templates/design-default.md`) has
  no slice table: read the seams from its `## LLD` snapshots and `## HLD views
  affected` (each new or changed interface, flow, entity or component is a
  candidate child) and the ordering from `## Risks` › `### Rollout & migration`
  (sequencing, migrations, flags, backward compatibility) — plus any slice
  breakdown a repo's own design template adds. A legacy `design.md` carries them
  under `## Architecture` and `## Rollout/migration`.
- **From the plan's split seams**, on a split.
- **Otherwise from the parent's description and acceptance criteria**, grounded
  in a look at the code the criteria touch.

Each proposed child carries:

| Field | Rule |
|---|---|
| `title` | what the PR delivers, as given (no `[EPIC] ` prefix) |
| `type` | `story` (user-visible capability), `task` (technical work, no user story) or `bug` (a defect the design or plan found) |
| `acceptance_criteria` | concrete and testable — the rules in `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/authoring-rules.md` "Acceptance criteria"; FLAG any you could not make concrete |
| `features` | the parent's, inherited by `new-ticket.py`; narrowed only when the child clearly serves fewer of them |
| `requirements` | the `<slug>/R<n>` ids of the linked feature PRDs this child delivers (a story: at least one; ADR-0144). Together the children cover every requirement the parent names — an uncovered one is a gap in the coverage table |
| `priority`, `story_points` | the parent's priority unless the ordering says otherwise; points per the rubric |

**Size every child to ONE reviewable PR** with create-ticket's sizing rubric
(`${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/SKILL.md` "The sizing rubric"):
roughly ≤400 changed lines, one concern, ≤~7 acceptance criteria, each child
independently shippable — by layer, by endpoint, migration versus consumer,
behind a feature flag when a slice alone would break the build. Never propose one
mega-child because decomposition is tedious. Build a **coverage table**: each
parent acceptance criterion → the child (or children) that delivers it; a parent
criterion no child covers is a gap you show, never drop.

## The confirmation — ONE grouped interaction

**This gate is never skipped, and no child is minted before the user confirms or
edits the breakdown.** Present, in ONE interaction:

1. the parent, its mode, and on a split: "<id> becomes an epic, keeping its id,
   description, priority and PRD trace";
2. the design warning, when Inputs step 3 raised one;
3. on a split, any downstream work that already exists (a plan, specs, a branch):
   prior state files stay in the epic's partition as history, and the children
   start their own pipelines fresh — say so;
4. the children table (title, type, points, features, requirements, criteria) with every
   FLAGGED criterion marked, and the coverage table;
5. an optional due date per child ("YYYY-MM-DD, or blank").

The user confirms, edits or drops children. A flagged criterion is minted only
once the user revised it or explicitly kept it. Record the confirmation and each
answer with `clarify.py add --skill breakdown-ticket` (User interaction).

**A request that confirms up front IS the confirmation.** When the request
itself lists the children and says not to ask ("I confirm these three", "you
decide", "no need to confirm"), record each settled field with `clarify.py add …
--source assumption --rationale "…"`, list the assumptions under the completion
report's Findings, and continue. Never return `needs_input` for what the request
already settled. If you genuinely cannot reach the user (a non-interactive run),
return `<handoff skill="breakdown-ticket" ticket-id="<id>" status="needs_input">`
with the open `<questions>` — see Finish.

## Materialize — inline, in this order

The confirmed breakdown is binding: do not re-analyze while minting. If it turns
out impossible to write as confirmed, stop and say so (Finish, failure path).

1. **Split only — convert the parent to an epic.** `new-ticket.py --parent`
   refuses a parent that is not an epic, so the conversion comes first, as a
   patch through `acs.py ticket save` (never a hand edit):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" ticket save --ticket <id> --from - <<'ACS_EOF'
   {"type": "epic", "title": "[EPIC] <the ticket's title>"}
   ACS_EOF
   ```

   Its id, description, priority, features and PRD trace stay. An existing
   approved design in the partition counts as the epic's design.
2. **Mint each confirmed child** not already in the parent's `children`:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/new-ticket.py" --title "Wishlist API" --type story --parent SHOP-123 --description "..." --priority medium --story-points 3 --requirements wishlist/R1 --require-prd-link
   ```

   It mints the child id, writes BOTH link directions (child `parent`, parent
   `children`) and copies the parent's `features` to the child (pass `--features
   <slugs>` only to narrow them, `--due-date` only when one was given).
   `--require-prd-link` is always passed: a child whose link to the PRD is not
   sound (`acs.py ticket link-check`) is refused before an id is spent. A `bug`
   child takes its bug fields (`--severity`, `--reproduction`, `--expected`,
   `--actual`, `--environment`) when the breakdown settled them. Capture each
   printed `ticket_id`. Children never run `/acs:create-ticket`: their pipeline
   starts at `/acs:analyze-requirements <child-id>` (or `/acs:ship <child-id>`).
3. **Save each child's acceptance criteria.** `new-ticket.py` exposes no
   `--acceptance-criteria` flag, so write the confirmed criteria into the child's
   ticket with a PATCH:

   ```bash
   printf '%s' '{"acceptance_criteria": ["...", "..."]}' \
     | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" ticket save --ticket <child-id> --from -
   ```

   The ticket lives in the workspace and the tracker only, never in the repo
   (ADR-0128). Never hand-edit `ticket.json`, `counters.json`,
   `tickets-index.json` or `run.json`; never allocate an id yourself.
4. **Record each child's references** (ADR-0140) — the documents the standard
   layout holds for its features, the parent epic's design records included
   (the layout finds them from `parent`; nothing to pass):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" ticket references --ticket <child-id> --write
   ```

   Then **re-read the parent**: its `children` must list every minted id.
5. **Tracker sync** — only when `settings.tracker.provider` is `github` (skip on
   `local`). Open `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md`
   and follow it — the one tracker-sync procedure both skills share. The sync set
   is the children minted in step 2. **Write each child's body first** —
   `tracker sync` refuses a partition without one: `acs.py write
   <child partition>/tracker-body.md` (the `partition` new-ticket.py printed) with
   the child's description, its criteria as a `## Acceptance criteria` checklist,
   an empty `## References` section (`<!-- acs:references -->` then
   `<!-- /acs:references -->`, which the sync fills) and a last line
   `acs-ticket: <child-id>`. The parent's `external` is already set, so the
   exclusion rule keeps its issue from being re-created; refresh its References
   block instead with `acs.py tracker refresh --ticket <id>` (non-critical: an
   `info` finding on failure). On a split, the parent's remote issue is
   **updated** to the Epic type with links to its children. A failed `gh issue create` is critical per ticket and soft per batch:
   an `error` finding naming that child, `replayable: false`, and the batch
   continues (`gh` is the only transport, ADR-0088).
6. **Write the materialize report** to
   `steps/breakdown-ticket/iter-1/materialize.json` through `acs.py write`:
   the commands run with their outcomes, the ids minted, the conversion, the sync
   result, problems hit. On failure keep what was minted — never roll a child back.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list`
and reuse any recorded answer — re-asking an answered question is a defect.
Every question this run has goes into the ONE grouped interaction above (e.g. a
single AskUserQuestion holding the breakdown and the open points as a numbered
list), never serial round-trips. Record each answer as its own `clarify.py add
--skill breakdown-ticket --question "..." --answer "..."` entry (one `C-<n>` per
question, `--source` preserved) BEFORE acting on it. Never skip a question, merge
two questions into one entry, or auto-answer a question outside the
`--source assumption --rationale "..."` rule. Before a needs_input handoff,
record the outgoing questions as `open` (`clarify.py add` without `--answer`).

## Context pressure

If your context is running low mid-run: flush in-flight work and soft context
(the confirmed breakdown, minted child ids, answers) to
`steps/breakdown-ticket/handoff-context.md` through `acs.py write`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next / decisions>"
```

Tell the user the exact `continue_with` command it prints, then stop.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/breakdown-ticket/result.json` through `acs.py write` (never the
   Write tool), per the result-document contract in INTERNALS.md. The `states`
   keys are EXACTLY: `ticket_id`, `type`, `converted_from`, `children`, `minted`,
   `design_status`. Example:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write steps/breakdown-ticket/result.json <<'ACS_EOF'
   {
     "status": "completed",
     "summary": "SHOP-12 split into 3 children; converted from story to epic",
     "states": {
       "ticket_id": "SHOP-12",
       "type": "epic",
       "converted_from": "story",
       "children": ["SHOP-13", "SHOP-14", "SHOP-15"],
       "minted": ["SHOP-13", "SHOP-14", "SHOP-15"],
       "design_status": null
     },
     "findings": [],
     "errors": []
   }
   ACS_EOF
   ```

   `type` is the parent's type after the run (`epic`); `converted_from` is
   `story` or `task` on a split, `null` on a fan-out; `children` is the parent's
   full list after the run, `minted` only this run's; `design_status` is the tech
   design's status (`approved`, `proposed`, …) or `null` when there is none. On
   failure keep whatever is true (the children minted so far) and record the
   blocking findings with `severity: "blocking"`.
2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-breakdown-ticket.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim.
3. Report. Under /acs:ship (or any caller expecting one): return ONLY the
   `<handoff>` XML as your final message (summary ≤ 1 KB), `<next-step>` naming
   the first child:

   ```xml
   <handoff skill="breakdown-ticket" ticket-id="SHOP-12" status="completed">
     <summary>Split SHOP-12 into SHOP-13..SHOP-15 (2 stories, 1 task); SHOP-12 is now an epic keeping its id; features inherited; no tracker sync (local).</summary>
     <artifacts>
       <file>steps/breakdown-ticket/result.json</file>
       <file>steps/breakdown-ticket/iter-1/materialize.json</file>
     </artifacts>
     <next-step>/acs:ship SHOP-13</next-step>
   </handoff>
   ```

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your
final message is the `<handoff>` XML instead — this report is for direct
invocations:

```markdown
## /acs:breakdown-ticket · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>; converted from <story|task> when split)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: children minted (id, title, type, points), inherited or narrowed features, the coverage of the parent's criteria, each child's references (pending ones marked), the design status (a warning when not approved), tracker keys when synced
- **Findings**: <open findings / flagged criteria kept / assumptions, or "none">
- **Artifacts**: <partition files>
- **Metrics**: children <n> · <wall time>
- **Next**: each child continues on its own: `/acs:ship <child-id>` (or `/acs:analyze-requirements <child-id>`), one run at a time; epics are never implemented directly
```
