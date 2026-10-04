# acs plugin internals — the implementation contract

This document is the binding contract between the plugin's moving parts: skills
(SKILL.md), subagents (agents/), hooks (hooks/), schemas, and templates. The
business requirements live in the repo's `docs/` folder; this file records how
they map onto the Claude Code plugin API and the exact conventions every
component follows.

## Component map

| Piece | Where | Count |
|-------|-------|-------|
| Marketplace manifest | `.claude-plugin/marketplace.json` (repo root) | 1 |
| Plugin manifest | `plugins/acs/.claude-plugin/plugin.json` | 1 |
| Skills | `plugins/acs/skills/<name>/SKILL.md` | 25 |
| Subagents | `plugins/acs/agents/<skill>-<role>.md` | 25 files, all reachable. Each skill owns only the roles its own work needs, named for that work (`create-prd-surveyor`, `create-impl-plan-plan-reviewer`, `code-implementer`), and each role has a kind in `acs_lib.skills.ROLE_KINDS` — `survey`, `write` or `judge` (ADR-0109). `create-ticket`, `create-pr` and `merge-pr` own none: their coordinators run the steps inline. There is no declaration to keep level with the tree: `acs_lib.skills.skill_agents()` reads the roles from the file names |
| Hooks | `plugins/acs/hooks/hooks.json` + `hooks/scripts/` | dispatcher + 16 pre + 16 post |
| Helper CLIs | `hooks/scripts/{acs,citation_check,clarify,codeowners,front_matter_check,handoff,mermaid_lint,migrate_workspace,new-ticket,plan-approval,pr-conventions,prd_conformance_check,record-external,release_notes,setup_wizard,structure_lint}.py` (the `hooks/scripts/*.py` files with a `__main__` entry point, excluding the dispatcher + 16 pre + 16 post hooks counted in the row above; the `acs_lib/` package, `claude_code_adapter.py`, `markdown_headings.py`, `consistency_findings.py`, the three `release_notes_*` siblings MAR-531 split out and the `acs_cli.py` / `acs_commands.py` / `acs_state_commands.py` siblings split out of `acs.py` are importable libraries with no CLI entry point and are excluded; `skill-start.py`, `pipeline-step.py` and `validate_xml.py` are gone with the surfaces they served — `acs step start`, the run ledger's single writer, and the XML message contract — and `statusline.py`, `subagent-statusline.py` and `cost_sampler.py` went with the status line (ADR 0103), and `metrics_aggregate.py`, `metrics_render.py`, their siblings and `usage_reader.py` with the usage dashboards (ADR 0104); the count is derived from disk by `HelperCliInventoryTest`, so it stays right on its own; this list is the prose that has to be kept level with it) | 16 |
| Workflow files | `plugins/acs/workflows/ship.yaml` | 1 (the default delivery pipeline; a consumer may override it at `<repo>/.acs/workflows/ship.yaml`) |
| JSON Schemas | `plugins/acs/schemas/*.schema.json` | 13 |
| XML schema | `the SubagentStop hook` | 1 |
| Templates | `plugins/acs/templates/*.md` | 5 (4 description templates — `pr-default`, `epic/story/task-default` — plus `design-default`) |

Skills are invoked namespaced: `/acs:setup`, `/acs:ship`, `/acs:create-ticket`, …
(The requirements docs write `/setup`, `/ship`, … — same skills, plugin-namespaced
by Claude Code.)

## Hook event binding (resolves the open question in docs/requirements/functional/hooks.md)

Claude Code has no "skill completed" hook event, so the pre/post contract maps
onto the plugin hooks API like this:

1. **Pre-hooks — deterministic, enforced.** `hooks.json` registers a
   `PreToolUse` hook matching the `Skill` tool. `dispatch.py pre` extracts the
   skill name from the tool input (handling the `acs:` namespace), no-ops
   (exit 0) for anything that is not one of the sixteen hooked skills, and
   otherwise runs that skill's gate from `acs_lib.gates` **in-process** (the
   `pre-<skill>.py` wrappers exist for tests and `acs.py gate`, not for the
   hook path).
   Exit 2 blocks the skill before any of its instructions run; stderr names the
   safety brake that fired. A missing upstream artifact is never a reason to
   refuse — each skill falls back to the run's subject — and neither is a
   predecessor's POSITION in the workflow (see "Gates: order lives in
   ship.yaml"); the one refusal that names a predecessor's completion is
   `/acs:merge-pr`'s subject brake, which asks whether the step that recorded
   the PR reference completed — an artifact, not a position (see "Where a
   brake lives when the skill is not a step"). This fires for user-typed
   slash commands and model-initiated Skill calls alike — including the step
   skills `/ship` invokes directly.
2. **Post-hooks — coordinator-invoked, gate-backed.** `post-<skill>.py` is the
   skill's mandatory final step (each SKILL.md ends with it). It must be a
   script the coordinator calls because its inputs — final status, stop
   reason, and findings — exist only in the coordinator's context. No usage
   is recorded (ADR 0104): the legacy usage fields a result document may still
   carry are accepted for backward compatibility and ignored. The pipeline does
   not depend on the model's goodwill: skill-start has already appended an
   `in_progress` run entry, and the ledger it writes is what `acs.py run next`
   walks, so a skipped post-hook leaves the step UN-SATISFIED — the pipeline
   re-offers it rather than moving past it. (Before the skills-independence
   refactor the same fact held the next skill's gate closed; the gate no
   longer reads it, the walk does.)
3. **SessionEnd safety net.** `dispatch.py session-end` finalizes any run this
   checkout left `in_progress` as `interrupted` (and releases the lock), so
   abnormal endings still write state. A hard kill that skips even SessionEnd
   still leaves `in_progress` + a stale lock — the workflow walk reads the step
   as un-satisfied and offers it again, and the next run reconciles.
4. **Lifecycle hooks (MAR-528).** Four more events are bound, each replacing an
   instruction a coordinator had to remember:

   | Event | Matcher | `dispatch.py` mode | What it does |
   |---|---|---|---|
   | `SubagentStart` | `^acs:` | `subagent-start` | records the running agent — its skill, role and the role's kind — in `<partition>/active-agents/<agent_id>.json` — **one file per agent**, so a parallel fan-out — slices of one writer role, or the writers of a parallel group's members (ADR-0110) — cannot lose an entry to a read-modify-write race. `review-code`'s lenses and adjudicators are not recorded: the coordinator persists what they return itself |
   | `SubagentStop` | `^acs:` | `subagent-stop` | validates the returned XML and writes the phase snapshot (see "Phase artifacts"); **exit 2** sends the subagent back, at most `BLOCK_LIMIT` times |
   | `Stop` | — | `stop` | **exit 2** refuses to end a turn that left a run `in_progress` with no result document, naming the finish command; at most `BLOCK_LIMIT` times per checkout and run |
   | `PreCompact` | — | `pre-compact` | writes `<partition>/handoff-context.md` from the ledger before the window shrinks |
   | `PreToolUse` | `Write\|Edit\|MultiEdit\|NotebookEdit` | `file-map` | **exit 2** denies a write outside the declared executor file map while a `write`-kind agent runs (MAR-529) |

   The matchers are **anchored on the plugin scope** on purpose: unanchored,
   the subagent events would fire for every subagent in the session — `Explore`,
   `Plan`, another plugin's agents — and try to file their output as an acs
   phase artifact.

   These four fail **OPEN**, which is the opposite of the gate. The gate fails
   closed because letting a skill run unchecked is the harm; here the harm runs
   the other way — a bookkeeping bug that ends a session or wedges a subagent
   costs more than the bookkeeping is worth — so `dispatch.py`'s
   `run_lifecycle` turns anything raised into exit 0 plus one line on stderr.
   Both blocking hooks also give up after `BLOCK_LIMIT`: a session that cannot
   stop is worse than a run SessionEnd will mark `interrupted`.

   **The file-map guard (MAR-529).** "Mutate ONLY the files in your task's file
   map" is a bullet in every writing agent's charter, and plugin agents cannot
   carry frontmatter hooks, so the enforcement point is the plugin's own
   `PreToolUse` entry, keyed on the active agent `SubagentStart` recorded. The
   coordinator declares each writing task's map with **`acs.py filemap set
   --iteration <n> --task <k> --file …`** (additive, per task, written to
   `steps/<skill>/iter-<n>/filemap.json`); a write outside it is denied while
   an acs agent of the **`write` kind** is running (`code-implementer`,
   `create-prd-author`, `docs-sync-doc-updater`, … —
   `acs_lib.skills.ROLE_KINDS`), with the agent told to return `needs_input`
   for the file it needs. The guard is `filemap.file_map_guard`; it reads
   every live writer through `filemap.active_writers` (most recent first).

   **Several writers can be live at once (ADR-0110).** A coordinator fans a
   writer role out over disjoint slices, and `/acs:ship` runs a parallel
   group's members side by side, so writers of two SKILLS can be recorded at
   the same moment. The guard therefore never judges a write against
   "whichever writer started last". When the hook payload carries the calling
   subagent's `agent_id`, `filemap._writer_for` matches it to its own record
   and the write is judged against exactly that writer's skill: its own
   `steps/<skill>/` artifacts and its own iteration's map. An `agent_id` that
   matches no live writer is a judge's or a surveyor's, and passes: a
   parallel group puts one step's reviewer beside another step's writer, and
   the reviewer's report is not the writer's to scope. When the payload
   names no agent (an older Claude Code), the write cannot be attributed, and
   it is allowed when ANY live writer may make it — the **union** of their
   scopes. A candidate whose skill declared no map contributes only its own
   `steps/<skill>/` to the union, never a pass for everything: otherwise one
   map-less writer beside a mapped one would switch the mapped writer's
   guard off. The guard applies when at least one candidate declared a map;
   the deny lists each mapped candidate's skill, iteration and map, and is
   recorded on each of those skills' run entries. The price of the union is
   stated in ADR-0110: an unattributed write may touch a sibling skill's
   mapped file, and a map-less writer's unattributed write outside its
   siblings' maps is denied; with `agent_id` on tool hooks the check is
   exact.

   **Failure polarity is split, because the two questions carry opposite
   risks.** Deciding *whether the guard applies* fails OPEN — not an acs
   partition, no `write`-kind agent active (a surveyor, a judge and the
   coordinator all write outside any task's map legitimately), **no map
   declared** (a run that spawned no writer declares no map), or a call that
   names no path. A bug there must not
   deny every write on the machine. Deciding *whether this write is inside the
   map* fails CLOSED: an error, a timeout, or a `tool_input` the guard cannot
   read all deny, because a deny control that fails open is silently absent
   while still installed — the failure ADR 0002 records for the other exit-2
   `PreToolUse` hook. Exempt: this agent's own `steps/<skill>/` artifacts,
   and only those. Explicitly NOT exempt, and denied outright: the guard's own
   control inputs — the `active-agents/` record that arms it and any
   `iter-*-filemap.json` — since a writer that can rewrite either can answer
   the guard's own question.

   **Every deny is recorded: `invocations[-1].guard_events` (MAR-578).** A denial used
   to exist only as a line of stderr in a transcript, so "how often does the
   guard actually fire, and on what?" had no answer. Each deny now appends one
   event to the writing agent's `steps/<skill>/state.json` run entry — `ts`, `skill`,
   `iteration`, `tool`, `target` (repo-relative when the path is under
   `checkout_root`, else as given; `null` for an unreadable payload, which names
   no path), `reason` (`outside_map` | `control_input` | `unreadable_payload`)
   and `declared_count` (the size of the declared union the guard enforced; `0`
   for the other two reasons). It is written through
   `acs_lib.state.record_guard_event`, the sibling of `record_escalation_event`
   that returns `False` instead of raising when there is no run entry. Two rules
   bound the trail. It is written **never on a fail-open branch** — a write the
   guard waves through leaves no trace at all. And it **never changes the
   verdict**: a failed append is one extra stderr note, the exit code and the
   warning text stay byte-identical, and there are no retries, waits or lock
   acquisitions, so the append stays well inside the guard's timeout budget.
   One caveat, stated plainly rather than by analogy: this is the first writer
   of the shared `steps/<skill>/state.json` from a `PreToolUse` deny path, and so the
   first that can run while the parallel implementer fan-out is in flight.
   `SessionEnd`'s `finalize_run` writes the same file from a hook process too,
   but only at teardown, by which point this checkout's writers have normally
   already finished — normally, because nothing here enforces it: when the
   runtime fires `SessionEnd` is the runtime's business, not this repo's. No
   corruption is reachable: `write_json` is atomic (`mkstemp` + `os.replace`), so a torn or
   truncated state file cannot result. A lost update can: the append is an
   unlocked read-modify-write of the whole document, so when two writes to that
   file overlap — N implementers denied inside the same window, the correlated case
   since a wrong file map denies them all at once — the one that lands second
   replaces the other wholesale, and what it drops can be either side's: a guard
   event, or a concurrent finalization. `record_escalation_event` has the same
   shape but not the same exposure, having one writer at a time (the
   coordinator). Keeping a lock off a deny path is the rule above; the price
   is that the trail is a floor on how often the guard fired, not a
   guaranteed count. Read the trail
   with **`acs.py guard events --ticket <id> [--skill code]`**; `post-code.py`
   derives `states.review.guard_denials` from its length.

   **Known hole, stated rather than implied: `Bash` is not covered.** The
   matcher is `Write|Edit|MultiEdit|NotebookEdit`, so a mutation made with
   `sed -i`, `python -c`, `cat >`, `tee`, `mv` or `git checkout --` is outside
   this control entirely. That is not a small gap — an agent told to prefer
   shell over the write tools would be almost invisible to the guard. Closing
   it needs its own ticket (matching a path out of an arbitrary command line is
   a different problem from reading one out of `tool_input`); what must not
   happen is this list reading as exhaustive while omitting it.

   **What it checks is the UNION of the iteration's declared tasks, not the one
   task the running writer was given.** Per-task binding is not achievable
   with what Claude Code provides: neither `SubagentStart` nor `PreToolUse`
   carries a task index, and parallel instances of one `agent_type` — slices
   of one writer role — run at once, so there is nothing to bind an agent to
   its task by (`agent_id` names the agent, not its task). The union still
   enforces the property that actually goes wrong — a writer wandering outside the
   PLAN — while disjointness *between* tasks stays what the coordinator's
   partition rule already exists to decide. Two unions stack under a parallel
   group: the union of one skill's tasks, and — for an unattributed write —
   the union across the live writers' skills (above).

## Gates: order lives in ship.yaml; skills keep safety brakes

Until the skills-independence refactor, `acs_lib/gates.py` encoded the pipeline
ORDER: `_require_completed(tdir, "code", …)` refused `/acs:docs-sync` until a
completed `/acs:code` run was recorded, and so on down the chain. That made the
order enforceable but also made every skill un-runnable on its own, and it put
the same sequence in three places (the gates, `/acs:ship`'s prose, the docs).

`_require_completed` is gone, and so is the generic input gate that followed
it (ADR-0109). A gate now answers exactly one question:

| Kind | Question | Example |
|---|---|---|
| **Safety brake** | Would running now do damage that cannot be undone by re-running? | `/acs:create-pr` refuses a run whose `/acs:review-code` ran and left `verifier_passed != true`; `/acs:merge-pr` refuses without a PR reference recorded by a completed run; every hooked skill refuses while another session holds the `.lock`. |

**Where a brake lives when the skill is not a step.** `gate_outcome` returns as
soon as the resolved workflow does not name the skill, so `BRAKES` — consulted
after that return — can only hold steps. One table sits BEFORE it, and a
skill that is legitimately not a step of `ship.yaml` is gated from it:

| Table | Precondition it checks | Rows |
|---|---|---|
| `SUBJECT_GATES` | the SUBJECT TICKET the invocation names | `create-design` (flagged `needs_design`), `merge-pr` (a PR reference recorded by a completed step) |

It is consulted **unconditionally**, before the workflow is read,
because a safety brake must not be switchable off by editing `ship.yaml`. A
repo DOCUMENT precondition is not a hook's to check: no setting says where the
PRD or the architecture set lives, so the skill that reads one finds it at
Start. `create-architecture` takes the PRD as its primary input and, without
one, works from the run's subject (a document in its arguments, else the
focus notes plus the codebase) and confirms goals, NFRs and constraints
through the clarification ledger; `create-docs` stops without the
architecture set's `hld/tech-stack.md` (ADR-0102). A
`SUBJECT_GATES` row is `f(ctx, payload)` raising `GateError` to refuse; it
resolves a ticket and reads step state through path joins and `read_json`, so
it opens no run and takes no lock, which is what lets `acs gate` reach it too.
A row belongs there only when the skill is not a step AND its precondition is
a property of the subject ticket (ADR-0101).

**Inputs are the skill's own business.** No hook asks whether an upstream
artifact exists. Each skill reads what it finds and falls back to the run's
subject — the ticket's acceptance criteria, the prompt or the document — when
an upstream artifact is absent, so it runs the same whether `/acs:ship`
invoked it or a user did. What a skill does without its usual input is stated
in its own SKILL.md.

**`acs.py gate` is the pre-hook's dry-run, and it is inert by construction.**
It runs the same `run_pre_payload` with `record_marker=False` and
`mutate=False`, and must produce the hook's exit code and the hook's stderr —
brakes and advisory included. With no current run there is
nothing on disk to judge, so `run.projected_run()` builds the run the subject
WOULD open: the run id, the path it would occupy and the same document
`create_run` builds, with no `makedirs`, no `save_run` and no `index_run`.
`create_run` is that function plus exactly those two writes, so the projection
and a real run cannot drift. `gate_outcome` carries the gate's body and returns
`GateOutcome(run_id, doc)` so the advisory renders from the document the gate
judged rather than re-reading a run that was never written. The one-line
`gate_step` wrapper is gone — nothing called it once the body moved, so
`gate_outcome` is the gate's only name — and `acquire_lock`,
`_mark_step_started` and `settle_no_op` stay `mutate`-guarded.

The per-skill gate functions and the `GATE_INPUTS` partition that classified
them are gone. `acs_lib/gate_inputs.py` keeps the ticket helpers the brakes
share — the epic refusal and the e2e case count — and the lookup that finds a
ticket artifact in the docs folder, then the partition, then a legacy path
(`LEGACY_ARTIFACT_PATHS`, currently `phases/code/plan.md`).

**What replaced the order gate: one advisory line.** `acs_lib/advisory.py`
renders it and `run_pre_payload` prints it — after the gate passes, on stderr,
exit 0:

```
acs: review-code normally follows code in ship.yaml; the cursor for MAR-12 is code
acs: run-e2e-tests normally follows docs-sync in ship.yaml; the cursor for MAR-12 is create-e2e-tests
```

The line names the skill's predecessor — the step before its STAGE, and for a
skill that follows a parallel group that group's last member — and the cursor,
the step the run is actually waiting on. It is suppressed when the skill is one
of the steps due now (`run.due_steps`), so the second member of a parallel
group is never "out of order"; when the skill is not a step of the resolved
workflow; when `settings.workflow.advisories` is false (default true); or when
anything at all cannot be read — `workflow_advisory()` never raises and never
appears on a refusal path. It reads the same ledger the walk does, and never
writes.

**The two brakes are facts, not ordering.** "Its review did not pass" and
"no PR was ever opened" are properties of the ticket that no amount of running
things in a different order makes acceptable. Note the shape of the create-pr
brake: it fires only when `/acs:review-code` HAS run for this run. A run with no
review at all passes — you may be opening a PR for work done by hand, and the gate is
not the place to have an opinion about that.

## Skills and the delivery pipeline

### A skill is its directory

There is no registry and no per-skill manifest (ADR-0109). A skill is
described by its own directory and by the agent files named after it:

| On disk | Means |
|---|---|
| `skills/<name>/SKILL.md` | the skill EXISTS. Discovery is a directory listing, so a skill cannot be missing from a list |
| `skills/<name>/state.schema.json` | its `states` keys and its `outcome` vocabulary |
| `skills/<name>/references/` | the procedures its SKILL.md loads on demand |
| `agents/<name>-<role>.md` | it owns that subagent role |

`SKILL.md` front matter stays the four keys Claude Code reads, and acs adds
nothing to it.

**Nothing declares what a skill reads or writes.** Each skill is independent:
it reads what it finds and, when an upstream artifact is absent, falls back to
the run's subject (the ticket's acceptance criteria, the prompt or the
document). No gate refuses a skill because an earlier one has not run, and no
validator derives an order from artifacts.

**Legs are one table**, `acs_lib.skills.SKILL_LEGS`: the four delivery-path
legs (`code-trivial`, `code-small`, `code-standard`, `code-complex`) map to
`code`. A leg
keeps its SKILL.md and stays Skill-invocable, but a workflow names the entry
point, which dispatches to it.

**Agents are read from the tree**, by the `agents/<skill>-<role>.md`
convention. Both halves of the name may contain hyphens
(`create-impl-plan-plan-reviewer`), so `acs_lib.skills.split_agent_name`
matches the longest shipped skill name as the prefix and requires the rest to
be a role in `ROLE_KINDS`. PRD G8 — every agent file is reachable — is
therefore a naming check (`acs_lib.skills.unreachable_agents`) rather than a
registry kept in step with the tree by hand.

### `workflows/ship.yaml` — a list

```yaml
version: 3

steps:
  - analyze-requirements
  - create-impl-plan
  - create-api-contract
  - create-test-docs
  - code
  - review-code
  - [create-e2e-tests, docs-sync]   # a parallel group
  - run-e2e-tests
  - create-pr

loops:
  - from: review-code
    back_to: code
    max_iterations: 3
    on_exhausted: fail
```

That is the entire file, and it is an orchestrator: it keeps the order the
skills run in. Each entry is a **stage**: a skill name, or a list of two or
more skill names — a **parallel group** (ADR-0110), whose members
`/acs:ship` starts together and which completes when every member has.
`acs_lib.workflow` reads it through `stages_of` (the stages, each a list),
`steps_of` (every step flattened, a group's members in written order),
`stage_of` and `stage_index`. `acs workflow validate` checks only what a list
can get wrong on its own — every step is a skill that ships and not another
skill's leg, no skill appears twice (a skill is one step of a run), every
loop's `back_to` precedes its `from`, and neither end of a loop sits inside a
parallel group (a loop that re-entered half a group would leave the other
half's work neither kept nor redone). It does not check the order
against what the skills need, so an out-of-order override validates and its
steps run on their fallbacks. `workflow.schema.json` **rejects** every key version 2
carried — `when`, `paths`, `requires`, `needs`, `id`, `name`, `stop_after`,
`max_parallel`, `exclusive`, `on_fail`, `boundary`, `delivery` — rather than
ignoring them, and the refusal names where each one went, so a v2 file ports
in one pass rather than three.

The declared order is the order the steps run in, and every step runs on
every run. A skill whose applicability was decided by a workflow predicate could not
be run on its own and be trusted, because invoked by hand it never evaluated
the condition the workflow was evaluating for it. So each skill decides for
itself and records why (see *Nothing owed*, below).

**A parallel group is not a condition either.** It declares that its members
may overlap, nothing about whether they have work, and it is written by the
workflow's author, never derived: the skills declare nothing about each other,
so nothing could derive it. The shipped file declares one —
`create-e2e-tests` and `docs-sync` both follow the reviewed changeset and write
disjoint files (suites vs docs), and `run-e2e-tests` then runs the suites the
first one wrote.

`/acs:ship` runs a group inside its own session — a step's coordinator runs
in the invoking session, so two steps cannot each get a session of their own
inside one run. It invokes every member in written order (each call fires that
member's pre-hook and its own `acs step start`), advances their coordinators
in lockstep with each phase's subagents for all members spawned in ONE message,
gathers every member's questions into one ask, and lets each member write its
own result and run its own post-hook (`skills/ship/SKILL.md`, "Running a
parallel group"). When one member fails, the others finish the phase in
flight, are recorded `interrupted` through their own Finish, and the run
stops. The cost is the coordinator's context: every member's coordinator
prose is loaded together, which is why groups are declared, never derived.

`loops:` is the only other construct, and it is not a condition: it tests nothing
about the change, it declares that two steps form a cycle and how many times.
It cannot live inside a skill because it spans two of them — which is exactly
why the review could not be a separate skill until the loop moved here.

### `acs run` and `acs step`

| Command | Answers |
|---|---|
| `acs run new \| show \| next \| check \| abandon` | the run: its ledger, its cursor, its invariants |
| `acs step start \| finish \| show --step <name>` | one step's transition and its own state |
| `acs result validate` | is this result document admissible? |
| `acs workflow show \| validate` | which workflow file, and does it hold together? |
| `acs notes merge --out <file> <slice files…>` | join what a parallel fan-out wrote into the one file every reader expects (see "Fan-out inside a skill") |

`acs run next` is **the cursor**: the first step in workflow order that is not
`completed`. With no graph there is no ready-set to compute and nothing to
record as skipped. It also prints **`due`** — every unfinished step of the
cursor's stage (`run.due_steps`): `[next]` for a plain step, each unfinished
member for a parallel group — and **`parallel`**, true when `due` holds more
than one step. `/acs:ship` starts everything in `due`; `next` stays the first
of them.

`acs run check` proves the ledger's invariants. The two that concern the
cursor:

- **I1 — one stage in progress.** Every step recorded `in_progress` belongs
  to ONE stage: a parallel group's members may all be open at once, nothing
  else may. `run.start_step` enforces it at the transition — it refuses a step
  while a step of ANOTHER stage is `in_progress` — and `check` reports a
  violation as an error. `run.in_progress_steps` lists the open steps;
  `run.in_progress_step` is the first of them, the one a handoff or a Stop
  reminder names.
- **I2 — the cursor is derived.** The stored `cursor` must equal the first
  step not `completed` (an error otherwise), and a step `in_progress` that is
  not in `due` is a WARNING, not an error: a skill run on its own is out of
  order, not inconsistent.

Every verb defaults to this checkout's current run and
takes `--run` only to name another, because nobody should have to type a run
id — `sessions/<checkout-id>/pointer.json` already knows.

`--step` validates against the **resolved workflow**, not an `argparse` enum.
That enum was the closed skill list in its fourth place.

## Skill lifecycle (every hooked skill)

Every workflow and product-level SKILL.md follows this exact lifecycle:

```
(PreToolUse fired pre-<skill>.py — already passed or we wouldn't be running)
1. acs step start  --step <skill> [--ticket|--args|--allocate ...]   # FIRST action
     -> context JSON: settings, partition, ticket, reconcile/handoff info,
        per-tier models, design source, post_hook path
2. if context.reconcile: reconcile recorded state against reality before continuing
   if context.handoff_summary: read it, light-verify, continue from where it points
3. Reflection loop (max 3 iterations), over the skill's OWN roles, in the order
   its SKILL.md gives (see "Subagents" for every skill's roles):
     survey -> spawn <skill>-<survey role> (surveyor, impact-analyst), iteration 1 only:
               read-only on the repo; records mode, inputs, evidence and open
               questions in iter-1/authoring.md; an open decision comes back as
               needs_input BEFORE any file is written. Later iterations reuse
               these notes as a fixed baseline. Sliced per disjoint top-level
               repo area when the scope spans two or more; the slices'
               authoring-<id>.md are joined by `acs notes merge`.
     write  -> spawn <skill>-<write role> (author, planner, implementer, ...):
               produces the deliverable from the notes, the answers and, on
               iteration 2+, the judge's findings. Sliced BY DEFAULT, from
               iteration 1, whenever the deliverable splits into disjoint
               files; then one more writer instance, slice="integration",
               reconciles the seams before the judge. Decomposition is
               coordinator-only. The file-map guard applies while one runs.
               A skill with no survey role has its writer survey first and
               record the survey in the same authoring notes.
     judge  -> spawn <skill>-<judge role> (reviewer, plan-reviewer, suite-runner, ...):
               re-derives and judges fresh; returns a result with findings.
               Sliced BY DEFAULT at five or more check dimensions: 2-3 slices
               over disjoint dimensions, joined by `acs notes merge`; the
               iteration passes only when every slice passed.
     - a fan-out is N instances of the SAME agent spawned in ONE message,
       each carrying slice="<id>", at most max_parallel = 4 per phase (see
       "Fan-out inside a skill")
     - every task and result carries phase="<role>"
     - every subagent WRITES ITS OWN ITERATION ARTIFACT (see below) and names it
       in its outputs; the message itself stays compact
     - the SubagentStop hook persists every message it receives under
       steps/<skill>/iter-<n>/ at the phase boundary, before the next role
       starts. The messages are validated in the hook; there is no second
       schema language and no validate_xml.py.
     - judge findings == 0 -> done; findings > 0 -> feed findings into the next
       iteration's write role
     - iteration 3 still failing -> stop; final status "failed", findings recorded
   /acs:code runs no loop of its own: its implementers run once per step, and
   the review -> fix cycle is ship.yaml's review-code -> code loop. The three
   inline skills (create-ticket, create-pr, merge-pr) run no loop and spawn no
   subagent.
4. Write the result document steps/<skill>/result.json
5. python3 <post_hook> --result-file <result.json>                    # MANDATORY final step
```

**No skill re-plans inside its loop.** A plan for a document is a second
copy of the writing, so no skill runs a planning pass before its writer
(ADR-0092). Where a skill's work genuinely has two jobs — a read-only survey
that ends in questions, then a write after the answers — the jobs are two
roles (ADR-0109): `create-prd` runs a surveyor on iteration 1 only, and its
author writes from the frozen notes. Every other skill's writer surveys
first and records the survey in its authoring notes. On iteration 2+ the
judge's findings feed straight into the next write role's `<context>`, and
the writer authors the remediation. `/acs:create-impl-plan`'s `planner` is the
one role whose deliverable is a plan: `plan.md`, which the delivery path is
judged from (ADR-0095), so the skill has no per-path shape and every run
spawns the planner.

### Fan-out inside a skill (ADR-0110)

A subagent cannot spawn a subagent, so every fan-out is the coordinator's: it
runs N instances of the SAME agent in ONE message, in the foreground, each over
a disjoint **slice**, and waits for all of them before the next phase. The
cap is **`max_parallel = 4` instances per phase**; a skill with its own cap
keeps it (`/acs:create-docs` runs its doc sets at 2), and work beyond the cap
runs in waves. Three kinds of work fan out:

| Kind | When | Slice | Joined by |
|---|---|---|---|
| **Writers** | by default, from iteration 1, whenever the deliverable splits into disjoint files — authors per feature area, architects per HLD/LLD, test-writers per suite file, doc-updaters per doc area, implementers per file-map partition. A deliverable that is one document keeps one writer, and its SKILL.md says so | one disjoint set of files, named by the skill's partition rule | the integration pass (below) |
| **Judges** | by default when the judge has five or more check dimensions | two or three named slices over disjoint dimensions, as a table in the SKILL.md (slice id → dimension numbers), passed as `<constraint name="dimensions">`. Each deterministic checker runs in exactly one slice; a judge that runs something once (a build, a suite) keeps that run in one slice | `acs notes merge` into `iter-<n>/<role>.md`, then de-duplication |
| **Surveys** | when the scope spans two or more disjoint top-level areas of the repo | one area | `acs notes merge` into `iter-1/authoring.md`, then the consumer's synthesis |

**The slice is on the message and in every file name.** The task and the
result carry `slice="<id>"` (`<task skill="S" phase="<role>" slice="<id>" …>`);
an un-sliced instance omits it exactly as before. A sliced instance writes
`iter-<n>/<role>-<id>.json` (write and survey report), `iter-<n>/<role>-<id>.md`
(judge report) or `iter-<n>/authoring-<id>.md` (survey notes), and the
SubagentStop hook files its snapshot at `iter-<n>/<role>-<id>-message.xml`
(`lifecycle.phase_artifact_path(..., slice_id=)`), so siblings sharing a phase
and an iteration never overwrite each other. `lifecycle.validate_message`
holds a slice id to what a file name can safely be: letters, digits, `_` and
`-`, at most 40 characters.

**The join is deterministic: `acs notes merge`.** `acs.py notes merge --out
<file> <slice files…>` (`acs_lib.notes.merge_files`) merges markdown by `## `
heading: the preamble is the first input's; every H2 appears once, in the
order first seen; each input's body under it is appended in input order behind
a `<!-- slice: <id> -->` marker. Headings inside fenced code are body text, and
`###` and deeper stay where their slice put them. It prints `{ok, out,
sections, inputs}`. Slice ids come from the file names: the stem minus the
prefix every input shares, cut back to a hyphen (`impact-reviewer-surface.md`,
`impact-reviewer-form.md` → `surface`, `form`), so role names and slice ids
may both contain hyphens. **A missing input fails the merge** — a missing slice
is a failed slice, and a merge that quietly left it out would read as a pass.
Every downstream reader and deterministic checker (`prd_conformance_check.py`
parsing the notes' sections, the next writer reading the judge's report) still
reads ONE file with each section once.

**Joining is not synthesizing.** The merge is the whole join only where slices
cannot disagree. Where they meet at a seam, the skill reconciles them before
the next phase:

- **Parallel writers → an integration pass.** After every writer slice
  finished and BEFORE the judge, ONE more instance of the same writer role runs
  with `slice="integration"` — `/acs:code-complex`'s final integration
  implementer, generalised. Its task names every slice's outputs and reports.
  It reconciles only the seams its SKILL.md names (shared terms and IDs,
  cross-references, index and overview files, shared fixtures and config),
  never a slice's substance; records each seam it changed (file, what, why,
  which slices) in `iter-<n>/<role>-integration.json`; returns a conflict it
  cannot settle from the evidence as `needs_input`; and is skipped when one
  writer ran. The judge then judges the integrated result, and a seam
  inconsistency is a finding for the next iteration.
- **Parallel surveys → the consumer synthesizes.** A single writer that reads
  the merged `authoring.md` reconciles contradictions between slices under a
  `## Synthesis` section of its own notes — the resolution with its evidence,
  or an open question — and never silently picks one.
- **Parallel judges → the merge plus de-duplication.** Slices own disjoint
  dimensions, so the merge is the synthesis; the coordinator additionally
  drops a finding that cites the same location and the same defect as another
  slice's (keeping the higher severity) and says so in the joined report.

**A sliced judge passes only when every slice passed**: every slice returned
`status="completed"` with zero blocking findings. Any slice's blocking finding
blocks, every slice's findings go verbatim to the next writer, and a slice that
failed or returned nothing usable fails the iteration — never "pass with a
missing slice". A resumed iteration re-runs only the slices whose report is
missing.

**Commits from parallel writers** on one ticket branch meet git's
`index.lock`. The rule is wait briefly and retry; never delete the lock and
never force anything.

**Cost.** Wall time falls wherever work splits; token cost rises with sliced
judges, which re-read shared inputs once per slice, and the per-phase cap
bounds it.

### Phase artifacts (written by the subagents themselves)

Subagents persist their full work products into the partition — the XML result
carries references, never the bodies (docs/requirements/functional/reflection.md: subagents write their states,
findings, error details, and stop reasons into workspace files):

| Phase | Artifact (under `steps/<skill>/`) | Written by | Contents |
|-------|------------------------------------------------|------------|----------|
| authoring | `iter-<n>/authoring.md` (every skill that authors a deliverable, ADR-0092/ADR-0094; no skill writes `iter-<n>/plan.md`. `/acs:create-impl-plan` is the one skill whose DELIVERABLE is a plan — its planner's survey goes into the same notes and its draft is the per-ticket `plan.md` (MAR-70). It runs BEFORE any delivery path exists — the path is judged from the plan it produces (§3.2) — so it has no per-path shape and no coordinator-authored fast path: every run spawns the planner) | the survey role on iteration 1 where the skill has one (`surveyor`), else the write role | the survey the draft was authored from, iteration 1 (mode with its evidence; inputs read and what each settled; the Upstream inventory — every upstream fact the document was tailored on, cited with a verbatim excerpt, which the judge corroborates through `citation_check.py` where the skill uses it; ADR-0012 consistency findings; decisions, assumptions and open questions) and, on iteration 2+, the findings addressed; the judge's `authoring-conformance` dimension judges the draft against these notes. Sliced survey instances write `authoring-<id>.md`, joined into this file by `acs notes merge`; a single writer consuming the merged notes adds a `## Synthesis` section reconciling the slices (`/acs:analyze-requirements` runs that reconciliation as its own `slice="synthesis"` analyst pass, `authoring-synthesis.md` joined last, BEFORE the user is asked, so its draft pass consumes reconciled notes) |
| survey / write | `iter-<n>/<role>.json` — `surveyor.json`, `author.json`, `planner.json`, `implementer.json`; a sliced instance writes `<role>-<id>.json` (parallel implementers: `implementer-<k>.json`), and the integration pass `<role>-integration.json` listing every seam it changed, … | survey and write roles | artifacts produced, repo files changed, commands/tests run with outcomes, problems hit, clarifications used |
| judge | `iter-<n>/<role>.md` — `reviewer.md`, `plan-reviewer.md`, `suite-runner.md`, …; a sliced judge writes `<role>-<id>.md`, joined into `<role>.md` by `acs notes merge` | judge roles | the full report: every check performed with its evidence, every finding in detail (the XML `<finding>` entries summarize this file) |

**A judge also writes a verdict** (MAR-527):
`steps/<skill>/iter-<n>/verdict.json`, or one `lens-<A..E>.md` per lens for
`/acs:review-code`. It carries a per-dimension result table (by the numbers in
the judging agent's own charter, where `n/a` is a real answer), the findings, and
`passed` — which is **derived, not asserted**: `passed` is true exactly when no
finding is `blocking`. `acs_lib.verdict.validate_verdict` enforces that, and the
SubagentStop hook runs it, so a verdict claiming a pass over a blocking finding
is refused rather than believed. `verdict.schema.json` pins the shape; that
function pins the meaning, and says so. On full depth the coordinator runs
`acs.py verdict merge` — the conjunction of `passed`, the union of findings, the
worst result per dimension — which is arithmetic over the lens files, not a
second opinion. `states.verifier_passed` is **derived by the post hook** from
the review's `verdict.json` (MAR-523) — never copied from the coordinator's
result document, and never concluded from a findings count by hand.

**The XML snapshot is written by the SubagentStop hook** (MAR-528), not by the
coordinator remembering to. The hook fires on `^acs:`-matched agents, validates
the returned message, and files it at
`steps/<skill>/iter-<iteration>/<phase>-message.xml` — a path taken entirely
from the message's own `skill`, `phase` and `iteration` attributes (the phase
is the role, so an implementer's snapshot is `implementer-message.xml`; a
sliced instance's lands at `<phase>-<slice>-message.xml`, so parallel
siblings never overwrite each other), so
nothing about it has to be carried in the coordinator's head. `-message`
keeps the snapshot off the role's own `<role>.json` report. An invalid message sends the
subagent back with the errors, at most twice (`BLOCK_LIMIT`); a still-invalid
third message is let through and the coordinator records the failure, because a
hook that can refuse forever is a hung session. Two consequences worth knowing:
a `<handoff>` is the run's outcome, not a phase artifact, so it validates but
files nothing; and since the schema reads an *absent* `iteration` as `1`, a
subagent must echo its task's `iteration` — one that omits it on iteration 3 is
claiming to be iteration 1, and the hook says so on stderr rather than guessing
at a counter it cannot see. The coordinator still writes the snapshot itself for
work it performs **inline** (`/acs:create-ticket`, `/acs:create-pr`,
`/acs:merge-pr`), where no subagent runs and therefore no SubagentStop fires.

**Every statement in a phase artifact must be grounded**: decisions and
analysis cite the file (path + line/section) they are based on; claims about
behavior quote the command run and its relevant output; anything unverifiable
is marked as an assumption for the coordinator to resolve. Each agent body
carries the binding "Grounding (anti-hallucination)" section; ungrounded
plans/reports are a verification finding.

The `iter-<n>/<phase>-message.xml` snapshots plus these artifacts are
what reconcile mode reads on resume — a crash can lose at most the in-flight
phase. Phase persistence + the `in_progress` run entry give the three resume
levels: between steps (gates), within /ship (ledger), and mid-skill
(reconcile mode).

### Why not Claude Code's native plan mode

The reflection loop deliberately does NOT use plan mode
(`EnterPlanMode`/`ExitPlanMode`) for a survey: plan mode's
contract is *interactive user approval*, but every role runs
as a spawned subagent (no user to approve; under `/ship` the whole step is
headless — that is what the `needs_input` handoff is for), plugin agents cannot
set `permissionMode`, and resumability comes from the phase artifacts + gates,
not from plan-mode state. A survey or judge role's read-only discipline is
enforced by its tool allowlist and charter instead (Write is permitted solely
for its own `steps/<skill>/` artifacts); a write role is bounded by the
file-map guard and its own charter. A user
may still wrap a *direct* skill invocation in plan mode for pre-approval —
that is orthogonal to the pipeline and changes nothing in this contract.

### Completion report (user-facing, every skill, every terminal status)

On a **direct invocation**, the coordinator's final message always ends with
this exact block — same labels, same order, rendered AFTER the post-hook has
succeeded (so what the user reads is what was persisted). Labels never
disappear: an empty one reads `none`. Under `/acs:ship` the step's final
message is the `<handoff>` XML instead; `/ship` itself renders this report at
pipeline end.

```markdown
## /acs:<skill> · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <completed|failed|interrupted> — <stop_reason, on interrupted only>
- **Results**: <the skill's canonical states keys, as short bullets>
- **Findings**: <open findings / clarifications obtained, or "none">
- **Artifacts**: <what was written where: partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: <exact command(s), e.g. `/acs:create-pr SHOP-123`, or what unblocks>
```

**The `iterations` element.** A skill that runs no reflection loop omits it
entirely rather than reporting a fraction of a loop it never ran. That is a
property, not a list: it covers the inline apply-work skills (`create-ticket`,
`create-pr`, `merge-pr`), the unhooked utilities (`setup`, `update`, `test`,
`release`), and the orchestrators that drive other skills'
loops without running one of their own (`ship`, `handoff`). The
ten skills that run a write → judge loop over their own subagents
report it, with a constant `<cap>` of **3**. `/acs:code` reports the
iteration of ship.yaml's review-code → code loop it is on, whose ceiling is
that loop's `max_iterations`, the same on every delivery path.

**Sanctioned substitutions.** A skill that runs without a ticket drops
`<ticket-id>` from the heading and replaces the **Ticket** line with a
one-line label naming what the run covered — **Scope** for the
configuration utilities (`setup`, `update`), **Run** for the
two run-oriented ones (`test`, `release`), whose subject is an execution
rather than a scope. `/acs:handoff` additionally puts the `continue_with` command in **Next**. No other label
substitution is sanctioned; per-skill Results/Next content is fixed in each
SKILL.md's "Completion report" section.

### The result document (input to post-<skill>.py)

```json
{
  "status": "completed | failed | interrupted",
  "stop_reason": "session_end | needs_input | context_pressure (interrupted only)",
  "states":   { "<skill-specific result data for the next skill>": "..." },
  "findings": [ {"severity": "blocking|info", "dimension": "...", "detail": "..."} ],
  "errors":   [ "..." ],
  "handoff_summary": "only when status=interrupted"
}
```

`status` is REQUIRED. A post hook invoked with no result document at all, or
with one that omits `status`, exits 1 rather than defaulting to `completed` --
defaulting would finalize the run and open the next gate on nothing. The same
rule holds one layer down: `finalize_run` raises on a result with no status,
so an in-process caller cannot bypass it either.

**Five `states` keys are DERIVED, not read (MAR-523, MAR-578).** `run_post`
computes `verifier_passed`, `tests`, `pr`, `review.iterations` and
`review.guard_denials` from the artifacts before persisting the document, and
the computed value wins:

| Key | Source | When it cannot be computed |
|---|---|---|
| `verifier_passed` | `/acs:review-code`'s `iter-<n>/verdict.json` for the highest iteration (MAR-527), whose own `passed` is derived from its findings | **`false`** — this key answers "may the next step run", and with no evidence the answer is no |
| `tests` | the review's own suite run, else the last iteration's `iter-<n>/implementer*.json` reports (`coverage_target` from `tests.coverage`; a run started before ADR-0109 has `execute*.json`, read the same way) | the coordinator's value is kept |
| `pr` | `gh pr list --head <branch>` | the coordinator's value is kept, flagged unverified |
| `review.iterations` | `/acs:review-code`'s verdict, lens and adjudication artifacts on disk | the coordinator's value is kept |
| `review.guard_denials` | the length of `invocations[-1].guard_events` on `steps/<skill>/state.json` | **absent, not `0`** — a run that never tripped the file-map guard carries no key |

A disagreement is recorded, never silently resolved: `runs[-1].derived_states`
carries `values`, a one-line `provenance` for every key considered (including
the ones it declined to compute, and why), and `overrode` — the
supplied-vs-derived pairs — which is also printed on stderr. `verifier_passed`
is derived only for `review-code`, the one skill whose verdict `/acs:create-pr`
gates on. **A coordinator cannot open that gate by writing `true`.**

`tokens`, `role_usage`, `model_usage`, `cost_usd`, `cost_basis` and
`api_duration_ms` are legacy fields (ADR 0103, ADR 0104): the result schema
still accepts them, so an older coordinator's document validates, and nothing
reads them — acs records no usage. Emitting them is harmless but has no effect.

`post-<skill>.py` finalizes `runs[-1]`, merges `states` (replaces `findings` /
`errors` when present), updates `run.json` and `tickets-index.json`,
releases the `.lock`, and performs per-skill extras (create-pr → ticket
`in_review`; merge-pr → ticket `done`, epic auto-done check, partition
archived to `archive/<ticket-id>/`).

### Canonical `states` keys per skill

The next skill, a ship.yaml predicate, or a gate brake reads these — keep the
names exact. `acs_lib/derive.py` owns only `DERIVED_KEYS`
(`verifier_passed`, `tests`, `pr`, `review`) and `VERDICT_SKILLS` (`review-code`);
every other key below is persisted verbatim from the result document:

| Skill | Required `states` keys on success |
|-------|-----------------------------------|
| create-prd | `prd` `{path, files:[...]}`, `pr` `{number, url, branch}` |
| create-architecture | `architecture` `{path, hld:[...], lld:[...]}`, `pr` `{...}` |
| create-ticket | `ticket_id`, `type`, `needs_design`, `children: [ids]`, `prd_trace` `{feature, divergence}` |
| create-design | `design_path` (the published `design.md` — the docs folder, or the partition when there is no checkout), `decision` (one line) |
| analyze-requirements | `ready_for_planning: true/false`, `api_surface: true/false` (the `api_surface_changed` predicate), `questions_open` (int) |
| create-impl-plan | `plan_path`, `plan_approved: true/false` (written by `plan-approval.py`), `file_map` (object) |
| create-api-contract | `contract_path`, `items` (int), `traced_acs: [...]` |
| create-test-docs | `cases` (int), `e2e_cases` (int), `untraced_acs: [...]` (empty on a completed run) |
| code | `branch`, `delivery_path`, `plan_path`, `plan_approved`, `file_map`, `specs_implemented: [...]`, `commits: [...]` (plus `review.guard_denials`, derived, only when the file-map guard denied a write) |
| review-code | `verifier_passed: true/false` (the /create-pr BRAKE, derived from `verdict.json`), `reviewed_sha`, `review` `{iterations, findings_open}`, `tests` `{passed, failed, coverage_percent, coverage_target}` |
| create-e2e-tests | `suites_written: [...]`, `cases_covered: [...]` |
| create-pr | `pr` `{number, url, branch, base}` (the /merge-pr brake) |
| merge-pr | `merged: true/false`, `merge_strategy`, `readiness` `{ci, approvals, conflicts, protections}` |

On failure, keep whatever is true (e.g. a `/acs:review-code` coverage
hard-fail records `verifier_passed: false`, achieved coverage, and the reason
in `stop_reason`).

The exempt non-ticket merge path (`/acs:merge-pr --pr <n>`) has **no** result
document and writes **none** of the merge-pr ticket states above — there is no
partition. It has no post step either: it touches no ticket index, pipeline,
or archive, and there is nothing repo-level to record (ADR 0104).

### The Build and Test skills at a glance

Six skills were carved out of what `/acs:code` and `/acs:test` used to do
alone, so each produces ONE artifact another step can read, and each is
runnable on its own:

| Skill | Reads | Writes | Downstream use |
|---|---|---|---|
| `analyze-requirements` | the ticket, PRD/requirements/architecture, the codebase, the ledger, and its own previously published `analysis.md` (the survey starts from it) | three stages — survey the impact, clarify with the user (one grouped ask; confirmed criteria and `needs_design` written into the ticket via `acs.py ticket save`), store — ending in `analysis.md` (front matter `ticket`, `ready_for_planning`, `api_surface`, `needs_design_recommendation`) published to `docs/tickets/<id>/` | the `api_surface_changed` predicate; `/acs:create-impl-plan`'s planner plans from the impact map, and `create-api-contract` / `create-test-docs` read it; the next analysis of the ticket starts from it; a not-ready analysis returns `needs_input` |
| `create-impl-plan` | `analysis.md` and `design.md` when present, else the ticket | `plan.md` + the executor file map, plan approval on STANDARD/COMPLEX | `/acs:code` implements it; `on_replan` re-runs it when execution finds the plan wrong |
| `create-api-contract` | `plan.md`, `analysis.md`, the architecture set, existing contracts where the repo keeps them (else `docs/api/`) | `api-contract.md` + machine-readable contract files | code implements it; create-test-docs derives contract cases; `/acs:review-code` checks conformance |
| `create-test-docs` | the ticket's ACs, `plan.md` and `api-contract.md` when present | `test-cases.md` (`TC-n`, traced AC, type unit/integration/e2e, steps, expected, target suite) | the implementer writes tests from it; `create-e2e-tests` reads its e2e-typed rows |
| `create-e2e-tests` | the e2e-typed rows of `test-cases.md`, `settings.tests.e2e` | e2e suites at the repo's configured location, on the ticket branch | `run-e2e-tests` executes them |
| `run-e2e-tests` | the ticket's suites (from `test-cases.md`, falling back to the plan's Test-plan section) | the run artifact + triage | `on_fail: {relay_to: code}` with the fix-loop cap |

`/acs:code` keeps the implementers, the escalation triggers and the boundary;
its plan phase is `/acs:create-impl-plan` and its review is
`/acs:review-code`. It reads `plan.md` when there is one and otherwise works
from the ticket's acceptance criteria. When execution finds the plan wrong it ends `failed` with
`stop_reason: plan_superseded`, which is what `on_replan` in ship.yaml exists
to handle.

## Subagent messaging

Coordinator <-> subagent communication uses three message shapes — `task`,
`result`, `handoff`. The XSD that used to define them, and the
`validate_xml.py` that checked against it, are gone: a second schema language
for a three-element vocabulary bought a dependency on `xmllint` and a file
nobody read. The **SubagentStop hook** validates what a subagent returns
(`acs_lib.lifecycle.validate_message`): well-formed, one of the two permitted
roots, and the three attributes the snapshot path is derived from —
`skill`, `phase`, `iteration` — plus `slice` when a coordinator fanned the
role out (a short id of letters, digits, `_` and `-`).

- `phase` is the role the message belongs to (`surveyor`, `author`,
  `plan-reviewer`, `implementer`, …). `/acs:review-code` is the exception its
  own fan-out needs: a lens returns `phase="review"` and carries its lens back
  as `lens="A|B|C|D|E"`, which is how the hook finds that lens's verdict file,
  and an adjudicator returns `phase="adjudicate"`.
- Subagents receive the `<task>` inside their prompt and must return the
  `<result>` as the final content of their reply — nothing after it.
- `<handoff>` is only for step-coordinator -> /acs:ship returns: compact
  (~1 KB), referencing workspace files rather than inlining detail.
- Subagents never spawn sub-subagents; every fan-out is the coordinator's
  (see "Fan-out inside a skill"); a judge runs after all writers of its
  iteration — and the integration pass, when one runs — complete.
- A sliced instance carries `slice="<id>"` on its task and echoes it on its
  result; the SubagentStop hook takes the snapshot's file name from it. A
  sliced judge's task also carries `<constraint name="dimensions">`.

**Phase results are JSON.** What a step ends with is `result.json`, validated
against `result.schema.json` by `acs result validate` and by the post-hook —
in the language the kernel is written in.

## Subagents

25 agent files named `<skill>-<role>` in `plugins/acs/agents/`, 25 reachable —
every one of them: the files on disk are exactly the roles the naming
convention makes reachable (`acs_lib.skills.unreachable_agents` is empty).
There is no generic planner / executor / verifier set. Each skill owns only
the roles its own work needs, named for that work (ADR-0109), and each role
has a **kind** in `acs_lib.skills.ROLE_KINDS` that the hooks act on:

| Kind | What the role does | Hooks | Model tier (`settings.models`) |
|---|---|---|---|
| `survey` | reads the repo and records notes and open questions; writes only its own workspace files | recorded, not guarded | `planner` |
| `write` | produces the deliverable — the repo, or the workspace draft | the file-map guard applies while it runs | `executor` |
| `judge` | re-derives and judges fresh; read-only by charter | recorded, not guarded | `verifier` |

A role's kind does not pick its model: `settings.models.<skill>.<role>` does
(ADR-0115). A new role needs one line in `ROLE_KINDS`, one in the scaffold table
(`acs_lib.models`), and no new
setting.

| Skill | Subagents (kind) |
|---|---|
| `analyze-requirements` | `analyst` (write — a `requirements` survey lane, a `synthesis` pass, then a `draft` pass after the user's answers) · `impact-analyst` (survey — one per code area, on the `executor` tier) · `impact-reviewer` (judge); the loop is run by a controller, `acs.py analysis` (ADR-0114) |
| `create-prd` | `surveyor` (survey) · `author` (write) · `reviewer` (judge) |
| `create-architecture` | `architect` (write) · `reviewer` (judge) |
| `create-design` | `designer` (write) · `design-reviewer` (judge) |
| `create-docs` | `author` (write) · `reviewer` (judge), one pair per doc set |
| `create-impl-plan` | `planner` (write) · `plan-reviewer` (judge) |
| `create-api-contract` | `contract-author` (write) · `contract-reviewer` (judge) |
| `create-test-docs` | `test-designer` (write) · `trace-reviewer` (judge) |
| `code` (and its four legs) | `implementer` (write), one per file-map partition |
| `review-code` | `lens` · `adjudicator` (judge) |
| `create-e2e-tests` | `test-writer` (write) · `suite-runner` (judge) |
| `docs-sync` | `doc-updater` (write) · `drift-reviewer` (judge) |
| `create-ticket`, `create-pr`, `merge-pr` | none — the coordinator runs the steps inline from `skills/<skill>/references/` (`materialize.md`, `publish.md`, `merge.md`) |

The surveyor runs on iteration 1 only and freezes its notes; the author
writes from them. The lifecycle hooks do not track `review-code`'s lenses and
adjudicators (`acs_lib.lifecycle.UNTRACKED_ROLES`): they fan out one per lens
and one per finding, and the coordinator persists what they return itself.

Conventions:

- Frontmatter: `name` (`<skill>-<role>`) and `description` (what the role does
  for `/acs:<skill>`, ending "Spawned by the /acs:<skill> coordinator with a
  JSON task; not for direct invocation."). Survey and judge roles carry
  `tools: Read, Glob, Grep, Bash, Write`; write roles carry
  `disallowedTools: Agent, Skill`. No `model:` or `effort:` key — the
  *actual* model/effort comes from `settings.json` `models.<skill>.<role>`
  (inheriting where unset). `acs step start` writes
  `.claude/agents/acs-<skill>-<role>.md`, a copy of the agent carrying that
  `model:`/`effort:`, for every entry that sets one, and reports the name to
  spawn per role in `context.agents`. An unknown model id or unsupported effort
  fails at spawn — surface the error, never silently fall back.
- Spawn with `subagent_type: "acs:<skill>-<role>"`; the task and the result
  carry `phase="<role>"`.
- Survey and judge roles are read-only with ONE exception: each writes its
  own phase artifacts under `steps/<skill>/` (notes, report — see Phase
  artifacts above). Only write roles mutate real targets (the repo for /code
  and the product-level skills, the workspace artifacts — specs, and the
  ticket-document DRAFTS under `steps/<skill>/` — for the rest; a document in
  the ticket docs tree is published by the coordinator from the reviewed
  draft, never written by a subagent, which the file-map guard enforces), and
  they record what they changed in their `iter-<n>/<role>.json` report. A
  judge must judge fresh — it never sees the writer's reasoning, only
  artifacts.
- Judges re-run the actual checks (tests, coverage, builds, doc diffs) —
  trust nothing recorded that they can cheaply re-verify.

## The analyze-requirements controller (ADR-0114)

`/acs:analyze-requirements` is the one skill whose loop runs on a controller
rather than on SKILL.md prose. `acs.py analysis <verb>` (`acs_analysis_commands.py`
over `acs_lib/analysis_loop.py` and `acs_lib/analysis_publish.py`) owns the
loop's position in `steps/analyze-requirements/loop.json` — written only by
the controller, validated against `schemas/analysis-loop.schema.json` on every
write. The coordinator performs ONE action at a time and reports it:

| Verb | Reads / does | Moves the loop to |
|---|---|---|
| `next` | read-only: prints the one action (`plan`, `survey`, `synthesize`, `clarify`, `draft`, `review`, `publish`, `completed`, `blocked`, `failed`) with every path it involves | — |
| `plan --areas a,b` | declares the survey lanes once: the analyst's `requirements` lane + one `impact-analyst` lane per area (`repo` when none; `requirements`, `synthesis`, `survey`, `repo` are reserved → `area-<name>`) | `survey` |
| `record-survey` | every lane's `<result>` snapshot, notes and JSON report; joins the notes into `iter-1/authoring.md` | `synthesize` (always: ≥ 2 lanes) |
| `record-synthesis` | the synthesis snapshot and notes; re-joins with the synthesis last | `clarify` |
| `record-clarify [--blocking-open]` | the joined notes and the ledger's open count | `draft` (with `--blocking-open`, the not-ready arm: published, then `blocked` needs_input) |
| `record-draft` | the draft snapshot, `analysis.md`, `iter-<n>/analyst.json` (and `iter-<n>/authoring.md` on n ≥ 2); records the draft's sha256 | `review` |
| `record-review` | the three judge slices' snapshots and reports; joins them into `iter-<n>/impact-reviewer.md`; parses every `<finding severity dimension file>` | `publish` on a pass; else `failed`/`stalled`, `failed`/`cap` (iteration 3), or `draft` n+1 |
| `publish` | refuses unless the last review passed and the draft is the reviewed bytes; runs `front_matter_check` and `structure_lint` (a finding fails the iteration); copies the draft byte-for-byte to `artifact_path(…, "analysis.md")`; `git add` and `git commit` on the ticket docs folder pathspec only, with `conventions.COMMIT_SUBJECT`; never pushes | (unchanged) |
| `record-publication` | re-reads the published bytes and `git show HEAD:<path>` | `completed` |

Rules the code holds, each with a transition test in
`tests/acs/test_analysis_loop.py`:

- **Derived, never asserted.** No verb takes a verdict. An iteration passes
  iff every judge slice returned `status="completed"` with zero
  `severity="blocking"` findings; a slice with `status="failed"` contributes a
  `review-failed` blocking finding.
- **Stall.** The blocking set — (dimension, file, whitespace-normalised text),
  de-duplicated, order-insensitive — identical to the previous iteration's
  ends the run `failed` with `stop_reason: stalled`.
- **Cap.** 3 draft → review cycles; lanes and the synthesis do not count.
- **Blocked spends nothing.** A missing or malformed snapshot, a snapshot whose
  `skill`/`phase`/`iteration`/`slice`/`ticket-id` is not the dispatched one, a
  missing artifact or an unreadable report blocks (`kind: machinery`); an
  agent's `status="failed"` blocks (`agent_failed`); `needs_input` blocks and
  hands back `clarify` on the same iteration. The same `record` verb clears
  the block once the evidence is there.
- **Restart.** A loop that ended (`completed`/`failed`) under a step
  invocation that was itself finished (or interrupted with `needs_input`) is
  history: the next invocation's `next` answers `plan`. A loop that ended under
  an invocation interrupted for any other reason resumes straight to Finish.

## Workspace layout (normative example)

Durable state is split by AUDIENCE. The documents a human reads or reviews live
in the consumer repo and are committed with the change; the run ledger — every
fact a hook or a walk reads — stays in the gitignored workspace.

Who commits the documents (ADR 0090): the skill that publishes a Build-phase
document commits it on the ticket branch. `ticket.md` and `design.md` are
published in the Design phase, BEFORE a ticket branch exists — acs never
commits to the default branch — so their writers leave them in the working
tree and `/acs:analyze-requirements`, the first Build step, commits the ticket's
whole docs folder when it creates the branch.

```
<checkout>/docs/tickets/<ticket-id>/    # fixed: artifacts.TICKETS_PATH
  ticket.md        # YAML front matter = the ticket fields; body = Description,
                   #   Acceptance criteria, Clarifications (a read-only mirror)
  design.md  analysis.md  api-contract.md  plan.md  test-cases.md

<workspace>/<repo-id>/                  # repo-id from git remote: owner-name
  tickets-index.json  counters.json
  runs-index.json                       # every run: id, workflow, subject, status
  sessions/<checkout-id>/               # ONE directory per checkout, not five files
    pointer.json                        #   the current RUN and STEP
  archive/<ticket-id>/                  # moved here by post-merge-pr
  runs/<run-id>/                        # THE PARTITION -- a run, not a ticket
    run.json                            #   the run machine (§4.3)
    subject/                            #   ticket.json | prompt.md | the document
    requirements.md                     #   step 1's artifact, promoted
    clarifications.json
    lock.json  lock-events.jsonl  agents/<agent_id>.json  handoff-context.md
    steps/<skill>/
      state.json                        #   the step machine (§4.4)
      result.json                       #   the post-hook's input
      plan.md  api-contract.md  ...     #   CURRENT artifacts
      iter-<n>/                         #   the AUDIT TRAIL, one dir per iteration
        authoring.md  <role>.json  <role>.md  <role>-message.xml
        authoring-<id>.md  <role>-<id>.json|.md  <role>-<id>-message.xml   # sliced
        verdict.json  lens-<A..E>.md ...
```

### Ticket artifacts (`acs_lib/artifacts.py`)

`artifacts.py` owns the layout and every read/write of it.

- **Resolution is first-existing, then a write target.**
  `artifact_path(checkout_root, tdir, ticket_id, name)` returns the
  first of `<docs>/<name>`, `<tdir>/<name>`, `<tdir>/<legacy rel>` that exists;
  when none does it returns where a WRITE should go — `<docs>/<name>` when
  there is a checkout, else `<tdir>/<name>`. Callers tell the two apart with
  `os.path.isfile`. This is why a partition built before the move keeps working
  unchanged, and why the gates' "looked in the ticket's docs folder and in
  `<partition>`" wording is literally true.
- **`status` is DERIVED, never stored.** `ticket.md` carries every ticket field
  EXCEPT `status`; `derive_status(tdir, ticket=None)` computes it from the
  ledger — `done` when the partition is archived, `merge-pr` completed, or (for
  an epic) every child is done; `in_review` when `create-pr` completed, or a
  delivery-ticket skill completed with a `pr` in its state file; `in_progress`
  when any step other than `create-ticket` has a non-`skipped` status (or any
  child is not open); `open` otherwise. `load_ticket()` puts it back in the
  returned dict, so callers are unchanged. A committed document and the run
  state can no longer disagree, because only one of them holds the fact.
- **`load_ticket` / `save_ticket` are the seam.** `load_ticket(tdir)` reads
  `ticket.md` from the docs folder, else `ticket.json`, else follows
  `ticket.json.moved`; a corrupt file warns on stderr and reads as absent.
  `save_ticket(tdir, ticket)` writes `ticket.md` when `md_target()` says the
  tree is active and this ticket belongs to it, else `ticket.json` exactly as
  before. `acs_lib.state.load_ticket`/`save_ticket` delegate here with
  unchanged signatures. On the `ticket.md` path a save whose rendered bytes
  equal what is on disk writes NOTHING and does not bump `updated_at`: several
  callers save after flipping only `status`, which `ticket.md` does not store,
  and a tracked document must not be re-dirtied for a field that never
  reached it.
- **The body round-trips verbatim.** `render_ticket_md` copies `description`
  in under `## Description` unchanged, and a description is arbitrary markdown
  — every shipped description template is `## `-headed, and `task-default`
  opens with its own `## Description`. `parse_ticket_md` therefore does NOT
  scan forward for the next `## `: it finds the two sections that follow the
  description from the END of the body (the last `## Clarifications`, the last
  `## Acceptance criteria` before it, the first `## Description` before that).
  Neither trailing section can emit a `## ` line of its own — a criterion's
  first line is numbered and its continuations indented, and the
  clarifications mirror folds each entry onto one line — so the description
  survives whatever it contains. A forward scan silently truncated it, which
  is a deletion inside a committed document.
- **Migration is one idempotent command.** `acs.py artifacts migrate
  [--dry-run]` renders each live partition's `ticket.json` into
  `<docs>/<ID>/ticket.md`, copies `design.md` and `phases/code/plan.md` across
  when absent, writes `<tdir>/ticket.json.moved` (`{ticket_id, moved_to,
  relative, migrated_at}`) and unlinks `ticket.json`. It never touches
  `archive/`, refuses while a partition to move holds a `.lock`, and re-running
  it is a no-op. `acs.py artifacts show [--ticket ID]` prints where a ticket's
  documents actually resolved, which source answered, and the derived status.
- **The location is fixed, not a setting.** `TICKETS_PATH` (`docs/tickets`)
  is a constant the hooks own; `ticket_docs_root(checkout_root)` and
  `ticket_docs_dir(checkout_root, ticket_id)` anchor it to the checkout, and
  there is no opt-out (ADR-0102). The tree is ACTIVE when its root directory
  exists; `migrate` creates it, and so does a skill writing into `<docs>/<ID>/`.
- **The docs tree is a control input.** `acs_lib/filemap.py` denies a writing
  agent's write under `<checkout_root>/docs/tickets/` with exit 2 and
  "`<target>` is the ticket docs tree (`docs/tickets/`), a control input only
  the coordinator and the ticket skills write." — the same polarity as the
  guard's own `active-agents/` and `iter-*-filemap.json` records: a writer
  that can rewrite the ticket can rewrite its own scope.

### Concurrency: two mechanisms, both fail closed

**Repo-level guards.** `tickets-index.json` and `counters.json` are
read-modify-written by any session in any worktree, so each write holds an
`O_EXCL` guard file beside it (`repo_guard`, a bounded spin: `ACS_GUARD_ATTEMPTS`
× 0.05s, default 200 → 10s, clamped at `GUARD_ATTEMPTS_MAX` since a longer spin
only outlives the 25-second bound Claude Code puts on the pre-hook). **Exhausting
the budget raises `GuardTimeout` and writes nothing.** It used to write anyway, which meant the guard covered every
case except the one it exists for. A refused write is recoverable; a clobbered
one is invisible — and for `counters.json` it means two sessions holding the
same ticket id. In `post-<skill>.py` the refusal exits 1 and says which half
landed: the run, `ticket.json` and `run.json` are already durable, and the
index self-heals on the next post hook — except after **merge-pr**, the
terminal post hook, where nothing runs afterwards and the message says so
instead. Every other entry point
reports the refusal as `acs <command>: <reason>` and **exit 2**, and any that
holds the ticket lock releases it first: a skill that did not start, a handoff
that did not hand off, or a SessionEnd net that did not release would otherwise
strand the lock under a pid that is about to exit — and a cross-host lock
stranded that way does not read as stale for 24 hours.

A guard file left behind by a writer that crashed is reclaimed, but the test is
deliberately narrow. Age alone cannot tell a crashed writer from a slow one, so
a reclaim requires **both** that the file outlive twice the configured budget
(`guard_stale_seconds`, so raising `ACS_GUARD_ATTEMPTS` for slow storage widens
the patience rather than the hole) **and** that its recorded holder — the guard
file carries the writer's pid and hostname — is not a process still running on
this host. Releasing is symmetric: a holder unlinks the guard only if it is
still its own, so a writer whose guard was reclaimed cannot strip the guard off
whoever reclaimed it. Both halves are what keep two writers out of the critical
section at once.

**The ticket lock.** `<ticket-id>/.lock` records the holder's `checkout_id`,
path, pid, hostname and start time. `lock_staleness(lock)` returns a verdict
*and its basis*, because only one of its two regimes actually observes the
holder:

| Regime | Evidence | Verdict |
|---|---|---|
| Same hostname, integer pid | `os.kill(pid, 0)` — a real liveness probe | live → not stale; gone → stale; not ours to probe → not stale |
| Anything else (foreign host, absent hostname, non-integer pid) | **none** — the pid names a process in another machine's namespace, so it is deliberately not probed | age only: stale after `LOCK_MAX_AGE_HOURS` (24h) |

The second row is the ordinary case for containers, CI runners and worktrees on
different machines, and it means a *live* holder elsewhere reads as stale once
24h pass, while a *dead* one reads as live until then. Nothing is removed on the
verdict alone: `check_lock` reports the basis and the operator decides.
`release_lock` still refuses another checkout's lock; breaking one goes through
**`acs.py lock force-unlock --reason "…"`**, which appends the break — who, from
where, why, and the staleness verdict it did not obey — to the ticket's
append-only `lock-events.jsonl` *before* removing the file. `acs.py lock status`
prints the same view without changing anything.

## Nothing owed — a no-op is evidence, never an absence

Which steps run is no longer a question: **every step runs on every run**.
What varies is whether a step has work, and that is the SKILL's judgement,
recorded as data.

A step that owes nothing is settled by its own **pre-hook**, from the plan's
`## Contract` block, before any coordinator is spawned: the step is recorded
`completed` with an `outcome` naming why, and the Skill invocation is refused.
Milliseconds, zero tokens.

```
steps.create-api-contract = {status: "completed", outcome: "no_surface_owed",
                             summary: "CLI-only change; no HTTP surface, no browser flow"}
```

This is strictly more than the `skipped` status it replaces. `skipped`
recorded that a workflow predicate was false, which never distinguished *the
plan says nothing is owed* from *nobody asked* — and it cost the same as this
does, which is nothing.

**Silence is not permission to skip.** A plan that does not mention an
artifact leaves the step to do its work. The alternative — treating absence as
`false` — would let an old plan silently disable a step.

The four steps that can owe nothing, and what each consults:

| Step | Reads | Outcomes |
|---|---|---|
| `create-api-contract` | `owes.api_contract` | `contract_written` · `no_surface_owed` |
| `create-test-docs` | `owes.test_cases` | `cases_written` · `no_cases_owed` |
| `create-e2e-tests` | `owes.e2e` | `tests_written` · `no_e2e_owed` |
| `run-e2e-tests` | the repo's harness | `passed` · `no_harness` · `nothing_to_run` |

A failure is **not** an outcome. A step that could not do its work records
`status: failed` with an error — the distinction is what keeps "nothing was
owed" from being confused with "something went wrong".

Ticket flags still steer the skills that read them (`needs_design` gates
`/acs:create-design`; `docs_only` drops tests-first and the coverage hard fail
in `/acs:code`), but they are inputs to a skill, never predicates in a
workflow.

## Testing layers — unit always, e2e by configuration, CI at the gate

Tests belong to the same changeset as the change (like docs), and *executing*
unit suites is verification, which `/acs:review-code`'s final gate owns — so there is
deliberately no skill that "writes the unit tests" as a separate step. What the
Test phase adds is the layer the code loop cannot cover from inside itself:
`/acs:create-test-docs` writes the traced `TC-n` case set (Build phase, so the
cases exist before the code does), `/acs:create-e2e-tests` turns the e2e-typed
rows of that set into suites, and `/acs:run-e2e-tests` executes the configured
suites against the finished changeset and drives the triage loop. Three layers:

| Layer | Authored | Executed & gated |
|-------|----------|------------------|
| Unit + coverage | /code implementers, tests-first (TDD) per the spec's Test plan | Implementers iterate against the AFFECTED tests only. The full suite runs **once per review iteration**, in `/acs:review-code`'s final gate, which runs it and reads coverage off that same run vs `test_coverage_percent` — hard fail below target (`docs_only` relaxes only this layer's authoring, never the suite-must-stay-green rule). It records both in `iter-<n>/verdict.json`, and `states.tests` derives from there, so the recorded numbers are the review's independent finding rather than the implementer's self-report; `acs_lib.derive_tests` falls back to the implementer reports when a verdict carries none |
| E2E (`tests.e2e`: command + optional setup/teardown) | /create-e2e-tests writes the ticket's e2e suites after /code; /code implementers run the AFFECTED e2e tests for a spec that declares e2e impact; /setup detects and offers the config and installs the e2e workflow/runner templates | **`/acs:run-e2e-tests` owns the full suite** (setup → command → teardown always) — `workflows/ship.yaml` runs it after `create-e2e-tests`, which is the first point at which the suite is complete. `/acs:review-code` judges the DIFF instead: a spec declaring e2e impact with no matching e2e test change is blocking. |
| CI (the gates /setup installs; runs unit + e2e on the PR) | — | /merge-pr readiness reads CI status — report-only, never auto-fixed |

The chain of declarations keeps e2e honest: `test-cases.md` types each `TC-n`
case (unit / integration / e2e) and traces it to an acceptance criterion → the
implementation plan maps the unit and integration cases into implementer tasks →
`/acs:create-e2e-tests` writes suites for the e2e-typed cases → `/acs:review-code`
demands matching test diffs. A repo without `tests.e2e`
skips the layer entirely — `e2e_configured` is false, so
ship.yaml records `create-e2e-tests` and `run-e2e-tests` as `skipped` and
`create-pr` proceeds, and a hand run of `/acs:create-e2e-tests` refuses with
the same reason. Adding the config later is one `/acs:setup` re-run.

## Requirement clarification — controlled, recorded, never repeated

Clarification is governed by one ledger and four rules. The ledger:
`<partition>/clarifications.json` (schema shipped; append-only via
`hooks/scripts/clarify.py` — add / answer / list). Every Q&A of the ticket
lives there with id (`C-n`), asking skill, status
(`open | answered | assumed | withdrawn`), source (`user | assumption`), and
rationale for assumptions.

1. **Research first.** A subagent never asks what the repo, docs,
   PRD, design, or ledger can answer — researchable facts are researched and
   cited (grounding rules); only genuinely open decisions (user preference or
   business trade-off that changes what gets built) become questions.
2. **Ask once, at the cheapest phase.** Before asking the user ANYTHING, the
   coordinator runs `clarify.py list` and reuses recorded answers — re-asking
   an answered question is a defect. Each skill asks only what ITS phase
   needs settled — ticket scope and the due date at
   /create-ticket, design trade-offs at /create-design, requirement
   clarification (impact, assumptions, refined acceptance criteria) at
   /analyze-requirements, execution-level behavior at /code — batched, not dribbled.
   `/acs:analyze-requirements` is where requirement questions now belong: its
   survey pass ends with `## Questions for the user` (open questions,
   conventional defaults to confirm, refined criteria, a needs_design
   recommendation), and between that survey and its draft pass the
   coordinator asks every one the ledger does not answer in ONE grouped
   `AskUserQuestion` (at most one follow-up round), records each through
   `clarify.py`, and writes confirmed criteria into the ticket with
   `acs.py ticket save`. Only when no user is reachable does a default fall
   back to `--source assumption`; `/acs:create-ticket` parks anything needing
   the codebase read for it rather than asking up front.
3. **Record everything.** Every answer received — interactively or via a
   /ship relay when re-invoking a step — is recorded with `clarify.py add/answer`
   BEFORE acting on it; coordinators feed the ledger into subagent `<context>`,
   and subagents cite the `C-n` ids they relied on (`clarifications_used`).
4. **Assumptions are visible debt.** When no user is available (or the user
   says "you decide"), the decision is recorded as `assumed` with a
   rationale; assumptions surface in the completion report's Findings line
   and the PR body until a user confirms (flips to `answered`) or overrides
   them. A silent default is a review finding.

Under /ship: a step that cannot proceed records its questions as `open`,
returns the `needs_input` handoff; /ship relays the user's answers when it
re-invokes the step directly, and the step coordinator records them before
resuming.
(Product-level elicitation — e.g. /create-prd's product definition — lands
in its real artifact, the PRD itself; the ledger is for ambiguity
resolution, not for primary content capture.)

## Living architecture — day-by-day currency by induction

The architecture doc set (the repo's own, else `docs/architecture/`) stays
current through an induction invariant, not a periodic chore:

- **Base case** — /create-architecture bootstraps the doc set verified
  against both the PRD and the actual codebase.
- **Inductive step** — every ticket carries its own architecture delta on
  the SAME branch/PR: /create-design conforms or lists required doc changes;
  `/acs:docs-sync`'s doc-updater names the HLD files and `lld/flows/` diagrams
  to update, from the diff, in its authoring notes after `/acs:code`
  completes; `docs-sync`'s
  drift-reviewer derives the architectural impact from the diff itself (a
  positive, evidenced conclusion — never a default) and blocks before
  `/acs:create-pr` runs when impact exists without matching doc changes.
- **Drift repair (boy-scout)** — commits that bypass the pipeline can still
  desynchronize docs. Both the designer's and the implementation planner's
  surveys (`create-impl-plan-planner.md`, which inherited the former
  `code-planner.md` charter) compare the touched area's docs against current
  code and schedule stale sections for repair as part of the ticket (MAR-72:
  the survey is **best-effort** on TRIVIAL/SMALL work, and its omission there
  is never a finding); widespread drift triggers a
  recommended
  /create-architecture re-run (the full reconcile, shipped as its own
  delivery ticket + docs PR).

Net effect: after every merge the doc set matches the code — "update the
architecture" is not a separate activity but a blocking dimension of every
change that has architectural impact.

The same induction maintains the **living requirements**
(the repo's requirements set, else `docs/requirements/`, one file per feature
area): per-ticket specs are archived change-deltas, so the CURRENT
behavioral contract accumulates here instead — `/acs:docs-sync`'s doc-updater
merges the merged ticket's acceptance criteria and behavior-defining
clarifications (answered/assumed ledger entries) into the touched area's
file; /create-ticket reads it as standing behavior and flags
contradictions; `/acs:review-code` blocks a user-observable behavior change
whose requirements file was not updated. Phrasing rule: the file states what
the product DOES now — current behavior, not change history.

## Size control: tickets, specs, PRs

The PR is the unit of review, and **the ticket is the PR boundary** — every
spec of a ticket lands on one branch in one PR. Size is therefore controlled
at two levers, with an escalation between them:

1. **Ticket sizing (controls PR size).** `/create-ticket`'s coordinator applies a
   PR-size rubric to the type decision: a story/task should yield one
   reviewable PR — rule of thumb ~≤400 changed lines, one concern, ≤~7
   acceptance criteria, grounded in the codebase survey. Above the bar →
   epic with children cut at PR-sized, independently shippable seams.
2. **Spec sizing (controls execution units).** Each spec is one coherent
   slice sized for a single /code implementer pass; the spec count is a size
   *signal*, never a release valve.
3. **Sizing today.** The mid-decomposition "stop and recommend a
   split" step this bullet described through the standalone spec-authoring era belonged
   to the deleted spec-authoring planner (ADR 0066 supersedes ADR 0006);
   `create-impl-plan-planner.md`'s survey (which inherited the former
   `code-planner.md` charter when the plan phase moved) migrated the narrower **Spec-simplicity gate** — when
   a materially simpler decomposition satisfying the same acceptance criteria
   exists, it is surfaced as a question, never a stop — plus (ADR 0069) a
   non-blocking **oversize signal** on the same charter item: when the
   decomposition itself exceeds `create-ticket/SKILL.md`'s sizing rubric's
   `~4-spec`/`~400-line`/`~7-AC` rubric, the implementation planner records
   the split seams in its authoring notes and the plan draft and surfaces a `<question>` through the
   clarification ledger — never a stop.
   Oversized-ticket control is therefore a two-lever chain again: lever 1,
   `/create-ticket`'s upfront PR-size rubric, before any decomposition
   exists; lever 2, this plan-time signal, once the actual decomposition is
   known. On a "split" answer, the planning run terminates with a recorded
   `failed` status and a `/acs:create-ticket split <id>` next step instead
   of continuing silently.

The numbers are deliberate rules of thumb for the authors' judgment, not
hard limits enforced by hooks — splitting at a bad seam (e.g. a child that
cannot build alone) is worse than a slightly large PR; feature flags are the
sanctioned way to keep children shippable when a slice alone would break.

## Forge metadata: two commands, two failure policies

`gh` is acs's only transport to GitHub, and everything acs writes through it
beyond the PR or issue itself — labels, assignee, milestone, reviewers, Project
membership and fields — goes through `acs_lib.forge` (MAR-525), reached as two
commands:

| Command | Performs | Policy |
|---|---|---|
| `acs.py pr metadata fill --pr N` | create-pr step 6a: assignee, the ticket-type label alongside `ACS`, CODEOWNERS reviewers minus the author, the Project item, Status, and Priority / Story Points / Parent | **non-critical throughout** — the PR already exists, so every failure is one `info` finding carrying the command, and the next sub-step still runs |
| `acs.py tracker sync --ticket … ` | create-ticket step 5's batch: issue creation, labels, assignee, milestone, Project membership, `Type`/`Status`, and the same Group-B fields | **critical per ticket, soft per batch** — a failed `gh issue create` is an `error` finding naming the ticket and carrying `gh_failure_hint`, `replayable: false`; the batch continues and that ticket keeps `external` unset for a retry |

Both resolve Project fields the same way: **the board's own spelling wins.** A
field is matched case-insensitively against a fixed table of accepted names
(`Story Points` / `Points` / `Estimate`; `Parent` / `Epic`), an option is matched
case-insensitively against the ticket's value, and a board that defines neither
the field nor the option gets **one info finding naming exactly what was skipped**
— a schema-undefined field is surfaced, never silently ignored, and never a
wrong-type write. A ticket value that is simply `null` is skipped silently: that
is expected data, not a gap.

The runner is injectable and the resolvers are pure, so every arm — including
the ones that only fire when a board lacks a field, or when one call in five
fails — is exercised from a recorded `gh` transcript with no forge. `--gh-replay
FILE` gives the CLI the same seam. Jira is not supported: `gh` is the only tracker transport.

Four rules keep the two flows honest about what they did:

- **The issue body is a precondition, not an argument.** `tracker sync` posts
  each partition's `tracker-body.md`, and `/acs:create-ticket`'s
  `references/materialize.md` is what tells its coordinator to write it. A partition without one is reported under `failed`
  with an `error` finding naming the missing path — never a bodiless issue,
  and never N opaque per-ticket gh errors for one missed step.
- **A create that cannot be parsed is a failure.** `gh issue create` exiting 0
  without printing an issue URL leaves the issue number unknown, so the ticket
  fails and keeps `external` unset. Recording an empty key would have been
  worse than failing: `sync_candidates` excludes any ticket that carries an
  `external`, so the half-written ticket would never be retried.
- **`command` is shell-quoted.** Every finding's command is documented as
  ready to re-run, which means a human runs it. It is rendered with
  `shlex.quote`, so a milestone of `Q3 2026; rm -rf /tmp/x` replays as one
  `gh` call with one odd argument rather than two commands. The executed calls
  were never affected — they are argv, never `shell=True`.
- **Every degraded call carries its `hint`.** The finding shape is
  `{severity, area, message, command, error, hint, replayable}`, and `hint` is
  derived from `error` via `gh_failure_hint` when the call site does not pass
  one (ADR-0088). Without it a 403 "GitHub access is not enabled for this
  session" — the one failure with a specific remedy — reads like a mistyped
  label name.

The reviewer set is CODEOWNERS minus the author, and "minus the author" is a
normalised comparison: a leading `@` is stripped and case is folded on both
sides, because CODEOWNERS writes owners `@`-prefixed while `--author` is passed
bare. `--author` is optional and `@me` is accepted; when it is absent the login
is resolved with `gh api user`, and when even that fails the flow says so in one
info finding rather than silently requesting the author as their own reviewer —
the owners are comma-joined into ONE `gh pr edit --add-reviewer` call, so a set
that names the author is rejected whole and nobody is requested.

The milestone the sync writes comes from `ticket.milestone`, falling back to
`settings.tracker.milestone`; **both are declared** in their schemas, which is
what makes the arm reachable for a real ticket rather than only for a fixture.

## Bootstrap: `/acs:setup` is a conversation over a wizard

`setup/SKILL.md` was 1,003 lines, most of them mechanics. Since MAR-526 the
skill asks and explains; `setup_wizard.py` writes, reached as two commands:

Setup is optional (ADR-0105): no skill needs it first. It sets the ticket
prefix and installs the CI gates — the ticket-link check, tests and e2e —
scaffolds the `models` block, and writes `.claude/launch.json`, the Claude Code
Desktop app's preview-server config, from a dev server it guesses and the user
confirms (`acs_lib.launch_config`: validated against the documented schema,
merged by configuration name so an existing entry is never replaced, and never
written over a file with comments); every other setting keeps its default until
someone edits `.acs/settings.json` by hand.

- **`acs.py setup detect`** — read-only. Which settings exist and **in which
  scope**, the resolved workspace, whether both ignore layers are in place and
  whether a broad rule is swallowing `.acs/settings.json` or `.acs/ci/`, the
  toolchain, plausible test commands, which CI installs are already present,
  and which retired keys (ADR-0102) a settings file still carries.
- **`acs.py setup apply --answers FILE`** — the project settings, both ignore
  layers, the workspace create-and-probe, and the CI copies. An answer equal to
  its built-in default is never written, and is removed when an earlier run
  wrote it (`defaulted` in the result), so the file carries only choices.

**Idempotence is the contract.** `/acs:setup` is re-run whenever a gate is added, and a repo initialised by an older acs is expected to be *repaired* by
a re-run. So every settings write is a read-update-write merge (unknown keys
preserved for forward compatibility, nested objects merged rather than
replaced), every ignore entry is added only when `git check-ignore` says it is
missing — probed **with** its trailing slash, since a directory-only rule does
not match a bare path that does not yet exist — and every CI copy is a refresh.
The result splits into `changed` and `unchanged`, so a re-run is visibly a
no-op rather than silently one; `warnings` is what setup must relay but must
not fix (a `!.acs/` negation is the user's configuration to decide); and
`--dry-run` reports without writing.

## Settings and templates

- Resolution: `settings.local.json` -> project `settings.json` -> user
  `~/.acs/settings.json`, deep-merged per key (defaults in `acs_lib/settings.py`).
  No settings file is required: every key has a default, `ticket_prefix`
  included (`ACS`, ADR-0105), and only a malformed value (a lowercase prefix,
  an unknown skill or role under `models`) is refused.
  A linked worktree without its own gitignored `settings.local.json` inherits
  the main checkout's.
- There are no format settings: the model follows the repo's own branch, commit and
  PR-title style, and the branch name a script parses is fixed as
  `<type>/<ticket_id>-<slug>` in `acs_lib.conventions`.
- Long descriptions come from templates: built-in name -> `templates/`;
  otherwise `<repo>/.acs/templates/<name>.md`; otherwise absolute path.
- One key configures the pipeline itself, with a working default so an
  existing repo needs no settings change: `workflow.advisories` (default
  `true`, the one-line out-of-order notice the pre-hook prints). No key
  locates a document or the workspace (ADR-0102): ticket documents live at the
  fixed `docs/tickets/<ID>/` (`artifacts.TICKETS_PATH`), the workspace at
  `<main-checkout>/.acs/state-machine`, and a skill finds every other repo
  document through `CLAUDE.md` and the repo itself, creating a missing one at
  its `docs/` convention — `/acs:create-api-contract`'s machine-readable
  contract files go where the repo keeps them, else `docs/api/`. The
  delivery pipeline itself is NOT a settings key: it is the resolved
  `workflows/ship.yaml`, overridden wholesale at `<repo>/.acs/workflows/ship.yaml`
  when a repo ships one.
- The CI ticket-link check (opt-in, /setup Step 2) has no settings block: repo-side
  CI that fails *every* PR whose description names no ticket — its id
  (`PREFIX-\d+`), a `#<n>` reference or an issue link (ADR-0106). /setup copies
  `templates/ci/check-conventions.py` -> `<repo>/.acs/ci/` and
  `templates/ci/acs-conventions.yml` -> `<repo>/.github/workflows/`. The checker
  is intentionally **standalone (stdlib only, no `acs_lib` import)** because it
  runs on a CI runner with no acs install — it reads only `ticket_prefix` from
  the committed project `settings.json` over its own copy of the plugin's
  default (ADR-0105), so a repo with no settings file is checked against the
  default. A present but malformed prefix fails closed; tested by
  `tests/acs/test_conventions_check.py`, which also keeps the checker's copy of
  the exemption constants level with `acs_lib.conventions`.
  The CI check is necessary-but-not-sufficient (workspace proof lives off-repo),
  so the real gate is a required status check on a protected default branch.
  The exemptions are fixed: the `acs-exempt` label, or a head branch matching
  `release/*`, `dependabot/*` or `renovate/*`. The sanctioned way to LAND such a
  PR is `/acs:merge-pr --pr <n>` (also `#n` or a PR URL): a non-ticket mode that
  runs the same four readiness dimensions and branch/worktree cleanup as the
  ticket path but resolves no ticket, writes no partition/state, and skips
  tracker sync and archiving — `acs step start --pr` validates the PR carries
  the `acs-exempt` label (or an exempt head branch) and refuses + redirects to
  `/acs:merge-pr <ticket-id>` when the PR looks ticket-backed. acs writes
  nothing into a consumer's `CLAUDE.md`: that file is the repo's own project
  instructions, and the check above is what holds a hand-made PR to naming its
  ticket.
  Branch names, commit subjects and PR titles are not checked and not
  configured: the model follows the repo's own style, and the one convention a
  script parses — the branch name `<type>/<ticket_id>-<slug>` — is fixed in
  `acs_lib.conventions`, which also holds the exemptions, the `ACS` pipeline
  label (applied by `/acs:create-pr`, read by `/acs:merge-pr --pr`) and the
  built-in template names. There are no local git hooks: a repo that wants them
  uses its own pre-commit configuration.

## Consumer-repo prerequisites

`git`, `python3` (3.9+, stdlib only), `gh` (PRs; also tracker sync when
`tracker.provider=github`), `pre-commit` (recommended — shared local convention
hooks). `xmllint` is no longer
one of them: the XSD and `validate_xml.py` are gone, and what a subagent
returns is checked in-process (see Subagent messaging above), so nothing acs
runs needs an external XML tool. `acs_lib.check_toolchain()` is
the single source of truth for this list (kind = required | recommended |
optional, with per-platform install commands); `/setup` Step 1
(`setup detect`) reports it and names each missing required/recommended tool
with its install hint before configuring anything, so a gap surfaces up front
rather than mid-pipeline.
