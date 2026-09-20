---
name: ship
description: Umbrella command that drives the delivery pipeline declared in workflows/ship.yaml for one ticket — running every ready step, fanning independent steps out in parallel, always stopping before merge. Use when the user wants a ticket shipped end-to-end with one command, or wants to resume a ticket's pipeline from where it left off.
argument-hint: "<ticket-id>"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:ship — the umbrella command that drives the
delivery pipeline end-to-end for ONE ticket. You orchestrate; you never
implement, and you never decide the order.

Ground rules, non-negotiable:

- **The order is not yours.** It is declared in `workflows/ship.yaml` — the
  consumer's `.acs/workflows/ship.yaml` when present, else the plugin default
  — and computed for this ticket by `acs.py run next`. You never
  hard-code a step sequence, never skip a step the walk offers, and never
  invent one it does not. Every skill name in this file is an example of a
  mechanism, never the pipeline itself: read the pipeline from the walk.
- /acs:ship is NOT a hooked skill, but **every step it invokes IS gated** by
  pre/post hooks (the `PreToolUse` hook fires on the Skill tool whenever you
  invoke a step skill directly). You add orchestration only — never bypass,
  simulate, or work around a hook.
- A step skill's pre-hook checks that skill's own **inputs** and **safety
  brakes**, not its position: a skill run ahead of ship.yaml's order prints
  ONE advisory line on stderr (`acs: <skill> normally follows … in ship.yaml;
  …`) and proceeds at exit 0. Following the walk means you rarely see it —
  and when you do, it is information, never a stop. Only exit 2 stops you.
- You have **no executor/verifier** of your own. Each step skill —
  invoked directly via the Skill tool — runs its OWN reflection cycle (it
  spawns its own executor/verifier); you never do the step's work.
- Keep your own context tiny. Never read step transcripts, phase XML files, or
  diffs. You read exactly five kinds of things: the `workflow next` JSON,
  `run.json`, the ticket document, the compact `<handoff>` XML each
  step returns (~1 KB), and — ONCE per ticket, at the classification point
  below — `plan.md`. That fifth read is the one exception and it is bounded: it
  happens once, it produces one word and one sentence, and you drop the plan
  from your working context immediately after. Between steps your context is
  safe to compact — the ledger holds everything you need to continue. One
  step is an exception: a step carrying `boundary: full_verify_stop` (today,
  `code`) runs its own full reflection cycle inline in your context, and that
  is allowed precisely because of the stop described in
  "Full-verify pipeline boundary" below — the two rules coexist only via that
  stop.
- **Never run /acs:merge-pr.** The schema forbids ship.yaml from naming
  merge-pr or release at all, and the default `stop_after` is create-pr: the
  walk reports `done` with the PR open and unlanded. Landing it is a separate,
  reviewed step, not part of ship.

## Start

**Step 1 — resolve settings and repo partition id.** Run exactly (the
heredoc terminator `PY` must stay at column 0):

```bash
python3 - <<'PY'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "hooks", "scripts"))
import acs_lib as lib
cwd = os.getcwd()
settings, sources = lib.load_settings(cwd)
try:
    workspace = lib.validate_settings(settings, cwd)
except lib.GateError as exc:
    sys.stderr.write("acs ship: %s\n" % exc)
    sys.exit(2)
print(json.dumps({
    "workspace": workspace,
    "repo_id": lib.repo_partition_id(cwd),
    "ticket_prefix": settings["ticket_prefix"],
    "settings_sources": sources
}, indent=2))
PY
```

On exit 2: surface stderr verbatim (typically "Run /acs:setup first") and
stop. Otherwise record `workspace`, `repo_id`, and `ticket_prefix`. The
ticket partition path is always
`<workspace>/<repo_id>/<ticket-id>/` — call it `<partition>` below.

**Step 2 — parse `$ARGUMENTS`: a ticket id, and nothing else.**

- A single token matching `[A-Z][A-Z0-9]*-[0-9]+` (e.g. `SHOP-123`) → that is
  the ticket; every run is a resume of whatever the ledger already records.
- Empty → ask the user for a ticket id (offer `/acs:create-ticket` when they
  have only a prompt).
- Anything else → refuse, verbatim:

  > ship takes a ticket id; run `/acs:create-ticket "<prompt>"` (Design phase)
  > and then `/acs:ship <id>`

  Then stop. There is no new-request path: minting the ticket, and settling
  its design when it needs one, is Design-phase work that runs *before* ship.
  ship.yaml is Build/Test/Ship only.

