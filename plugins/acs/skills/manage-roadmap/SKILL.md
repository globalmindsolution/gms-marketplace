---
name: manage-roadmap
description: Plan, re-plan and track the product roadmap — milestones each with its release version, the PRD features it delivers and the epics behind it, and each milestone's delivery status derived from its tickets — left as local changes for /acs:create-pr to commit and open as a PR. Use once a PRD exists and the team needs a roadmap, when a scope change (a feature cut, added or reprioritized in the PRD) moves milestones or versions, when a milestone is added, moved or re-scoped, or to see how far each milestone is delivered. Invoke it directly on such a request — it confirms the plan and gathers what it needs from the user itself, so there is nothing to ask before running it.
argument-hint: "[status] [roadmap change | re-plan request]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:manage-roadmap. You own the product roadmap,
`roadmap.md` beside the PRD hub (ADR-0145): its milestones, the Release
versions table that gives each milestone its one version, the features and
epics each milestone delivers, and each milestone's delivery status. No other
skill writes it — `/acs:create-prd` defines the features, this skill schedules
them. It is a **ticketless run** and the document stays an uncommitted change
in the working tree: no ticket, no branch, no commit, no PR (ADR-0127).
`/acs:create-pr "<what changed>"` commits it and opens the PR when the user is
ready.

You orchestrate three subagents — surveyor → author → reviewer — and never
write the roadmap's content yourself. The one change you make to it directly is
the delivery status, and only through `acs.py roadmap status --write`: status is
**derived** from the tickets, never asserted by you or an agent.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step manage-roadmap --args "$ARGUMENTS"
```

A roadmap run needs no ticket: `step start` opens a run over the invocation —
or resumes this checkout's interrupted manage-roadmap run — and the post-hook
concludes it. If `acs step start` exits non-zero: STOP and surface its stderr
verbatim.

Parse the printed context JSON. Key fields: `partition`, `run_id`, `settings`,
`agents` (agent name to spawn per role), `reconcile`, `handoff_summary`,
`checkout_root`. The request — the prompt and any documents `$ARGUMENTS` named —
is recorded in the run's `requirements.md` (`requirements.path`).

Then locate the PRD the way any session finds a document: CLAUDE.md and the
docs index it points at, a Glob for `prd.md`, else
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs where --doc living:prd`.
`<prd>` is the hub `prd.md`, `<prd_dir>` its folder, `<roadmap>` is
`<prd_dir>/roadmap.md`, `<features_dir>` is `<prd_dir>/features`.

**No PRD, no roadmap.** When no hub `prd.md` exists, the roadmap has no
features to schedule: write nothing, and go straight to Finish with status
`failed`, summary `no PRD to plan a roadmap from`, and Next
`/acs:create-prd` — a roadmap is never invented ahead of the product it plans.

## Resume & reconcile

If `context.reconcile` is true, or `context.handoff_summary` exists, read
`${CLAUDE_PLUGIN_ROOT}/skills/manage-roadmap/references/resume.md` and
reconcile BEFORE continuing; a fresh run skips it.

## Modes

Classify from the request and the tree, then confirm in the survey:

