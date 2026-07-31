---
name: docs-sync
description: Re-verify and complete the doc updates a ticket's changeset requires, after /acs:code (and /acs:test, when it ran) and before /acs:create-pr — independently re-derived from git diff <default_branch>...HEAD, /code's result.json, and the final code-verify artifact, never from a hand-off summary alone. Commits additional doc changes on the SAME ticket branch (no new branch, no new PR). Use once /acs:code has completed and before /acs:create-pr.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:docs-sync. Your job: independently re-derive
what documentation the ticket's changeset requires and commit any missing or
incorrect doc updates as additional commits on the SAME ticket branch that
`/acs:code` and `/acs:create-pr` use — never a new branch, never a second PR.
You orchestrate planner/executor/verifier subagents over XML; you never write
doc content yourself.

`/code`'s own step 4 no longer authors general doc updates — it only
reconciles factual claims in `docs/product/prd.md`/`docs/product/roadmap.md`
(MAR-65). This skill is now the sole producer of README/API/usage/
architecture/living-requirements/ADR doc updates for a ticket's changeset,
diff-grounded and running after code (and test) settle.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill docs-sync --args "$ARGUMENTS"
```

- If it exits non-zero: STOP and surface its stderr verbatim to the user. Do
  not improvise a workaround.
- Parse the printed context JSON. Fields you will use: `partition`, `ticket`,
  `ticket_id`, `settings`, `models`, `reconcile`, `handoff_summary`,
  `pipeline`, `post_hook`, `checkout_root`.

Throughout this file `<partition>` means the `partition` path from the
context JSON and `<id>` means `ticket_id` (e.g. `SHOP-123`).

**Branch confirmation (hard precondition).** Read the current git branch in
`<checkout_root>` and confirm it matches the ticket's recorded branch — read
`states.branch` from `<partition>/phases/code/result.json`, or the `branch`
recorded in `<partition>/pipeline-state.json`. docs-sync NEVER creates a
branch and NEVER opens a PR; it always operates on the SAME ticket branch
`/code`/`/create-pr` use, adding commits to the existing changeset (same
PR/review). A mismatch is a fail-fast error — stop and surface it; never
silently switch branches.

## Resume & reconcile

- If `context.reconcile` is true (prior run `in_progress`/`failed`/
  `interrupted`/`handed_off`): verify recorded progress against reality
  BEFORE continuing — list `<partition>/phases/docs-sync/iter-*-*.xml`,
  re-read `<partition>/docs-sync-state.json` if it exists, and check whether
  its `states.docs_committed`/`commits` actually match `git log` on the
  branch. Continue from the first unfinished phase/iteration; never redo
  work that demonstrably holds.
- If `context.handoff_summary` exists: read it plus
  `<partition>/phases/docs-sync/handoff-context.md` (when present), do a
  light reconcile, and continue from where it points.
- Fresh run (`reconcile` false): start at iteration 1, plan phase.

## Inputs — gather before planning

The planner's `<task>` `<inputs>` MUST literally enumerate, and the planner
MUST read, exactly these artifacts — never a bare hand-off summary:

1. `git diff <default_branch>...HEAD` on the ticket branch (the ground-truth
   changeset) — run from `<checkout_root>`.
2. `<partition>/ticket.json` (title, description, acceptance criteria).
3. `<partition>/phases/code/result.json`, specifically `states.docs_updated`
   (repo-relative paths of every doc file `/code` already changed).
4. The ticket's `<partition>/phases/code/iter-<n>-execute.json` execute
   report(s), specifically the `problems` field.
5. The final `<partition>/phases/code/iter-<n>-verify.md` (the last
   code-verifier artifact for the highest completed iteration).
6. The ticket's binding design (`<partition>/design.md`, or the parent
   epic's when the ticket inherits it) when `ticket.needs_design` is true or
   a parent design applies; absent otherwise.

`docs_updated`/`problems` may legitimately be near-empty for doc categories
`/code` no longer touches — reading them still tells docs-sync what `/code`'s
retained MAR-65 step 4 changed and any recorded doc-related friction
(including Boy-scout drift items carried verbatim from the code planner);
re-deriving from the live diff (input 1) remains docs-sync's own grounding
for every other doc category. Neither input substitutes for the other —
every phase (planner, executor, and verifier alike) reads all six,
independently.

## Reflection loop

Run plan → execute → verify, max 3 iterations. Decomposition is YOURS alone —
subagents never spawn subagents.

For every phase:

1. Compose a `<task>` per `schemas/acs-messages.xsd`, with `<inputs>` listing
   the six artifacts above by path.
2. Validate EVERY message you send and receive:

   ```bash
   echo "<xml>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
   ```

   On an invalid message from a subagent: re-request once with the
   validation error quoted; still invalid → fail the run, recording the
   error in `errors`.
3. Spawn the subagent with the Agent tool, `subagent_type` as below (fall
   back to the un-namespaced name only if the runtime rejects the
   namespaced one). Apply `context.models.<role>.model` / `.effort` at spawn
   when not `"inherit"`; if the runtime rejects the model or effort, FAIL
   the run with that exact error — no silent fallback.
4. Persist the phase's `<task>` and `<result>` to
   `<partition>/phases/docs-sync/iter-<n>-<phase>.xml` at the phase
   boundary, BEFORE starting the next phase.

### Phase: plan — `acs:docs-sync-planner`

Objective: from the six inputs above, produce a doc-delta plan in its
`<result>` — which doc files need which specific changes and why, each
cross-referenced to the diff lines / `docs_updated` entries / `problems`
entries that justify it. No file writes.

### Phase: execute — `acs:docs-sync-executor`

Objective: apply the planned doc updates as additional commits on the SAME
ticket branch (never a new branch, never a new PR), rendered with the same
`commit_message` format `/code` already uses. Author the doc-delta report
using the FIXED v1 structure — the existing `iter-<n>-plan.md` /
`iter-<n>-execute.json` / `iter-<n>-verify.md` artifact triad every hooked
skill already writes. No new artifact type, no settings-driven template, no
new `settings.schema.json` keys.

### Phase: verify — `acs:docs-sync-verifier`

Spawned fresh (sees artifacts, never the executor's reasoning); re-derives
doc impact from the same six-input contract itself (not exempt from the
independent-re-derivation rule) and checks each committed doc change is
accurate, complete against the diff, and consistent with `docs_updated` /
`problems` / the final verify.md. ALL findings block; zero findings = pass.
On findings: persist, feed into next iteration's plan `<task>` as
`<context>`, re-run. After iteration 3 with findings remaining: stop, final
status `failed`.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction, not serial round-trips. Record each answer as its own
`clarify.py add` entry (one `C-<n>` per question, `--source` preserved).
Never skip a question, merge two questions into one entry, or auto-answer a
question outside the existing `--source assumption --rationale "..."` rule.
Record every Q&A with
`clarify.py add --skill docs-sync --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."`. Before a needs_input
handoff, record the outgoing questions as `open` (`clarify.py add` without
`--answer`).