**Step 3 — product-flow refusal.** Read `<partition>/run.json`
once. If it has `"flow": "product"`, this is a product-level delivery ticket
— /acs:ship does not drive those; tell the user to re-run the matching
product skill (/acs:create-prd, /acs:create-architecture,
/acs:create-project, /acs:create-docs) and stop. If the file is absent or
unreadable, skip this check and continue: the first walk below refuses an
unknown ticket for you.

**Step 4 — model note.** Your own ship coordinator session has no
configurable model override in settings — the `coordinator` role was
retired from the `models` settings contract. You simply inherit whatever
model and reasoning effort the invoking session already has, and invoke
each step skill directly in that same context.

## The loop — `acs.py run next`

MANDATORY on entry, and again after every step (or parallel batch) returns.
The ledger, not your memory, decides what comes next:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" workflow next --ticket <ticket-id>
```

It evaluates ship.yaml's DAG against `<partition>/run.json` and
prints one JSON object:

| Field | What you do with it |
|---|---|
| `mode` | `"single"` → run the one ready step inline; `"parallel"` → fan the ready steps out as legs |
| `ready[]` | the steps to run now, each `{step, skill, args, reason, boundary, on_fail, on_replan, exclusive}` |
| `done` | `true` once `stop_after` is completed → go to Finish |
| `blocked_by` | `{step, predicate, pointer}` — a step whose `requires` predicate is false |
| `statuses` | every step id → its ledger status (or `null`), for your report |
| `delivery` | `{path, reason, classify_after, paths, awaiting_classification}` — null when the workflow declares no paths; see "Classify the delivery path" |
| `workflow` | `{source, path, name, stop_after, max_parallel}` — which file the order came from |

Branch strictly on what comes back:

1. **Exit 2** → surface stderr verbatim and stop. Two cases matter: an epic
   (stdout also carries `{"error": "epic", "pointer": …}` — see "Epic fan-out"
   below) and an unknown or archived ticket (`no partition for <ID>`; suggest
   `/acs:create-ticket`, or report that an archived ticket is already done).
2. **`done: true`** → Finish.
3. **`ready` empty and `blocked_by` set** → STOP and surface
   `blocked_by.pointer` verbatim (for example, "run /acs:create-design <id>
   first"). The pipeline cannot advance until that upstream work exists; it
   is not a failure of any step.
4. **`ready` empty, not `done`, nothing blocked** → stop and report the
   `statuses` map; the workflow has nothing to offer, which means the ledger
   and the file disagree — run `acs.py workflow validate` and surface it.
5. **`delivery.awaiting_classification: true`** → the plan is written and the
   path has not been judged. Do that now (next section), then run the walk
   again. `ready` is empty or short in this state by construction: the walk
   holds back every step that depends on the path, because a step resolved
   against an unknown path would resolve to nothing.
6. Otherwise run the ready step(s), per `mode`.

Invoking a step is always the same: the Skill tool with skill
`acs:<ready.skill>` and args = `ready.args` when it is non-null (ship.yaml
already substituted the ticket id), else the ticket id alone. Never re-derive
the args, and never pass `<partition>` — the step resolves it itself.

Run the walk again after every step. A step recorded `in_progress`, `failed`,
`interrupted`, or `handed_off` simply becomes ready again — the step's own
skill-start reconciles recorded state against reality; you never reconcile
yourself, and you never re-record a step's own status.

## Classify the delivery path

Once `delivery.awaiting_classification` is true, this ticket needs one word and
one sentence from you before the pipeline can continue. It is the only
judgement /acs:ship makes about the work itself, and it is made exactly once.

Read the rubric — it is the contract, not a summary of it:

> `${CLAUDE_PLUGIN_ROOT}/skills/code/references/classify.md`

In short: read `plan.md` (the file `delivery.classify_after` produced; resolve
it the way that step's handoff names it, or under the ticket's docs folder,
else `steps/code/plan.md`). Judge it onto one of
`delivery.paths`. Prefer the more expensive path whenever two fit — an
unnecessary lens pass costs tokens, a missed regression in a load-bearing path
costs more. Then record it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" path set \
  --ticket <ticket-id> --path <trivial|small|standard|complex> \
  --reason "<one sentence naming what in the plan decided it>"
```

On exit 2, surface stderr verbatim and stop — it refuses an unknown path, an
empty reason, and any attempt to move a ticket already on one. That last
refusal is the mechanism, not an obstacle: the path is judged once, and a
resumed run reads it. If you believe a recorded path is wrong, the route is
`/acs:create-impl-plan` and a fresh judgement from the corrected plan, never a
second `path set`.

