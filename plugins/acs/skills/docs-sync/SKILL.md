---
name: docs-sync
description: Re-verify and complete the doc updates a ticket's changeset requires — independently re-derived from git diff <default_branch>...HEAD, /code's result.json, and the final code-verify artifact, never from a hand-off summary alone. Commits additional doc changes on the SAME ticket branch (no new branch, no new PR).
when_to_use: Use when a ticket has a changeset on its branch whose documentation still needs reconciling; workflows/ship.yaml places it after code and before create-pr, but it is runnable on its own whenever the docs have drifted from the diff.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:docs-sync. Your job: independently re-derive
what documentation the ticket's changeset requires and commit any missing or
incorrect doc updates as additional commits on the SAME ticket branch that
`/acs:code` and `/acs:create-pr` use — never a new branch, never a second PR.
You orchestrate executor/verifier subagents over XML — execute → verify, no
planner (ADR-0092); you never write doc content yourself.

`/code`'s own step 4 no longer authors general doc updates — it only
reconciles factual claims in `docs/product/prd.md`/`docs/product/roadmap.md`
(MAR-65). This skill is now the sole producer of README/API/usage/
architecture/living-requirements/ADR doc updates for a ticket's changeset,
diff-grounded and best run once code (and the post-code test step) settle.

**What the pre-hook checks (and what it no longer checks).**
`pre-docs-sync.py` gates on this skill's INPUTS and one safety brake only:
settings resolve, the ticket resolves to a live, unlocked partition. It no
longer refuses because `/acs:code` — or the post-code test step — has not
recorded a completed run: pipeline order lives in `workflows/ship.yaml`, not in
the gate, so docs-sync is runnable on its own against whatever the branch
already holds. Run out of that declared order, the pre-hook prints ONE advisory
line on stderr (`acs: docs-sync normally follows code in ship.yaml; code has not
completed for <id>`) and lets the skill run. The real precondition is a
CHANGESET: with no diff against the default branch there is nothing to
re-derive, and step 1 below is where you find that out and stop.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step docs-sync
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
`states.branch` from `steps/code/result.json`, or the `branch`
recorded in `<partition>/run.json`. docs-sync NEVER creates a
branch and NEVER opens a PR; it always operates on the SAME ticket branch
`/code`/`/create-pr` use, adding commits to the existing changeset (same
PR/review). A mismatch is a fail-fast error — stop and surface it; never
silently switch branches.

## Resume & reconcile

- If `context.reconcile` is true (prior run `in_progress`/`failed`/
  `interrupted`/`handed_off`): verify recorded progress against reality
  BEFORE continuing — list `steps/docs-sync/iter-*-*.xml`,
  re-read `<partition>/docs-sync-state.json` if it exists, and check whether
  its `states.docs_committed`/`commits` actually match `git log` on the
  branch. Continue from the first unfinished phase/iteration; never redo
  work that demonstrably holds.
- If `context.handoff_summary` exists: read it plus
  `steps/docs-sync/handoff-context.md` (when present), do a
  light reconcile, and continue from where it points.
- Fresh run (`reconcile` false): start at iteration 1, execute phase.
- There is no plan artifact to reuse: an execute with no verify → verify it;
  a verify with findings and no later execute → execute with those findings
  as `<context>`. The executor's authoring notes (`iter-<n>/authoring.md`)
  belong to their iteration.

## Inputs — gather before the loop

The executor's `<task>` `<inputs>` MUST literally enumerate, and the executor
MUST read, exactly these artifacts — never a bare hand-off summary:

1. `git diff <default_branch>...HEAD` on the ticket branch (the ground-truth
   changeset) — run from `<checkout_root>`.
2. `<partition>/ticket.json` (title, description, acceptance criteria).
3. `steps/code/result.json`, specifically `states.docs_updated`
   (repo-relative paths of every doc file `/code` already changed).
4. The ticket's `steps/code/iter-<n>/execute.json` execute
   report(s), specifically the `problems` field.
5. The final `steps/code/iter-<n>/verify.md` (the last
   code-verifier artifact for the highest completed iteration).
6. The ticket's binding design (`<partition>/design.md`, or the parent
   epic's when the ticket inherits it) when `ticket.needs_design` is true or
   a parent design applies; absent otherwise.

`docs_updated`/`problems` may legitimately be near-empty for doc categories
`/code` no longer touches — reading them still tells docs-sync what `/code`'s
retained MAR-65 step 4 changed and any recorded doc-related friction
(including Boy-scout drift items carried verbatim from the implementation plan);
re-deriving from the live diff (input 1) remains docs-sync's own grounding
for every other doc category. Neither input substitutes for the other —
every phase (executor and verifier alike) reads all six, independently.

**Constraints the task carries.** Every placeholder the executor's and the
verifier's charters read comes from the `<task>`'s `<constraints>`, and only
names in the `constraintName` vocabulary of `the SubagentStop hook's message check`
validate — never invent a variant such as `commit_message_format` or
`contracts_root`. Pass, on every phase:

```xml
<constraints>
  <constraint name="partition">/abs/workspace/owner-repo/SHOP-123</constraint>
  <constraint name="checkout_root">/abs/path/to/the/checkout</constraint>
  <constraint name="branch">task/SHOP-123-add-user-login</constraint>
  <constraint name="default_branch">main</constraint>
  <constraint name="commit_message">{ticket_id} {summary}</constraint>
  <constraint name="requirements_dir">docs/requirements</constraint>
  <constraint name="functional_dir">docs/requirements/functional</constraint>
  <constraint name="non_functional_dir">docs/requirements/non-functional</constraint>
</constraints>
```