The doc-delta plan's own `<questions>` (a planner uncertain whether a doc
change is in scope, or which of two conflicting docs is authoritative) go
through this same ledger-first path before the coordinator settles them and
carries the answer into the execute `<task>` via `<context>`.

## Context pressure

If your context is running low mid-run: flush in-flight work and soft
context to `<partition>/phases/docs-sync/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, including on failure or handoff:

1. Write `<partition>/phases/docs-sync/result.json` per the result-document
   contract in INTERNALS.md. Canonical `states` keys (EXACT names) on
   success:

   ```json
   {
     "status": "completed",
     "stop_reason": "verifier passed with zero findings on iteration 1",
     "states": {
       "docs_committed": ["docs/api/import.md", "README.md"],
       "commits": ["a1b2c3d SHOP-123 sync API doc for the new 409 response"],
       "review": {"iterations": 1, "findings_open": 0}
     },
     "findings": [],
     "errors": [],
     "tokens": {"input": 60000, "output": 12000},
     "cost_usd": 0.35
   }
   ```

   `docs_committed`: repo-relative paths of every doc file docs-sync itself
   changed, mirroring `/code`'s `docs_updated` naming. `commits`: short SHA +
   message list of the additional commits docs-sync made. `review`:
   `{iterations, findings_open}`. On `failed`: keep whatever is true, put the
   verifier's blocking findings in `findings`, and the reason in
   `stop_reason`.

2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-docs-sync.py" --ticket <id> --result-file <partition>/phases/docs-sync/result.json
   ```

   If it exits non-zero, surface its stderr verbatim — the `/acs:create-pr`
   gate stays closed until it succeeds.

3. Report:
   - Direct invocation: a compact summary — doc files committed, commits
     made, iterations used, and the next step (`/acs:create-pr <id>`).
   - Under /acs:ship: return ONLY the `<handoff>` XML as your final message —
     `status` matching result.json, `<summary>` <=1KB, `<artifacts>`
     referencing the committed doc paths, `<next-step>/acs:create-pr
     <id></next-step>`. Validate it with validate_xml.py like every other
     message.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your
final message is the `<handoff>` XML instead — this report is for direct
invocations:

```markdown
## /acs:docs-sync · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: doc files committed; commits made; review iterations and open findings
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch>
- **Metrics**: iterations <n>/3 · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:create-pr <ticket-id>`
```