Then **drop `plan.md` from your working context** and go back to the walk. You
will not read it again this run; from here on the path is a word in
`run.json`, which is what keeps your context small enough to reach
the end of the pipeline.

**A plan you cannot classify is an unfinished plan.** If it has no file map, or
a Test strategy that says nothing, stop and say so — the remedy is re-running
`/acs:create-impl-plan`, not a guess that every later step inherits.

## Single mode — invoke the one ready step

`mode: "single"` means exactly one step runs now: either only one is ready,
or a ready step is `exclusive: true` and must run alone.

Invoke the Skill tool directly and follow that step skill to completion as
its coordinator, in your own context, holding the Agent tool the step needs
to spawn its own executor/verifier. Keep what you pass lean — the
ticket id is enough.

You do not prompt a subagent; you run the step skill yourself. A few
properties of every step skill you must understand as its coordinator:

- It honors the hooks. If its Skill invocation is denied (pre-hook exit 2),
  it surfaces a `status="failed"` handoff quoting the hook stderr verbatim —
  you stop the pipeline on that (see "Handling the handoff").
- It CAN reach the user under direct invocation, so it asks you/the user
  directly when it needs input; it only returns `status="needs_input"` if the
  run is genuinely non-interactive.
- Its terminal output is the `<handoff>` XML (per acs-messages.xsd): a
  `<summary>` under 1 KB, `<artifacts>` referencing workspace files (never
  inlined content), `<questions>` when status is `needs_input`, and a
  `<next-step>` when known.

You read the step's outcome from its `<handoff>` and from
`<partition>/run.json` — that is the read mechanism that keeps your
context lean. There is no returning subagent and no per-step task brief to
compose; the step skill's own argument contract (`acs:<skill> <args>`) is the
interface.

Step-specific adjustments:

- **Re-invoke after needs_input**: re-invoke the SAME step skill directly,
  passing each question with the user's answer (`Q: ... A: ...` lines) as
  context. The re-invoked step coordinator records the relayed answers in the
  ticket's clarification ledger (per its own "Clarification ledger first"
  rule) — /ship only relays; it never writes the ledger itself.
- **A step that takes `args`**: pass `ready.args` exactly as printed. It is
  the workflow's contract with that skill (e.g. a ticket-scoped test run),
  not a flag for you to choose.

If you compose any XML context to hand into a step, validate it first:

```bash
echo '<task ...>...</task>' | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
```

Exit 1 means your XML is malformed — fix it and re-validate; never pass
invalid XML into a step. When the step returns its handoff, validate it the
same way. If the handoff is invalid or missing: first re-read
`<partition>/run.json` — if the ledger shows the step
`completed`, trust the ledger and continue; otherwise re-run the step once;
if the second handoff is also invalid, stop and report (see failed handling
below).

## Parallel mode — one leg per ready step

`mode: "parallel"` means ship.yaml has declared these steps independent (none
needs another), none is `exclusive`, and `max_parallel > 1` — the walk has
already cut `ready` to `max_parallel` entries. Run them as LEGS, reusing the
fan-out shape `/acs:create-docs` already uses (`skills/create-docs/SKILL.md`,
"Worktrees", "Starts", "Reflection loop"), cited here rather than restated:

1. **A worktree per leg, before that leg's Start.** Two legs must never share
   an index. The ticket branch is the branch the session checkout is already
   on (`git rev-parse --abbrev-ref HEAD`); cut each leg its own branch from
   that head:

   ```bash
   git worktree add -b <ticket-branch>--<step id> <path> <ticket-branch>
   ```

   A freshly created worktree has a clean tree by construction, which is the
   precondition each step skill's own Branch/commit step requires. Each leg's
   `<task>` carries that leg's worktree-absolute paths, so its writes cannot
   land in the session checkout.
