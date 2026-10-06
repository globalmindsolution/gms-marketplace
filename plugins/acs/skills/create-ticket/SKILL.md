---
name: create-ticket
description: Turn requirements — a raw request, a bug report, documents (specs, PDFs, images; in the repo or attached), a feature's analysis, a mix of them, or a remote tracker key to import — into one well-formed acs ticket (epic, story, task or bug) with PRD tracing, drafted by an author for its type and checked by a reviewer before you confirm it. Use when the user asks to create, file, log or import a ticket, reports a bug or describes new work that has no ticket yet. Not for breaking an existing ticket into children — that is /acs:breakdown-ticket. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[documents…] [request] | <remote-key>"
disallowed-tools: Edit, NotebookEdit
---

# /acs:create-ticket

You are the coordinator of /acs:create-ticket. Turn `$ARGUMENTS` (requirements — a raw
request, a bug report, documents in the repo or attached from outside it, or a mix of
them — or a remote tracker key) into ONE schema-complete ticket in the workspace
partition: typed (`epic`, `story`, `task` or `bug`), clarified, traced to the PRD,
and optionally synced to the tracker. A ticket records no design flag (ADR-0139): a
design is written when the user asks for one. Every creation run ends with
`children: []` — an epic's children are minted later by `/acs:breakdown-ticket`.

You keep, inline: parsing the input, the sizing rubric that picks the type, every
question to the user (one grouped ask), the confirmation gate, materialization
(`references/materialize.md`) and tracker sync. Between the type decision and the
confirmation you spawn ONE author for the chosen type, then the reviewer (Step 1b):
the draft the user confirms has been judged by an agent that did not write it.
Decomposition is YOURS alone — subagents never spawn subagents.

Notation: `<partition>` = `context.partition`, `<id>` = `context.ticket_id`,
`<repo>` = `context.checkout_root`. Substitute real values in every command.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-ticket --allocate --type task --title "(ticket under analysis)" --args "$ARGUMENTS"
```

- The ticket id is minted up front (e.g. `SHOP-123`) with placeholder content;
  Step 3 rewrites `ticket.json` with the real content later. Sequence gaps from
  abandoned runs are fine — never hand-pick ids.
- **Except when resuming.** If `$ARGUMENTS` is exactly a ticket id, or
  `--ticket` is passed, and that ticket still has a live partition, the run
  resumes it instead of minting a second id for the same work (`/acs:ship`
  re-invokes an interrupted create-ticket this way). A prompt that merely
  MENTIONS an id — "follow-up to SHOP-1: …" — is not a resume and still mints
  a new ticket.
- **Retired modes — refuse BEFORE `step start`.** When `$ARGUMENTS` is a local
  ticket id with `--fan-out`, or asks to split or restructure an existing ticket
  (`split SHOP-123 per <plan path>`), run nothing and mint nothing: reply that
  the mode moved to `/acs:breakdown-ticket <id>` (ADR-0138), which mints an
  epic's children and splits an oversized story or task into
  an epic that keeps its id — and stop. Under /acs:ship return
  `<handoff skill="create-ticket" ticket-id="<id>" status="failed">` with that
  pointer as `<next-step>/acs:breakdown-ticket <id></next-step>`.
- If `acs step start` exits non-zero: STOP and surface its stderr verbatim to the user.
  One specific case of this rule: on a fresh/unreconciled workspace partition,
  `--allocate` refuses with exit 2 and a local-evidence reconciliation proposal
  (`allocate_ticket_id`'s fail-closed gate, MAR-402) instead of minting an id.
  Relay that stderr verbatim, obtain the confirmed start number from the user
  — never invent it — and re-run `acs step start` with `--seed-next <n>` added.
- Parse the printed context JSON. Bind: `partition`, `ticket_id`, `ticket`,
  `requirements`, `settings`, `models`, `agents`, `reconcile`, `prior_status`,
  `handoff_summary`, `pipeline`, `post_hook`, `checkout_root`, `plugin_root`.
- **Requirements: `context.requirements` / `acs.py requirements show` — the
  request text, documents and an imported issue are only where they came
  from.** `step start` records every source `$ARGUMENTS` named — the prompt
  verbatim, each document (a repo path, or a file attached from outside the
  repo, copied into the run and hashed; PDFs and images are cited for you to
  Read) — in the run's `requirements.md` (`requirements.path`). Step 1 reads
  THAT, never a paraphrase of the arguments.
- **The ticket lives in the workspace and the tracker only** — no
  `docs/tickets/<ID>/` folder, no `ticket.md` in the repo (ADR-0128).

## Remote import

Decide BEFORE planning whether `$ARGUMENTS` is a remote key for
`settings.tracker.provider` (on `github`: `#123`, a bare integer or a GitHub
issue URL); when it is, read
`${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/remote-import.md`.
Otherwise it is not an import: the requirements (`requirements.path`) are the
request.

