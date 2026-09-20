---
name: create-ticket
description: Turn a raw request — or a remote tracker key to import — into a well-formed acs ticket (epic, story, or task) with PRD tracing, an epic-only needs_design flag, and child fan-out for epics; also runs in --fan-out mode to mint an already-designed epic's children. Use when the user asks to create or import a ticket, describes new work that has no ticket yet, or wants to fan out an existing epic's children after its design is approved.
argument-hint: "<request or remote-key> | <epic-id> --fan-out"
disallowed-tools: Edit, NotebookEdit
---

# /acs:create-ticket

You are the coordinator of /acs:create-ticket. Turn `$ARGUMENTS` (a raw request, or a
remote tracker key) into a schema-complete ticket in the workspace partition: typed,
clarified, traced to the PRD, with an epic-only `needs_design` flag (stated, never
confirmed, for epics; never offered for story/task), and optional tracker sync. An
epic's own creation run always ends with `children: []`; when invoked as
`<epic-id> --fan-out` against an already-created epic, this skill instead mints that
epic's child story/task tickets (see `references/epic-fan-out.md`). You perform the
create-ticket work directly (deterministic inline flow), optionally delegating to
**at most one executor** subagent (`acs:create-ticket-executor`). You NEVER spawn a
planner or a verifier subagent, ever. Decomposition is YOURS alone (subagents
never spawn subagents).

Notation: `<partition>` = `context.partition`, `<id>` = `context.ticket_id`,
`<repo>` = `context.checkout_root`. Substitute real values in every command.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-ticket --allocate --type task --title "(ticket under analysis)" --args "$ARGUMENTS"
```

- The ticket id is minted up front (e.g. `SHOP-123`) with placeholder content; the
  executor rewrites `ticket.json` with the real content later. Sequence gaps from
  abandoned runs are fine — never hand-pick ids.
- **Except when resuming.** If `$ARGUMENTS` is exactly a ticket id, or
  `--ticket` is passed, and that ticket still has a live partition, the run
  resumes it instead of minting a second id for the same work (`/acs:ship`
  re-invokes an interrupted create-ticket this way). A prompt that merely
  MENTIONS an id — "follow-up to SHOP-1: …" — is not a resume and still mints
  a new ticket.
- If skill-start exits non-zero: STOP and surface its stderr verbatim to the user.
  One specific case of this rule: on a fresh/unreconciled workspace partition,
  `--allocate` refuses with exit 2 and a local-evidence reconciliation proposal
  (`allocate_ticket_id`'s fail-closed gate, MAR-402) instead of minting an id.
  Relay that stderr verbatim, obtain the confirmed start number from the user
  — never invent it — and re-run `skill-start.py` with `--seed-next <n>` added.
- Parse the printed context JSON. Bind: `partition`, `ticket_id`, `ticket`,
  `settings`, `models`, `reconcile`, `prior_run_status`, `handoff_summary`,
  `pipeline`, `post_hook`, `checkout_root`, `plugin_root`.

## Remote import

Decide BEFORE planning whether `$ARGUMENTS` is a remote key for
`settings.tracker.provider`:

- provider `jira` and `$ARGUMENTS` matches `[A-Z][A-Z0-9]*-[0-9]+` (e.g. `PROJ-456`):
  pull with `acli jira workitem view PROJ-456`.
- provider `github` and `$ARGUMENTS` is `#123`, a bare integer, or a GitHub issue
  URL: pull with `gh issue view 123 --json number,title,body,labels,assignees,url`.
- provider `local`, or no match: not an import — treat `$ARGUMENTS` as the request.