2. **Starts, sequentially, as real Skill-tool calls.** Invoke
   `Skill(acs:<skill>)` for each ready step one after another — never
   concurrently, and never from inside an agent you spawned (no acs subagent
   may hold both the Agent and Skill tools; decomposition stays exclusively
   the coordinator's job). Each is a genuine Skill call, so each leg's own
   pre-hook gates it for real and its own post-hook finalizes it for real.
   Every `skill-start.py` invocation runs from the **session checkout**, not
   from a leg worktree — the same rule `/acs:create-docs` states, for the same
   session-marker reason.
3. **Reflection loops, in parallel batches, from this coordinator.** Once
   every leg has started, spawn each phase's existing agents for all legs in
   ONE message: every leg's executor together, then (once those return)
   every leg's verifier — the same mechanism `/acs:code`
   already uses to run several executors in parallel. Each leg keeps its own
   iteration cap, its own phase artifacts, and its own Finish contract,
   unchanged. Each leg commits on its own leg branch, in its own worktree.
4. **Merge back in ship.yaml file order**, from the session checkout on the
   ticket branch, one leg at a time:

   ```bash
   git merge --no-ff <ticket-branch>--<step id> -m "merge <step id> leg for <ticket-id>"
   ```

   A conflict STOPS the pipeline: `git merge --abort`, then report which two
   legs touched the same file and that they must be re-run sequentially (run
   the remaining step directly with `/acs:<skill> <ticket-id>` once the
   conflict is settled). Never resolve a leg conflict yourself.
5. **Clean up.** `git worktree remove <path>` for every leg, then delete the
   leg branch of each leg that merged. Keep the branch and report the path
   for a leg that did not.
6. **A failed leg never cancels its siblings.** Merge the legs that completed,
   leave the failed leg's branch unmerged, and go back to the walk: that step
   is simply ready again on the next `workflow next`, because its own
   post-hook already recorded what happened. Each leg's ledger entry is its
   own — you write none of them.

## The context boundary

A ready step may carry `boundary: full_verify_stop`. Today exactly one does
(`code`), and only on two of its four delivery paths — `ship.yaml` gives the
boundary as a per-path mapping naming `standard` and `complex`. That is the
step whose whole reflection cycle lands inside your own coordinator context,
because you run it as its coordinator (see "Single mode"): every executor, and
on `complex` up to three rounds of four merged verifier lenses. On `trivial`
and `small` that is small. On the two deep paths it routinely leaves too little
context to safely reach the end of the walk. Left unacknowledged, the run just
trails off after the step completes — an implicit silent stop that reads as a
failure. This section replaces that implicit stop with a **designed boundary,
not a failure**.

**You do not decide the depth; the walk already did.** The `ready` entry you
invoked carried `boundary` already resolved for this ticket's recorded path:
`"full_verify_stop"` on `standard` and `complex`, `null` on `trivial` and
`small`. There is nothing to recompute and no ticket to re-read — the mapping
lives in `ship.yaml` where a reviewer can see which paths are expensive, and
`workflow next` resolved it against the path recorded once at classification.

- `boundary` was **null** → no stop. Go straight back to the walk and continue
  through the remaining ready steps (docs-sync, create-pr, and the e2e steps
  when they apply) exactly as before.
- `boundary` was **`full_verify_stop`** and the step returned `completed` →
  STOP, before the next `workflow next` — the test step's own work would also
  run in your context, so stopping before it is strictly safer. Do not mark any
  step `failed`, and do not run `handoff.py` (unchanged: /acs:ship is not
  hooked and owns no run entry).

**The stop report.** The boundary step is complete and /acs:ship stops here by
design. The remaining steps run in a fresh session. Resume with
`/acs:ship <ticket-id>` — `<partition>/run.json` already records the
step completed AND the delivery path, so the resumed run's first
`workflow next` picks up at the steps ready after it, on the same path, with no
re-judgement. Close with the standard completion report block below,
`<status>` = `handed_off`.

This section changes only **when** the tail runs, never **which** steps run or
in what order — that stays ship.yaml's to declare and the walk's to compute.

## The failure-path reference, and when to open it

Nearly all of this skill is one loop: ask `acs.py run next` what is
ready, invoke it, record the outcome, ask again. One part is not — what to do
when an invoked step comes back `failed` and its `ready[]` entry says the
pipeline is allowed to recover rather than stop:

| Open | When |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/ship/references/failure-paths.md` | A step returned `failed` AND its `ready[]` entry carries `on_fail` (relay the failure into a named step and re-try, up to a cap this skill keeps as `fix_loops`) or `on_replan` (re-run a named step, but only for `stop_reason: plan_superseded`). A step that fails carrying neither is an ordinary stop — see "Handling the handoff" below. |

## Handling the handoff

Branch strictly on `status`:

- **completed** — re-read `<partition>/run.json` to confirm the
  ledger agrees (the step's post-hook wrote it), keep only the one-line
  summary, drop the rest from your working context, and go back to "The loop"
  — except after a step carrying `boundary: full_verify_stop`, where you
  evaluate "Full-verify pipeline boundary" first.
- **needs_input** — a directly-invoked step normally asks the user itself;
  when it nonetheless returns `needs_input`, ask the user every `<question>`
  (use AskUserQuestion; plain questions if unavailable). Then re-invoke the
  SAME step with the answers as context, as described above. This loop has no
  fixed cap, but if the same step returns needs_input three times with
  substantially the same questions, stop and surface the impasse to the user.
- **failed** or **interrupted** — STOP the pipeline, unless the step carries
  `on_replan` and the reason is `plan_superseded`, or it carries `on_fail`
  and the counter is under its cap — both in
  `references/failure-paths.md`.
  Otherwise: surface the handoff `<summary>` verbatim, say where the state
  lives (`<partition>` and `<partition>/phases/<step>/`), and tell the user
  how to resume: `/acs:ship <ticket-id>` to retry the pipeline from this
  step, or `/acs:<skill> <ticket-id>` to run just the step interactively
  (useful when it needs back-and-forth). Do not retry a failed step yourself.
- **handed_off** — treat as interrupted: stop and print the same resume
  commands; the step flushed its own handoff context to the partition.
- **fix-loop cap reached** — when an `on_fail` step's `fix_loops` counter
  reaches its `max_loops` on a failing run (`references/failure-paths.md`),
  STOP the
  pipeline the same way as failed/interrupted: surface a "persistent failure"
  report, say where the state lives (`<partition>` and
  `<partition>/phases/<step>/`), and tell the user how to resume:
  `/acs:ship <ticket-id>` to retry from this step, or `/acs:<skill> <args>`
  to re-run just that step interactively. Do not continue the walk.

Hook-blocked step: if the step's Skill call was denied (pre-hook exit 2),
surface that stderr message verbatim and stop — it names exactly which input
is missing and which skill produces it. Same for a partition `.lock` held by
another session: surface the skill's message and stop; never delete a lock.
That message now ends with `acs.py lock force-unlock` — surface it, **do not
run it**. Breaking another session's lock is the operator's call, not yours:
the command requires a stated reason and records who broke it in the
partition's audit ledger, and nothing about being blocked tells you the other
session is actually gone.

## Epic fan-out — refuse and point at it

Epics are never shipped. `workflow next` exits 2 on one, printing
`{"error": "epic", "ticket": …, "pointer": …}` on stdout: surface the pointer
verbatim and stop. It names the whole Design-phase path — settle the epic's
design with `/acs:create-design <epic-id>`, mint its children with
`/acs:create-ticket <epic-id> --fan-out`, then run `/acs:ship <child-id>` for
each child you want shipped, one ticket per run (parallel children belong in
separate worktrees and sessions).

Implementation happens on the children, never on the epic itself; the epic is
auto-marked done by hooks once all children merge — not your concern.

## Context pressure

Your per-step state is exactly: the ticket id, `<partition>`, and the last
step's status — all recoverable from `run.json` through the walk,
so compaction at a step boundary loses nothing. If your context runs low
mid-run: finish handling the current handoff (never abandon an in-flight
handoff), then tell the user to continue with `/acs:ship <ticket-id>` in a
fresh session. Do NOT run `handoff.py` for /acs:ship itself — only hooked
skills own run entries; a step that was mid-flight flushes through its own
handoff protocol.

## Finish

There is no post-hook for /acs:ship; each step's post-hook already persisted
everything. End every run — success or failure — with a compact report:

- The ticket id, and per-step status straight from the last walk's `statuses`
  map (one line per step; `skipped` means ship.yaml's `when` was false for
  this ticket, which is a normal outcome, not a gap).
- Which workflow file drove the run (`workflow.source` and `workflow.path`) —
  a consumer override is worth naming.
- The PR reference when the walk reached its `stop_after`: take the URL from
  that step's handoff; if it is not there, read `states.pr.url` from
  `steps/create-pr/result.json` (a single small file — the one
  permitted exception to the "ledger and handoffs only" rule).
- On failure: which step failed, its summary, `<partition>`, and the resume
  commands (`/acs:ship <ticket-id>` or `/acs:<skill> <ticket-id>`).

When the walk reported `done`, the LAST line is always:

> The PR is ready. Review it yourself, then run `/acs:merge-pr <ticket-id>`
> to land it — a separate, reviewed step.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty:

```markdown
## /acs:ship · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: per-step status from the last `workflow next` (one line per step); the PR reference when the walk reached `stop_after`
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, ticket docs folder, branch, PR URL>
- **Metrics**: <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: review the PR yourself, then `/acs:merge-pr <ticket-id>`; on a failed step: the resume command (`/acs:ship <ticket-id>` or `/acs:<skill> <ticket-id>`)
```