### GitHub call failure policy

`gh` is the only tracker transport this skill uses — no MCP-based transport, no second
credential path (ADR-0088). Three classes apply to every call below: **critical** (a gate
input this step cannot proceed without — gh's verbatim stderr plus ONE canonical hint from
`acs_lib.gh_failure_hint(stderr)`, then STOP, no fallback to any other transport),
**critical (per ticket), soft (per batch)** (Step 5's `gh issue create` only — an error
finding naming that ticket, `replayable: false`, but the batch continues to the next
ticket), and **non-critical** (metadata/best-effort — one `info` finding plus a replayable
command block, never abort). Canon hint text (`acs_lib.GH_ACCESS_HINT`, selected when the
stderr names a session-access restriction; `acs_lib.GH_GENERIC_HINT` otherwise):

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
  checklist (`gh label list`, `gh api …/milestones`, `gh project
  item-add` / `field-list` / `item-edit`) and an import's `acs.py tracker
  refresh` — one `info` finding, `replayable: true`, continue.

## References, and when to open each

| Open | When |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/authoring-rules.md` | Before Step 1b: the rules every type author follows and the reviewer judges against (acceptance criteria, PRD trace, features, grounding, the draft's keys). Read it again at Step 2 to present the draft. |
| `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/materialize.md` | Once Step 2's gate has closed: Steps 3-5, in order. |
| `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md` | `settings.tracker.provider` is `github`. It is Step 5, and `/acs:breakdown-ticket` reaches it through the same pointer. On the default `local` provider there is nothing to sync and the step does not run. |

## Resume & reconcile

If `context.reconcile` is true or `context.handoff_summary` exists, read
`${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/resume.md` and reconcile
BEFORE continuing; a fresh run skips it.

## The flow

Analyze and pick the type (Step 1, yours) → one type author drafts and the reviewer
judges (Step 1b, at most 2 iterations) → the user confirms the reviewed draft
(Step 2, yours) → you materialize it (Steps 3-5, `references/materialize.md`).
The schema enforces completeness, the reviewer the draft's quality, the
confirmation gate the record; the in-loop verifier gate (MAR-55 invariant (d))
belongs to the downstream code review.

### The sizing rubric

**One story, task or bug must equal ONE reviewable PR.** The ticket is the PR
boundary — all of its work lands on one branch — so size it for review,
grounded in a survey of the codebase: as a rule of thumb a story or task
should need roughly **≤400 changed lines**, touch **one concern**, and carry
**≤~7 acceptance criteria**. Estimate the expected diff surface (the
modules and files the survey turned up) and state it. Above the bar —
recommend `epic`; its children are cut at PR-sized seams later, by
`/acs:breakdown-ticket`. Never propose one mega-story
because decomposition is tedious.

### Step 1 — Analyze and recommend fields

The coordinator reads the requirements (`requirements.path` — the raw request,
the documents, or the imported remote issue), the codebase, the PRD, the roadmap
and — when the request names or traces to a PRD feature that has one — the
feature's living analysis (`<prd_dir>/features/<feature>/analysis/`, written by
`/acs:analyze-requirements` in Discovery — its `README.md` first, then only the
context files the request touches; a legacy single `analysis.md` whole). Decide,
before anyone drafts:

- `type`, judged against the sizing rubric: **bug** when the request reports
  existing behaviour that differs from what it should be (an error, a
  regression, "customers keep reporting …"); **epic** when the work exceeds one
  PR; **story** for a user-visible capability; **task** for technical work no
  user story describes. It is a recommendation about SHAPE, not a stored axis: a
  ticket carries no `size` or `stakes` field since ADR-0095, and how much rigor
  the work gets is judged later, from its plan, by `/acs:ship`.
- the PRD feature(s) it likely traces to, and whether it goes beyond the PRD;
- the questions the record genuinely needs answered (Step 2 item 1) — held for
  the ONE grouped interaction, never asked one at a time.