On import: if the pull fails — **critical**, a gate input this run cannot
proceed without — stop and surface the CLI error verbatim plus the canonical
hint from `acs_lib.gh_failure_hint(stderr)` (see "GitHub call failure
policy" below), with no fallback to any other transport. Otherwise seed the
working title/description from the remote issue and record the mapping
`external = {"provider": "jira", "key": "PROJ-456"}` (or `{"provider": "github",
"key": "123"}`) for the executor to write into `ticket.json`. Then run the NORMAL
analysis below on the imported description — imports get the same clarification,
typing, PRD trace, and needs_design decision as a local request. Never create a new
remote issue for an imported ticket: the mapping points at the existing one.

### GitHub call failure policy

`gh` (and `acli` for Jira) are the only tracker transports this skill uses —
no MCP-based transport, no second credential path (ADR-0088). Three classes apply to
every call below: **critical** (a gate input this step cannot proceed
without — gh's verbatim stderr plus ONE canonical hint from
`acs_lib.gh_failure_hint(stderr)`, then STOP, no fallback to any other
transport), **critical (per ticket), soft (per batch)** (Step 5's `gh issue
create` only — an error finding naming that ticket, `replayable: false`,
but the batch continues to the next ticket), and **non-critical**
(metadata/best-effort — one `info` finding plus a replayable command block,
never abort). Canon hint text
(`acs_lib.GH_ACCESS_HINT`, selected when the stderr names a session-access
restriction; `acs_lib.GH_GENERIC_HINT` otherwise):

> This looks like a session-level access restriction — a Claude Code
> cloud/managed session must have the Claude GitHub App connected for this
> organization by an org admin. A local Claude Code session uses your own
> `gh` authentication and should not see this.

Finding shape (all three classes; the hybrid class shares critical's
pair): `{severity, area, message, command, error,
hint, replayable}` — `info` / `replayable: true` for non-critical, `error` /
`replayable: false` for critical and for critical (per ticket), soft (per
batch). Per-call classification:

- **Critical**: the remote-import `gh issue view` above.
- **Critical (per ticket, soft per batch)**: Step 5's `gh issue create`
  tracker-sync call — a failed create for one ticket is an **error**-severity
  finding for that ticket (naming that ticket's id + error + the canonical
  hint), `replayable: false`, but does NOT abort the batch: the loop
  continues to the next ticket, and that ticket's `external` stays null.
- **Non-critical**: the labels/assignee/milestone/Projects v2 field-fill
  checklist only (`gh label list`, `gh api …/milestones`, `gh project
  item-add` / `field-list` / `item-edit`) — one `info` finding,
  `replayable: true`, continue.

## The three alternative modes, and when to open each

Nearly all of this skill is one flow: analyze a raw request or a remote
import, confirm it with the user, write `ticket.json`. Three parts are not,
and each is read by exactly one kind of run — so they live in references
rather than inline. Resolve the mode BEFORE Remote import above; the
precedence is `--fan-out` -> split -> remote import -> raw request:

| Open | When |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/epic-fan-out.md` | `$ARGUMENTS` resolves to a local ticket id AND carries `--fan-out`. It mints an already-created epic's children and replaces Steps 1-3. |
| `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/split-ticket.md` | `$ARGUMENTS` asks to split or restructure an existing local ticket (e.g. `split SHOP-123 per <plan path>`). It converts that ticket into an epic keeping its id. |
| `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md` | `settings.tracker.provider` is `github` or `jira`. It is Step 5 of the flow below, and the two modes above reach it through the same pointer. On the default `local` provider there is nothing to sync and the step does not run. |

## Resume & reconcile

- If `context.reconcile` is true: verify recorded progress against reality BEFORE
  continuing — re-read `<partition>/ticket.json`, the persisted
  `steps/create-ticket/iter-*-*.xml` files, and any child partitions
  already minted (children listed in `ticket.json` must actually exist on disk with
  `parent` set). Continue from the first unfinished phase; do not redo work that
  verifiably holds, and never mint duplicate children for ones that already exist.
- If `context.handoff_summary` exists: read it, do a light reconcile (trust it but
  cheaply re-check the artifacts it names), and continue from where it points. Also
  read `steps/create-ticket/handoff-context.md` if present.

## Inline apply flow

This inline flow is the same on every run: /acs:create-ticket has no planner and
no verifier, and nothing about a ticket re-introduces either.
create-ticket carries no in-skill verifier subagent because this is **deterministic
minting** — schema completeness is enforced by the schema, and the user-confirmation
gate (step 2 below) is the quality checkpoint. The in-loop verifier gate (MAR-55
invariant (d)) belongs to the downstream code review; there is no upstream
code-verifier for create-ticket — the correctness mechanism here is the schema plus the
user-confirmation gate.

If you delegate to an executor, spawn **at most one** `acs:create-ticket-executor`
subagent. Apply `context.models.executor.model` / `.effort` for the executor when not `"inherit"`;
if the runtime rejects the model or effort, FAIL the run with that exact error — no
silent fallback. Validate all XML messages:

```bash
echo "<xml...>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
```

On invalid: re-request the message once with the validation error; still
invalid → fail the run and record the error in the result document's `errors`.

Persist each phase output to `steps/create-ticket/iter-<n>-<phase>.xml`
at the phase boundary, BEFORE starting the next phase.

### The sizing rubric

**One story or task must equal ONE reviewable PR.** The ticket is the PR
boundary — all of its work lands on one branch — so size it for review,
grounded in a survey of the codebase: as a rule of thumb a story or task
should need roughly **≤400 changed lines**, touch **one concern**, and carry
**≤~7 acceptance criteria**. Estimate the expected diff surface (the
modules and files the survey turned up) and state it. Above the bar —
recommend `epic` and cut children at PR-sized seams: by layer, by endpoint,
by migration versus consumer, behind a feature flag when a slice alone would
break the build. Never propose one mega-story because decomposition is
tedious.

### Step 1 — Analyze and recommend fields

The coordinator (or its single optional executor) reads the raw request (or imported
remote issue), the codebase, the PRD, and the roadmap. Produce a complete proposal:

- `type` (epic / story / task), `title`, `description` outline, `acceptance_criteria`
  (array of testable strings), `priority`, `story_points`
- Judge each proposed `acceptance_criteria` entry for concreteness/testability
  — an observable, checkable outcome versus vague satisfaction-claim
  boilerplate (e.g. "works correctly", "is better", "no bugs", "handles X
  properly") — and flag any non-concrete/non-testable entry as part of the
  proposal presented to the user in Step 2
- `prd_trace`: the PRD feature/goal this ticket traces to (epics to a roadmap
  milestone), or a divergence flag when the request goes beyond the PRD
- a PR-size reading in prose — is this one reviewable PR, or should it be an
  epic with children? — judged against the sizing rubric just above. It is a
  recommendation about SHAPE, not a stored axis: a ticket carries no `size` or
  `stakes` field since ADR-0095, and how much rigor the work gets is judged
  later, from its plan, by `/acs:ship`.
- For epics: proposed child story/task breakdown with title, type, and
  points (children are always `needs_design: false` — the epic carries the
  design) — apply the same concreteness/testability judgment to any
  AC/DoD-shaped text proposed for a child. This breakdown is produced
  only in a `--fan-out` run (or a split/restructure run); an epic's own
  creation run proposes no child breakdown and ends with `children: []`.

No separate planner subagent is spawned. The coordinator performs this analysis
inline.

### Step 2 — User-confirmation gate (human-in-the-loop checkpoint)

**This step is a deliberate design requirement (MAR-55 invariant (c)) — it is NOT a
verifier and it is never skipped.** The coordinator presents the proposal
and blocks until the user confirms or overrides:

1. Resolve every ambiguity ABOUT THE TICKET RECORD with the user before
   finalizing — what the work is, which type it is, and the fields items 2-7
   confirm. Deeper REQUIREMENTS clarification is no longer this skill's job:
   impact, assumptions, risks and refined acceptance criteria belong to
   `/acs:analyze-requirements <id>`, the first Build step, which records each question
   through `clarify.py` and proposes AC rewrites for your confirmation. Ask here
   only what you need to write a well-formed ticket; park anything that needs
   the codebase read for the analysis, and say so when you present the proposal.
2. **PRD divergence**: if the proposal goes beyond the PRD, present the divergence,
   propose a follow-up `/acs:create-prd` re-run, and obtain explicit user
   confirmation to proceed (or stop at the user's choice). Record the confirmed
   divergence one-liner.
3. **AC/DoD substantiveness**: present every flagged `acceptance_criteria` entry
   (root proposal, and — in a `--fan-out` or split/restructure run only — any
   flagged child-breakdown AC/DoD text for an epic) to the
   user. The user must either revise the entry or explicitly confirm keeping it
   as-is — the ticket does not finalize with a flagged entry unless the user
   explicitly confirms it anyway.
4. **Type and needs_design**: epics are always `needs_design: true` (state it, do
   not ask). For `docs_only`, present the recommendation and obtain USER CONFIRMATION
   when recommended `true` (it relaxes /acs:code's TDD/coverage gates — never set it
   without explicit user confirmation; when `false`, don't ask).
5. **Due date**: ask the user for an optional due date ("YYYY-MM-DD, or leave
   blank").
6. **Epic only**: present the proposed child breakdown and obtain user confirmation
   or edits before any child is minted. This item is reached only in the
   `--fan-out` mode or a split/restructure run; an epic's own creation run has
   no child breakdown to present and ends with `children: []`.

If you genuinely cannot reach the user (e.g. a non-interactive run), return
`<handoff skill="create-ticket" ticket-id="<id>" status="needs_input">` with the
open `<questions>` instead of guessing — see Finish.

**A request that delegates the record up front IS the confirmation.** When
the request itself says to decide without waiting — "you decide", "use your
judgement", "no need to confirm", "raise it with sensible defaults" — items
1 and 3-6 are answered by that delegation: record each field you settle
(type, priority, every acceptance criterion, no due date)
with `clarify.py add … --source assumption --rationale "…"`, keep
`docs_only` at `false` (the one value a delegation never sets to `true`),
list the assumptions under the completion report's Findings, and continue
to Step 3. Never return `needs_input` for a question the request already
delegated — a headless run that hands off on "story or task?" after being
told to decide has produced nothing. Only item 2, a PRD divergence, still
needs the user: a delegation never confirms going beyond the PRD.

### Step 3 — Rewrite ticket.json

Rewrite `<partition>/ticket.json` PRESERVING `id`, `status`, and `created_at`, and
setting all fields required by `schemas/ticket.schema.json`:

- `title`, `type`, `description`, `acceptance_criteria` (array of testable strings),
  `priority` (`critical|high|medium|low`), `parent` (null — this skill creates
  roots), `children` (`[]` on every creation run, including an epic's own —
  Step 4 fills it later, in a `--fan-out` or split/restructure run), `status`,
  `external` (the
  import mapping, the sync result from step 5, or null), `assignee` (or null),
  `story_points` (or null), `needs_design`, `docs_only` (confirmed value, default
  false), `due_date` (ISO-8601 date string or null); refresh `updated_at`
  (ISO-8601 UTC).

Render the title from `settings.formats.tickets.<type>.title` with placeholders
`{ticket_id}`, `{type}`, `{title}`, `{external_key}` (empty string when unsynced).
Build the description from the type's `description_template` (defaults:
`epic-default`, `story-default`, `task-default`). Resolution: a built-in name maps
to `${CLAUDE_PLUGIN_ROOT}/templates/<name>.md`; otherwise
`<repo>/.acs/templates/<name>.md`; otherwise an absolute path. Fill every section,
drop the HTML comments.

Every description template carries an `acs-ticket: {ticket_id}` line in its
`## Notes` section (epic-default's own `## Notes`, mirroring task/story) — the
rendered text is byte-identical across all three built-in templates, so the
acs ticket id is visibly recorded in the ticket's own body regardless of type
(AC-1). This line renders unconditionally as part of every description fill —
it is NOT itself conditional on tracker sync; what IS conditional is whether
that description ever reaches GitHub (Step 5 below, where the `local` provider
skips sync entirely — no regression for unsynced tickets, AC-4).

### Step 4 — Epic fan-out via new-ticket.py

Step 4 runs ONLY under `--fan-out` mode (`references/epic-fan-out.md`) or in the split/restructure
mode (above) — the two modes that mint children — and never during the
epic's own creation run. An epic's
creation run (Steps 1-3) always finishes with `children: []`; fan-out is
deferred until after `/acs:create-design` completes, when the user
re-invokes `/acs:create-ticket <epic-id> --fan-out`.

For each user-confirmed child, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/new-ticket.py" --title "Wishlist API" --type story --parent SHOP-123 --description "..." --priority medium --needs-design false --story-points 3
```

A child carries no rigor axes to pass — there are none (ADR-0095). Children are
confirmed ONCE, at the `--fan-out` mode's own confirmation gate (Step 2 item 6)
— or, in a split/restructure run, at that mode's own user confirmation of the
seams (above) — never individually re-confirmed by a child's own
`/acs:create-ticket` run, since a child never runs one (below). How much rigor
each child's implementation gets is decided later and per child, when
`/acs:ship` judges that child's own plan onto a delivery path.

This mints the child id, writes BOTH link directions (child `parent`, epic
`children`), and records a completed create-ticket run for the child — children do
NOT rerun /acs:create-ticket; their pipeline starts at /acs:code, which reads
the parent epic's `design.md`. Capture each printed `ticket_id`.

### Step 5 — Tracker sync

Only when `settings.tracker.provider` is `github` or `jira` — on `local`
there is no remote, so skip to Finish. When it does apply, open
`${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md` and
follow it: which tickets enter the sync set and which are excluded, the
`acs.py tracker sync` batch call and how to read its JSON, the `acli`
sequence for jira, and the per-ticket failure rule that surfaces a failed
sync without aborting the batch.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a /ship brief — with
`clarify.py add --skill create-ticket --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

Before finalising the ticket, ask the user for an optional due date:
"Do you want to set a due date for this ticket? (YYYY-MM-DD, or leave blank
for none)". Record the answer with `clarify.py add`; pass the non-blank value
to `new-ticket.py --due-date <date>`, or omit the flag if blank. Record the
answer in the clarification ledger.

Ask clarifying questions whenever the request is genuinely ambiguous (scope, type,
priority, acceptance criteria, PRD divergence) — use AskUserQuestion or plain
questions, and ask BEFORE finalizing, not after. Do not ask about things the
codebase or docs already answer. When you genuinely cannot reach the user (a
non-interactive run): return a `<handoff ... status="needs_input">` with
`<questions>` instead of guessing. A request that delegates the decisions up
front is not such a case — it is answered, by assumption entries, per Step 2's
delegation rule.

## Context pressure

If your context is running low mid-run: flush in-flight work and soft context
(user answers, confirmed decisions, partial findings, gotchas, minted child ids) to
`steps/create-ticket/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the exact `continue_with` command it prints, then stop.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/create-ticket/result.json` per the result-document
   contract in INTERNALS.md. The `states` keys are EXACTLY: `ticket_id`, `type`,
   `needs_design`, `children`, `prd_trace`. Example:

   ```json
   {
     "status": "completed",
     "stop_reason": "epic created; children deferred to --fan-out",
     "states": {
       "ticket_id": "SHOP-123",
       "type": "epic",
       "needs_design": true,
       "children": [],
       "prd_trace": {"feature": "Wishlist (Must-have, roadmap M2)", "divergence": null}
     },
     "findings": [],
     "errors": []
   }
   ```

   `children` is `[]` for non-epics **and for an epic's own creation run**;
   only a `--fan-out` (or split/restructure) run reports a non-empty list.
   `prd_trace.feature` is the PRD feature/goal
   the ticket traces to (null when no PRD exists); `prd_trace.divergence` is null
   or the user-confirmed divergence one-liner. On failure keep whatever is true
   (e.g. minted children) and record blocking findings under `findings` with
   `severity: "blocking"`.

2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-ticket.py" --ticket <id> --result-file steps/create-ticket/result.json
   ```

3. Report. Direct invocation: a compact summary — ticket id, type, title,
   needs_design, children, PRD trace, tracker key — and the next command:
   `/acs:create-design <id>` when `needs_design` is true, else
   `/acs:code <id>` (epic children each continue with
   `/acs:code <child-id>` after the epic's design). Under /acs:ship: return
   ONLY the `<handoff>` XML as your final message (validated, summary <= 1 KB):

   ```xml
   <handoff skill="create-ticket" ticket-id="SHOP-123" status="completed">
     <summary>Created epic SHOP-123 "Wishlist" (needs_design=true); no children yet — fan out later with /acs:create-ticket SHOP-123 --fan-out after its design; traced to PRD feature "Wishlist (Must-have)"; synced to jira PROJ-789.</summary>
     <artifacts>
       <file><partition>/ticket.json</file>
       <file>steps/create-ticket/result.json</file>
     </artifacts>
     <next-step>/acs:create-design SHOP-123</next-step>
   </handoff>
   ```

   For a `--fan-out` run, the same `<handoff>` shape applies; `children` in
   the result document is the epic's full child list after this run, and the
   summary states how many children were minted.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-ticket · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: ticket id, type, title; `needs_design`; children created (ids) (none on an epic's own creation run); PRD trace or flagged divergence; tracker key when synced
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:create-design <id>` when `needs_design` is true, else `/acs:code <id>`; for an epic, each child continues with `/acs:code <child-id>` after the epic's design; a not-yet-fanned-out epic runs `/acs:create-ticket <id> --fan-out` after its design
```