- **status** — the request only asks where delivery stands (`status`, "how far
  are we", "refresh the roadmap status"), and `<roadmap>` exists. Run Status
  below and nothing else: no agent, no clarification, no version change.
- **create** — `<roadmap>` does not exist.
- **amend** — `<roadmap>` exists and the user names the change: a milestone
  added, moved to another version, re-scoped, re-targeted or cut.
- **replan** — `<roadmap>` exists and the PRD moved under it (a feature cut,
  added or re-prioritised: the floor's `must-unscheduled`, `wont-scheduled` or
  `feature-unknown`), or the user asks to re-plan.

A status request with no `<roadmap>` is a create run: say so in the grouped ask.

## Status — the derived delivery status

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" roadmap status --roadmap "<roadmap>" --write
```

It reads the tickets each milestone tracks — its epics, and every ticket whose
`features` names one of its features — from the tickets index and the default
branch's history (a ticket id leading a merged commit subject is delivered),
and rewrites only each milestone's `Status:` line and its Release versions
cell: `delivered` when every tracked ticket is done, `in progress` when any has
started, `planned` otherwise. It prints `milestones` (each `name`, `version`,
`status`, `was`, `tickets`) and `changed`. A status refresh is not a new
version of the roadmap: its front matter does not move. A `status` run then
goes to Finish, `states.files` listing `<roadmap>` only when `written` is true.

## Reflection loop — surveyor → author → review

create, amend and replan run surveyor → author → review, max 3 iterations. One
iteration is one author → review round; the survey belongs to iteration 1 and
never re-runs — its notes are the fixed baseline every iteration is judged
against.

| Role | Kind | Agent | Spawn as |
|------|------|-------|------------|
| surveyor | survey | `acs:manage-roadmap-surveyor` | `context.agents.surveyor` |
| author | write | `acs:manage-roadmap-author` | `context.agents.author` |
| reviewer | judge | `acs:manage-roadmap-reviewer` | `context.agents.reviewer` |

Spawn subagents with the Agent tool, `subagent_type`
`acs:manage-roadmap-<role>` (fall back to the un-namespaced name only if the
runtime rejects the namespaced one), under the name in `context.agents.<role>` —
the plugin's agent, or the generated `acs-manage-roadmap-<role>` copy
`acs step start` wrote where `settings.models` sets a model or effort for it.
Model and effort travel with that agent, so pass none of your own. If the
runtime rejects the agent, FAIL the run with that exact error — no silent
fallback. Decomposition is YOURS alone — subagents never spawn subagents.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false`: the phase's `<result>` is your next input. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops.

Every message follows `the SubagentStop hook's message check`; the `phase=` of
each task and result is the role. On an invalid message, re-request once with
the error quoted; still invalid → fail the run with it in `errors`. The hook
snapshots each returned message to `steps/manage-roadmap/iter-<n>/<role>-message.xml`
at the phase boundary; if the snapshot is missing (a host that does not fire the
hook), write the `<task>` and `<result>` there yourself, through `acs.py write`.

Read `${CLAUDE_PLUGIN_ROOT}/skills/manage-roadmap/references/roadmap-shape.md`
(the document) and `${CLAUDE_PLUGIN_ROOT}/skills/manage-roadmap/references/authoring-notes.md`
(the notes) before the first spawn.

### Survey — iteration 1 only

Every task's `<constraints>` carry `partition`, `prd`, `roadmap`,
`features_dir`, the mode and `repo_root`; its `<context>` carries `$ARGUMENTS`
and the ledger's recorded answers (`C-<n>`). Example:

```xml
<task skill="manage-roadmap" phase="surveyor" iteration="1">
  <objective>Confirm the mode (create/amend/replan) with evidence; read the PRD hub's Features index and each feature PRD, the existing roadmap, the tickets index and the derived delivery status (acs.py roadmap status, without --write); record the roadmap outline, the milestone lines, the answer-fidelity lines and the open questions in the authoring notes; write no repo file.</objective>
  <inputs>
    <file>/abs/repo/docs/product/prd.md</file>
    <file>/abs/repo/docs/product/roadmap.md</file>
    <file>/abs/workspace/acme-shop/runs/acs-manage-roadmap-cut-deposits-7c1e/requirements.md</file>
  </inputs>
  <constraints>
    <constraint name="partition">/abs/workspace/acme-shop/runs/acs-manage-roadmap-cut-deposits-7c1e</constraint>
    <constraint name="prd">docs/product/prd.md</constraint>
    <constraint name="roadmap">docs/product/roadmap.md</constraint>
    <constraint name="features_dir">docs/product/features</constraint>
    <constraint name="mode">replan</constraint>
    <constraint name="repo_root">/abs/repo</constraint>
    <constraint name="amend_rule">milestones the change does not touch are preserved byte-for-byte</constraint>
  </constraints>
  <context>$ARGUMENTS; recorded clarification answers.</context>
</task>
```

The surveyor also runs the shared ADR-0012 design-time doc-consistency step
over the PRD and the roadmap; its findings surface through the clarification
ledger below. It returns `needs_input` with its open questions in
`<questions>`, or `completed` when nothing is open — and even then you confirm
the plan with the user before the author runs (User interaction).

### Author

Spawn the author (`phase="author"`) with the notes, `clarifications.json`, the
PRD hub, the existing roadmap and the user's answers in `<context>`. It writes
`<roadmap>` to `roadmap-shape.md` — a new milestone `planned`, no status
asserted — completes the notes' `## Answer fidelity` and `## Roadmap
milestones` against the text it wrote, and in amend/replan mode preserves every
milestone the notes mark `kept` byte-for-byte. Should it return `needs_input`,
ask the user and re-run it for the same iteration with the answer in `<context>`.
On iterations 2-3 the reviewer's and the floor's findings go verbatim into its
`<context>`.

### After every author result — status, then version

1. Run Status above (`roadmap status --write`), so every milestone's status is
   the derived one before anything judges it.
2. Version (ADR-0122, ADR-0130) — set ONLY by you, through `acs.py design`,
   never by the author and never by hand. Before the first author spawn, record
   where the run started, unless the file already exists (a resume):
   `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design check "<roadmap>" > <partition>/steps/manage-roadmap/version-before.json`
   (no roadmap yet: write `{"ok": true, "files": []}` there through `acs.py
   write`). After the author: a roadmap that is new or has no block →
   `acs.py design init --status proposed "<roadmap>"`; one whose plan changed
   and whose version still equals `version-before.json`'s →
   `acs.py design bump "<roadmap>"` (version + 1, re-opened `proposed`; one run
   is one version). `bump` refuses a `deprecated` roadmap: fail the run with that
   error. A run whose only change is the status refresh moves no version.

### Review — the floor, then the reviewer

The floor is yours, every iteration, recorded in `iter-<n>/floor.md` through
`acs.py write`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/roadmap_check.py" --roadmap "<roadmap>" --prd "<prd>" \
  --plan <partition>/steps/manage-roadmap/iter-<n>/authoring.md --mode <create|amend|replan> \
  --clarifications <partition>/clarifications.json [--added-heading "<heading>" ...]
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design check "<roadmap>"
```

In amend/replan mode pass one `--added-heading` per `+### ` line `git diff --
"<roadmap>"` adds (heading text without the `###`); omit it in create mode.
Every stderr `source:line: [rule] message` is a blocking finding; exit 2 is
itself one. Each `design check` problem is one too.

Then spawn the reviewer (`phase="reviewer"`) with ONLY artifact references —
`<roadmap>`, `<prd>`, the notes, `clarifications.json`, `iter-<n>/floor.md`, and
the git diff in amend/replan mode — never the author's reasoning. It judges
fresh what no script can: each milestone's paragraph is true to the PRD, the
order and grouping are coherent (a feature never ships before one it depends
on), the plan honours the answers and the Constraints and Out of scope of the
PRD, versions follow one another, and in amend/replan mode only the intended
milestones changed.

Zero findings from the floor and the reviewer = pass → Delivery. Otherwise route
every finding verbatim into the next author `<context>` and run author → review
again. After iteration 3 with findings remaining: STOP — status `failed`,
findings recorded; go to Finish (the file stays in the working tree as it is).

## Delivery

Only after the review passes. The roadmap stays local: no branch, no commit, no
push, no PR — whichever branch is checked out (ADR-0127). Record `<roadmap>`,
repo-relative, in result `states.files`, and point the user at
`/acs:create-pr "<what the roadmap change is>"` (e.g.
`/acs:create-pr "Roadmap: move deposits to v0.3.0"`).

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list` and reuse any
recorded answer — re-asking an answered question is a defect. When ≥2
clarifications are open, present them in ONE grouped interaction (a single
AskUserQuestion listing every open question), not serial round-trips. Record
each answer as its own `clarify.py add` entry (one `C-<n>` per question,
`--source` preserved) — `clarify.py add --skill manage-roadmap --question "..."
--answer "..."` — BEFORE acting on it, and pass the relevant `C-n` entries to
subagents in `<context>`. Never skip a question, merge two questions into one
entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule: if the user is unavailable or
says "you decide", record the decision that way — assumptions surface in the
completion report's Findings until a user confirms. Before a needs_input
handoff, record the outgoing questions as `open` (`clarify.py add` without
`--answer`).

- **create**: propose the milestone cut from the PRD's priorities (Must-haves
  first) and confirm it — the order, the versions, any target date. Never
  invent a date.
- **amend**: confirm exactly which milestones change and why.
- **replan**: show what the PRD change does to the plan (the floor's findings
  against the current roadmap) and confirm the new cut.
- **status**: no question.
- If you genuinely cannot reach the user (a non-interactive run), return a
  `<handoff skill="manage-roadmap" status="needs_input">` with `<questions>`
  instead of guessing.

## Context pressure

If your context is running low mid-run: flush in-flight work and soft context
(answers, decisions, partial findings) to
`steps/manage-roadmap/handoff-context.md`, then run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next / decisions>"
```

and tell the user the printed `continue_with` command. Never burn the last of
the context on work that would be lost.

## Finish

MANDATORY final step — never skipped, also on failure.

1. Write `steps/manage-roadmap/result.json` through `acs.py write` (never the
   Write tool) per the result-document contract (INTERNALS.md), with the
   canonical `states` keys — `roadmap` and `files`, exact names:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write steps/manage-roadmap/result.json <<'ACS_EOF'
   {
     "status": "completed",
     "summary": "Roadmap re-planned and reviewed; left as a local change",
     "states": {
       "roadmap": {"path": "docs/product/roadmap.md", "mode": "replan"},
       "files": ["docs/product/roadmap.md"]
     },
     "findings": [],
     "errors": []
   }
   ACS_EOF
   ```

   On failure keep whatever is true: status `failed`, remaining findings in
   `findings`, the file in `states.files` if it was written, the reason in
   `summary`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-manage-roadmap.py" --result-file "<the result.json you just wrote>"
   ```

   It finalizes the step, concludes the run `step start` opened, and releases
   the `.lock`.

3. Report a compact summary: the mode, each milestone with its version and
   derived status, and the uncommitted file. Under /acs:ship, return ONLY the
   `<handoff>` XML as your final message: status, summary <=1KB, artifact refs,
   next-step.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your
final message is the `<handoff>` XML instead:

```markdown
## /acs:manage-roadmap · <mode> · <status>

- **Ticket**: none — a ticketless run; the roadmap is delivered by `/acs:create-pr`
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: `<roadmap>` with its status and version (`proposed v<n>`, or unchanged for a status refresh), and each milestone `<name> — v<x.y.z> — <derived status>`, left as an uncommitted change (`states.files`)
- **Findings**: <open findings / assumptions, or "none">
- **Artifacts**: <partition files; the uncommitted repo path>
- **Metrics**: iterations <n>/<cap> (0 for a status refresh) · <wall time>
- **Next**: review the file, then `/acs:create-pr "<what the roadmap change is>"`; once the team approves it, `/acs:set-doc-status approved roadmap`; `/acs:create-ticket` for a milestone's epic that is `none yet`
```