The author drafts the fields (`title`, `description`, `acceptance_criteria`,
`priority`, `story_points`, `features`, `prd_trace`, and its type's own); you
check its draft the way the reviewer does:

- Judge each proposed `acceptance_criteria` entry for concreteness/testability
  — an observable, checkable outcome versus vague satisfaction-claim
  boilerplate (e.g. "works correctly", "is better", "no bugs", "handles X
  properly") — and flag any non-concrete/non-testable entry as part of the
  proposal presented to the user in Step 2 (the author records them in `flags`).
- For epics: proposed child story/task breakdown — an OUTLINE only
  (`breakdown_outline`), drafted by the epic author and held to the same
  concreteness/testability judgment; it mints nothing. An epic's own creation
  run ends with `children: []`; `/acs:breakdown-ticket <id>` mints the children.

Ask BEFORE drafting only when the type itself is genuinely open (story or epic?
a bug or a new feature?) — it picks the author; everything else waits for Step 2.

### Step 1b — Draft and review: one type author, then the reviewer

At most **2 iterations**; one iteration is one author → reviewer round.

| Role | Kind | Agent | Spawn as |
|------|------|-------|----------|
| epic-author | write | `acs:create-ticket-epic-author` | `context.agents.epic-author` |
| story-author | write | `acs:create-ticket-story-author` | `context.agents.story-author` |
| task-author | write | `acs:create-ticket-task-author` | `context.agents.task-author` |
| bug-author | write | `acs:create-ticket-bug-author` | `context.agents.bug-author` |
| reviewer | judge | `acs:create-ticket-reviewer` | `context.agents.reviewer` |

Spawn with the Agent tool under the name in `context.agents.<role>` — the
plugin's `acs:create-ticket-<role>`, or the generated `acs-create-ticket-<role>`
copy `acs step start` wrote where `settings.models` sets a model or effort for it
(fall back to the un-namespaced name only if the runtime rejects the namespaced
one). Pass no model of your own; if the runtime rejects the agent, FAIL the run
with that exact error. Spawn in the foreground and wait on the result, never on a
clock. Pass `run_in_background: false`, and if the runtime moves an agent to the
background anyway, wait for its completion notification — never poll with `sleep`
loops. ONE author per run — the chosen type's — never two types side by side.

1. **Author.** `<task skill="create-ticket" phase="<type>-author"
   ticket-id="<id>" iteration="<n>">` with `<inputs>` (`requirements.md`, the PRD
   and roadmap when they exist, the feature analysis files Step 1 found,
   `references/authoring-rules.md`), `<constraint name="partition">`
   (`<partition>`), `<constraint name="template">` (the type's template:
   `<repo>/.acs/templates/<type>-default.md` when the repo has one, else
   `${CLAUDE_PLUGIN_ROOT}/templates/<type>-default.md`) and `<context>` (the
   ledger's `C-<n>` answers; on iteration 2 the reviewer's findings verbatim) and
   `<context name="references">`: the JSON of `acs.py ticket references --features
   <slugs> --fetch`, run once Step 1 knows the features (`[]` when it found none). It
   writes `steps/create-ticket/iter-<n>/draft.json`, `draft.md` and its
   `<type>-author.json` report, and mints nothing.
2. **Reviewer.** `<task skill="create-ticket" phase="reviewer" ticket-id="<id>"
   iteration="<n>">` with the draft, the author's report, the same sources and
   `<constraint name="type">` and the same references. It writes `iter-<n>/reviewer.md`.

**Pass rule.** The iteration passes when the reviewer returned
`status="completed"` with zero blocking findings. Findings → iteration 2, all of
them verbatim to the author. Still findings after iteration 2 → go to Step 2
anyway with the reviewed draft AND the remaining findings shown beside it: the
user revises or keeps each (a delegated run records each kept one as an
assumption). An author that returns `needs_input` → its questions join Step 2's
grouped ask; re-run it with the answers (that is its next iteration). An author
or reviewer that fails → status `failed`, its errors in the result.

A snapshot missing (a host that never fires SubagentStop) → write the `<task>`
and `<result>` to `iter-<n>/<role>-message.xml` yourself.

### Step 2 — User-confirmation gate (human-in-the-loop checkpoint)

**This step is a deliberate design requirement (MAR-55 invariant (c)) — it is NOT a
verifier and it is never skipped.** Present the reviewed draft (`draft.md`) and
every open point in ONE grouped interaction, and block until the user confirms or
overrides:

1. Resolve every ambiguity ABOUT THE TICKET RECORD with the user before
   finalizing — what the work is, which type it is, the author's
   `open_questions`, and the fields items 2-5 confirm. Deeper REQUIREMENTS
   clarification is not this skill's job: impact, assumptions, risks and refined
   acceptance criteria belong to `/acs:analyze-requirements <id>`, the first Build
   step. Ask here only what you need to write a well-formed ticket; park anything
   that needs the codebase read for the analysis, and say so.
2. **PRD divergence**: if the draft goes beyond the PRD, present the divergence,
   propose a follow-up `/acs:create-prd` re-run, and obtain explicit user
   confirmation to proceed (or stop at the user's choice). Record the confirmed
   divergence one-liner. Show the proposed `features`; the user's correction wins.
3. **AC/DoD substantiveness**: present every flagged `acceptance_criteria` entry,
   and every reviewer finding left after iteration 2, to the user. The user must
   either revise the entry or explicitly confirm keeping it as-is — the ticket
   does not finalize with a flagged entry unless the user explicitly confirms it
   anyway. A revision is applied to the draft before Step 3 (a substantive one
   re-runs the author within the iteration cap).
4. **Type and docs_only**: for `docs_only`, present the recommendation and obtain USER CONFIRMATION
   when recommended `true` (it relaxes /acs:code's TDD/coverage gates — never set it
   without explicit user confirmation; when `false`, don't ask). A bug's
   `severity` is shown beside its `priority`; the user may change either.
5. **Due date**: ask the user for an optional due date ("YYYY-MM-DD, or leave
   blank").
6. **References**: show the documents found (title, kind, link), each pending
   one marked `pending: not on <default> yet` — information, not a question.

No user to reach, or a request that delegates the record up front ("you
decide"): read `${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/headless.md`
before you hand off or continue — a delegation never confirms item 2.

### Step 3 — Rewrite ticket.json

You run this step inline, as `references/materialize.md` steps 1-3 order it:
`acs.py ticket save --ticket <id> --from -` rewrites `<partition>/ticket.json`
from the confirmed draft, its description built from the type's template; then
`acs.py ticket references --ticket <id> --write` stores its references.

### Step 4 — An epic's children are not minted here

No creation run mints a child: an epic ends with `children: []`, and
`/acs:breakdown-ticket <id>` mints them (`references/materialize.md` step 4).

### Step 5 — Tracker sync

Only when `settings.tracker.provider` is `github` — on `local` there is no
remote, so skip to Finish. When it applies, follow
`${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md`.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a /ship brief — with
`clarify.py add --skill create-ticket --question "..." --answer "..."`
BEFORE acting on it, and pass the relevant `C-n` entries to the author in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`). Pass a non-blank due date to the ticket
as `due_date`, and record that answer too.

Ask clarifying questions whenever the request is genuinely ambiguous (scope, type,
priority, acceptance criteria, PRD divergence) — use AskUserQuestion or plain
questions, and ask BEFORE finalizing, not after. Do not ask about things the
codebase or docs already answer. With no user to reach, see `references/headless.md`.

## Context pressure

If your context is running low mid-run, follow the context-pressure arm of
`references/resume.md`, then stop.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/create-ticket/result.json` through `acs.py write` (never the Write tool) per
   the result-document contract in INTERNALS.md. The `states` keys are EXACTLY: `ticket_id`,
   `type`, `children`, `prd_trace`. Example:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write steps/create-ticket/result.json <<'ACS_EOF'
   {
     "status": "completed",
     "summary": "epic created; reviewer passed on iteration 1; children deferred to /acs:breakdown-ticket",
     "states": {
       "ticket_id": "SHOP-123",
       "type": "epic",
       "children": [],
       "prd_trace": {"feature": "Wishlist (Must-have, roadmap M2)", "divergence": null}
     },
     "findings": [],
     "errors": []
   }
   ACS_EOF
   ```

   `children` is `[]` for every type **and for an epic's own creation run**: only
   `/acs:breakdown-ticket` mints children. `prd_trace.feature` is the PRD
   feature/goal the ticket traces to (null when no PRD exists);
   `prd_trace.divergence` is null or the user-confirmed divergence one-liner. On
   failure keep whatever is true and record blocking findings under `findings`
   with `severity: "blocking"`.

2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-ticket.py" --result-file "<the result.json you just wrote>"
   ```

3. Report. Direct invocation: a compact summary — ticket id, type, title,
   PRD trace, tracker key, a bug's severity — and the next command:
   for an epic, `/acs:create-tech-design <id>` (when you want a design) →
   `/acs:breakdown-ticket <id>`; else `/acs:code <id>` (epic children each continue with
   `/acs:code <child-id>`). Under /acs:ship: return
   ONLY the `<handoff>` XML as your final message (validated, summary <= 1 KB):

   ```xml
   <handoff skill="create-ticket" ticket-id="SHOP-123" status="completed">
     <summary>Created epic SHOP-123 "Wishlist"; draft reviewed on iteration 1; no children yet — break it down with /acs:breakdown-ticket SHOP-123; traced to PRD feature "Wishlist (Must-have)"; synced to github issue 789.</summary>
     <artifacts>
       <file><partition>/ticket.json</file>
       <file>steps/create-ticket/result.json</file>
     </artifacts>
     <next-step>/acs:breakdown-ticket SHOP-123</next-step>
   </handoff>
   ```

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-ticket · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: ticket id, type, title; a bug's severity; PRD trace or flagged divergence; reviewer iterations; references (each pending one marked); tracker key when synced; children none (an epic's are minted by `/acs:breakdown-ticket`)
- **Findings**: <open findings / clarifications / kept reviewer findings, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/2 · <wall time>
- **Next**: an epic: /acs:create-tech-design <id> (when you want a design) → /acs:breakdown-ticket <id>, then each child continues with `/acs:ship <child-id>`; a story, task or bug: `/acs:code <id>`
```