`checkout_root` is `context.checkout_root`; `branch` is the ticket branch
confirmed above; `default_branch` is the base the diff is taken against;
`commit_message` is `settings.formats.commit_message`; the requirements
trio is the requirements set and its functional and non-functional
subfolders. Add the other document locations the executor's charter names —
`architecture_dir` and `adr_dir` — each as its own `<constraint>` under that
exact name.

Locate every one of them once, before the loop, the way any session finds a
document: CLAUDE.md and whatever docs index it or the repo points at (e.g.
`docs/README.md`), then a Glob/Grep by file name or content. Found → that
repo-relative location. Not found → the conventional default, where a doc
update would create it: `docs/requirements/` with `functional/` and
`non-functional/` subfolders (an existing set's own subfolder names are
followed), `docs/architecture/`, `docs/adr/`.

## Reflection loop — execute → verify, no planner

The loop is execute → verify, max 3 iterations. There is no plan phase:
iteration 1's executor re-derives the doc impact from the six inputs, writes
its authoring notes (the doc-delta list, each item justified by the diff),
and commits the doc updates from them; the verifier re-derives the impact
itself and judges the result fresh. On iterations 2-3 the verifier's
findings go verbatim into the next executor `<task>` `<context>` and the
executor authors the remediation. Decomposition is YOURS alone — subagents
never spawn subagents.

**What an iteration counts:** one execute → verify round. docs-sync has no
path-driven verify-depth selection: the cap is a fixed 3 on every run, and
this ticket does not introduce one.

For every phase:

1. Compose a `<task>` per `the SubagentStop hook's message check`, with `<inputs>` listing
   the six artifacts above by path.
2. Validate EVERY message you send and receive:

   ```bash
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
   `steps/docs-sync/iter-<n>/<phase>.json` at the phase
   boundary, BEFORE starting the next phase. The executor's own artifacts
   are `iter-<n>/authoring.md` (Diff analysis; Doc-delta list; Cross-check
   against docs_updated/problems; Open questions) and
   `iter-<n>/execute.json`; every iteration's verifier `<inputs>` name that
   iteration's authoring notes.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

### Phase: execute — `acs:docs-sync-executor`

Objective, iteration 1: from the six inputs above, record the doc-delta
list in the authoring notes — which doc files need which specific changes
and why, each cross-referenced to the diff lines / `docs_updated` entries /
`problems` entries that justify it — and then apply those doc updates as
additional commits on the SAME
ticket branch (never a new branch, never a new PR), rendered with the same
`commit_message` format `/code` already uses. Author the doc-delta report
using the FIXED v1 structure — the existing `iter-<n>/execute.json` /
`iter-<n>/verify.md` artifact shape every hooked skill already writes
(`/acs:create-impl-plan`, which carved the plan phase out of `/acs:code`,
publishes `plan.md`; every other authoring skill's executor writes its
`iter-<n>/authoring.md`). No new artifact type, no settings-driven template,
no new `settings.schema.json` keys.

If the executor returns `needs_input` with `<questions>` (which of two
conflicting docs is authoritative, whether a doc edit is in scope), resolve
them in User interaction and re-run execute for the same iteration with the
answers in `<context>`.

### Phase: verify — `acs:docs-sync-verifier`

Spawned fresh (sees artifacts, never the executor's reasoning); re-derives
doc impact from the same six-input contract itself (not exempt from the
independent-re-derivation rule) and checks each committed doc change is
accurate, complete against the diff, and consistent with `docs_updated` /
`problems` / the final verify.md. ALL findings block; zero findings = pass.
On findings: persist, then AUTOMATICALLY re-execute, passing every finding
to the next iteration's executor `<task>` as `<context>`, with no plan
phase in between — the executor authors the remediation. After iteration 3
with findings remaining: stop, final status `failed`.

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

The executor's own `<questions>` (uncertain whether a doc change is in
scope, or which of two conflicting docs is authoritative) go
through this same ledger-first path before the coordinator settles them and
carries the answer into the execute `<task>` via `<context>`.

## Context pressure

If your context is running low mid-run: flush in-flight work and soft
context to `steps/docs-sync/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, including on failure or handoff:

1. Write `steps/docs-sync/result.json` per the result-document
   contract in INTERNALS.md. Canonical `states` keys (EXACT names) on
   success:

   ```json
   {
     "status": "completed",
     "summary": "verifier passed with zero findings on iteration 1",
     "states": {
       "docs_committed": ["docs/api/import.md", "README.md"],
       "commits": ["a1b2c3d SHOP-123 sync API doc for the new 409 response"],
       "review": {"iterations": 1, "findings_open": 0}
     },
     "findings": [],
     "errors": []
   }
   ```

   `docs_committed`: repo-relative paths of every doc file docs-sync itself
   changed, mirroring `/code`'s `docs_updated` naming. `commits`: short SHA +
   message list of the additional commits docs-sync made. `review`:
   `{iterations, findings_open}` — to which the post-hook's derivation may add
   `guard_denials` when the file-map guard denied a write during THIS run
   (the derivation reads `steps/<skill>/state.json` for every step,
   docs-sync's own included); never write that key yourself, and a run that
   tripped nothing carries no key at all. On `failed`: keep whatever is true,
   put the verifier's blocking findings in `findings`, and the reason in
   `summary`.

2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-docs-sync.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — until it succeeds the
   run stays un-finalized in the ledger, so `acs.py run next` keeps
   offering docs-sync instead of moving on.

3. Report:
   - Direct invocation: a compact summary — doc files committed, commits
     made, iterations used, and the next step (`/acs:create-pr <id>`).
   - Under /acs:ship: return ONLY the `<handoff>` XML as your final message —
     `status` matching result.json, `<summary>` <=1KB, `<artifacts>`
     referencing the committed doc paths, `<next-step>/acs:create-pr
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
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: doc files committed; commits made; review iterations and open findings
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:create-pr <ticket-id>`
```
