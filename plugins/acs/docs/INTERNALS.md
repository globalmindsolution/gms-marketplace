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
| Skills | `plugins/acs/skills/<name>/SKILL.md` | 32 |
| Subagents | `plugins/acs/agents/<skill>-<role>.md` | 32 files, all reachable (13 executor + verifier pairs — the twelve authoring skills plus `create-docs` — 4 apply-work executors, and `review-code`'s lens and adjudicator; no skill has a planner since ADR-0092, and `code` lost its verifier to `/acs:review-code`). Each skill declares the roles it owns under `agents` in `skills/<name>/acs.yaml`; the files on disk are exactly that set |
| Hooks | `plugins/acs/hooks/hooks.json` + `hooks/scripts/` | dispatcher + 19 pre + 19 post |
| Helper CLIs | `hooks/scripts/{acs,citation_check,clarify,codeowners,front_matter_check,handoff,mermaid_lint,metrics_aggregate,metrics_render,migrate_workspace,new-ticket,plan-approval,pr-conventions,prd_conformance_check,record-external,release_notes,setup_wizard,stacked-base,structure_lint}.py` (the `hooks/scripts/*.py` files with a `__main__` entry point, excluding the dispatcher + 19 pre + 19 post hooks counted in the row above and the 2 status lines counted in the row below; the `acs_lib/` package, `usage_reader.py`, `cost_sampler.py`, `claude_code_adapter.py`, `markdown_headings.py`, `consistency_findings.py`, the twelve `metrics_render_*`, `metrics_aggregate_*` and `release_notes_*` siblings MAR-531 split out and the `acs_cli.py` / `acs_commands.py` / `acs_state_commands.py` siblings split out of `acs.py` are importable libraries with no CLI entry point and are excluded; `skill-start.py`, `pipeline-step.py` and `validate_xml.py` are gone with the surfaces they served — `acs step start`, the run ledger's single writer, and the XML message contract — the count is derived from disk by `HelperCliInventoryTest`, so it stays right on its own; this list is the prose that has to be kept level with it) | 19 |
| Status lines (opt-in) | `hooks/scripts/statusline.py` (prompt line: ticket + pipeline glyphs + cost; also samples and persists the real statusLine cost payload into the workspace on every invocation, fail-open, since MAR-1) and `hooks/scripts/subagent-statusline.py` (agent-panel rows for reflection subagents) — configured by hand in the user's Claude Code settings (`statusLine` / `subagentStatusLine`, each a `command` running `python3 <plugin-root>/hooks/scripts/<script>`); /setup no longer offers them, since it configures conventions and CI only. They stay user-owned settings, never forced. A plugin-root `settings.json` default was deliberately NOT shipped: `${CLAUDE_PLUGIN_ROOT}` expansion there is unverified, and a silently broken default is worse than an explicit opt-in. | 2 |
| Workflow files | `plugins/acs/workflows/{phases,ship}.yaml` | 2 (the skill registry and the default delivery pipeline; a consumer may override the latter at `<repo>/.acs/workflows/ship.yaml`) |
| JSON Schemas | `plugins/acs/schemas/*.schema.json` | 14 |
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
   (exit 0) for anything that is not one of the seventeen hooked skills, and
   otherwise runs that skill's gate from `acs_lib.gates` **in-process** (the
   `pre-<skill>.py` wrappers exist for tests and `acs.py gate`, not for the
   hook path).
   Exit 2 blocks the skill before any of its instructions run; stderr names the
   missing INPUT and the skill that produces it. A predecessor's POSITION in
   the workflow is never a reason to refuse (see "Gates: order lives in
   ship.yaml"); the one refusal that names a predecessor's completion is
   `/acs:merge-pr`'s subject brake, which asks whether the step that recorded
   the PR reference completed — an artifact, not a position (see "Where a
   brake lives when the skill is not a step"). This fires for user-typed
   slash commands and model-initiated Skill calls alike — including the step
   skills `/ship` invokes directly.
2. **Post-hooks — coordinator-invoked, gate-backed.** `post-<skill>.py` is the
   skill's mandatory final step (each SKILL.md ends with it). It must be a
   script the coordinator calls because its inputs — final status, stop
   reason, and findings — exist only in the coordinator's context. Token/cost
   usage is the one exception since MAR-1 (ADR 0082): `finalize_run` measures
   both itself, from the run's own Claude Code transcript and a sampled
   statusLine cost figure, rather than trusting a coordinator-supplied value —
   a `tokens`/`cost_usd` pair on the result document is accepted for backward
   compatibility but silently ignored. The pipeline does not depend on the
   model's goodwill: skill-start has already appended an `in_progress` run
   entry, and the ledger it writes is what `acs.py run next` walks, so a
   skipped post-hook leaves the step UN-SATISFIED — the pipeline re-offers it
   rather than moving past it. (Before the skills-independence refactor the
   same fact held the next skill's gate closed; the gate no longer reads it,
   the walk does.)
3. **SessionEnd safety net.** `dispatch.py session-end` finalizes any run this
   checkout left `in_progress` as `interrupted` (and releases the lock), so
   abnormal endings still write state. A hard kill that skips even SessionEnd
   still leaves `in_progress` + a stale lock — the workflow walk reads the step
   as un-satisfied and offers it again, and the next run reconciles.
4. **Lifecycle hooks (MAR-528).** Four more events are bound, each replacing an
   instruction a coordinator had to remember:

   | Event | Matcher | `dispatch.py` mode | What it does |
   |---|---|---|---|
   | `SubagentStart` | `^acs:` | `subagent-start` | records the running agent in `<partition>/active-agents/<agent_id>.json` — **one file per agent**, so the parallel executor fan-out this record exists for cannot lose an entry to a read-modify-write race |
   | `SubagentStop` | `^acs:` | `subagent-stop` | validates the returned XML and writes the phase snapshot (see "Phase artifacts"); **exit 2** sends the subagent back, at most `BLOCK_LIMIT` times |
   | `Stop` | — | `stop` | **exit 2** refuses to end a turn that left a run `in_progress` with no result document, naming the finish command; at most `BLOCK_LIMIT` times per checkout and run |
   | `PreCompact` | — | `pre-compact` | writes `<partition>/handoff-context.md` from the ledger before the window shrinks |
   | `PreToolUse` | `Write\|Edit\|MultiEdit\|NotebookEdit` | `file-map` | **exit 2** denies a write outside the declared executor file map (MAR-529) |

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
   map" was a bullet in the executor charter, and plugin agents cannot carry
   frontmatter hooks, so the enforcement point is the plugin's own `PreToolUse`
   entry, keyed on the active agent `SubagentStart` recorded. The coordinator
   declares each executor task's map with **`acs.py filemap set --iteration <n>
   --task <k> --file …`** (additive, per task, written to
   `steps/<skill>/iter-<n>/filemap.json`); a write outside it is denied while
   an acs **executor** is running, with the executor told to return
   `needs_input` for the file it needs.

   **Failure polarity is split, because the two questions carry opposite
   risks.** Deciding *whether the guard applies* fails OPEN — not an acs
   partition, no executor active (a verifier and the coordinator both
   write outside any task's map legitimately), **no map declared** (a run that
   spawned no executor declares no map), or a call that names no path. A bug there must not
   deny every write on the machine. Deciding *whether this write is inside the
   map* fails CLOSED: an error, a timeout, or a `tool_input` the guard cannot
   read all deny, because a deny control that fails open is silently absent
   while still installed — the failure ADR 0002 records for the other exit-2
   `PreToolUse` hook. Exempt: this executor's own `steps/<skill>/` artifacts,
   and only those. Explicitly NOT exempt, and denied outright: the guard's own
   control inputs — the `active-agents/` record that arms it and any
   `iter-*-filemap.json` — since an executor that can rewrite either can answer
   the guard's own question.

   **Every deny is recorded: `invocations[-1].guard_events` (MAR-578).** A denial used
   to exist only as a line of stderr in a transcript, so "how often does the
   guard actually fire, and on what?" had no answer. Each deny now appends one
   event to the executor's `steps/<skill>/state.json` run entry — `ts`, `skill`,
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
   first that can run while the parallel executor fan-out is in flight.
   `SessionEnd`'s `finalize_run` writes the same file from a hook process too,
   but only at teardown, by which point this checkout's executors have normally
   already finished — normally, because nothing here enforces it: when the
   runtime fires `SessionEnd` is the runtime's business, not this repo's. No
   corruption is reachable: `write_json` is atomic (`mkstemp` + `os.replace`), so a torn or
   truncated state file cannot result. A lost update can: the append is an
   unlocked read-modify-write of the whole document, so when two writes to that
   file overlap — N executors denied inside the same window, the correlated case
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
   task the running executor was given.** Per-task binding is not achievable
   with what Claude Code provides: neither `SubagentStart` nor `PreToolUse`
   carries a task index, and parallel executors of one `agent_type` run at once,
   so there is nothing to bind an agent to its task by. The union still enforces
   the property that actually goes wrong — an executor wandering outside the
   PLAN — while disjointness *between* tasks stays what the coordinator's
   parallel-vs-sequential decision already exists to decide.

## Gates: order lives in ship.yaml; skills keep inputs and safety brakes

Until the skills-independence refactor, `acs_lib/gates.py` encoded the pipeline
ORDER: `_require_completed(tdir, "code", …)` refused `/acs:docs-sync` until a
completed `/acs:code` run was recorded, and so on down the chain. That made the
order enforceable but also made every skill un-runnable on its own, and it put
the same sequence in three places (the gates, `/acs:ship`'s prose, the docs).

`_require_completed` is gone. A gate now answers exactly two questions:

| Kind | Question | Example |
|---|---|---|
| **Input** | Does the artifact or configuration this skill READS exist? | `/acs:code` refuses without `plan.md`: "no plan.md found for SHOP-12 (looked in the ticket's docs folder and in `<partition>`) — run `/acs:create-impl-plan SHOP-12` first." |
| **Safety brake** | Would running now do damage that cannot be undone by re-running? | `/acs:create-pr` refuses a ticket whose recorded `/acs:code` run left `verifier_passed != true`; `/acs:merge-pr` refuses without a PR reference recorded by a completed run; every hooked skill refuses while another session holds the `.lock`. |

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
PRD or the architecture set lives, so the skill that needs one finds it at
Start and stops without it — `create-architecture` without a PRD;
`create-project`, `standardize-project` and `create-docs` without the
architecture set's `hld/tech-stack.md` (ADR-0102). A
`SUBJECT_GATES` row is `f(ctx, payload)` raising `GateError` to refuse; it
resolves a ticket and reads step state through path joins and `read_json`, so
it opens no run and takes no lock, which is what lets `acs gate` reach it too.
A row belongs there only when the skill is not a step AND its precondition is
a property of the subject ticket — anything a run can answer stays in the
skill's `reads` declaration (ADR-0101).

**`acs.py gate` is the pre-hook's dry-run, and it is inert by construction.**
It runs the same `run_pre_payload` with `record_marker=False` and
`mutate=False`, and must produce the hook's exit code and the hook's stderr —
fallback lines, brakes and advisory included. With no current run there is
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

`GATE_INPUTS` in `acs_lib/gates.py` partitions the twenty gates by the input
they check — `none`, `prd`, `architecture`, `ticket` — and a test asserts the
partition covers `GATES` exactly, so a new skill cannot be registered without
declaring which family it belongs to. Input resolution for the ticket family
lives in `acs_lib/gate_inputs.py`: `_require_artifact` looks in the ticket's
docs folder first, then the partition, then a legacy path
(`LEGACY_ARTIFACT_PATHS`, currently `phases/code/plan.md`), and raises the
"run /acs:<producer> <ID> first" refusal when none exists.

**What replaced the order gate: one advisory line.** `acs_lib/advisory.py`
renders it and `run_pre_payload` prints it — after the gate passes, on stderr,
exit 0:

```
acs: docs-sync normally follows code in ship.yaml; code has not completed for MAR-12
acs: create-pr normally follows docs-sync and run-e2e-tests in ship.yaml; docs-sync has not completed for MAR-12
```

`<needs>` are the step's declared `needs`, `<pending>` the unsatisfied ones,
each a prose list ("a", "a and b", "a, b and c"); the verb agrees with the
pending count. The line is suppressed when the skill is not a step of the
resolved workflow, when `settings.workflow.advisories` is false (default true),
or when anything at all cannot be read — `workflow_advisory()` never raises and
never appears on a refusal path. It reads the same ledger the walk does through
`workflow.pending_needs()`, which never writes.

**The two brakes are facts, not ordering.** "Its verifier did not pass" and
"no PR was ever opened" are properties of the ticket that no amount of running
things in a different order makes acceptable. Note the shape of the create-pr
brake: it fires only when `code-state.json` HAS runs. A ticket with no code run
at all passes — you may be opening a PR for work done by hand, and the gate is
not the place to have an opinion about that.

## Skills and the delivery pipeline

### `skills/<name>/acs.yaml` — a skill describes itself

There is no registry. `workflows/phases.yaml` was the fifth central list of
the skills — after the closed enums in the pipeline-state and skill-state
schemas and the two `argparse` copies in `acs start` / `acs finish` — and
removing four of five would have left the one the others were copies of. A
skill is described by its own directory instead:

| On disk | Means |
|---|---|
| `skills/<name>/SKILL.md` | the skill EXISTS. Discovery is a directory listing, so a skill cannot be missing from a list |
| `skills/<name>/acs.yaml` | what acs knows about it: `phase`, `leg_of`, `reads`, `writes` |
| `skills/<name>/state.schema.json` | its `states` keys and its `outcome` vocabulary |
| `agents/<name>-<role>.md` | it owns that subagent role |

```yaml
# skills/create-api-contract/acs.yaml
phase: build
reads:
  required: [plan]
  optional: []
writes: [api-contract]

# skills/code-standard/acs.yaml — a leg, not a step
phase: build
leg_of: code
```

`acs.yaml` is acs's file, not Claude Code's: `SKILL.md` front matter stays the
four keys Claude Code reads, and acs adds nothing to it.

**`reads` / `writes` name artifacts, and they are the load-bearing
declaration.** They are facts about the skill that hold in every workflow, and
they have exactly two readers:

- `acs workflow validate` checks that each step's REQUIRED reads are written
  by an EARLIER step, which is how a step list's order is validated without
  any edge in the workflow file;
- the runtime input gate (`acs_lib/stepgate.py`) checks the same list.

One declaration, two enforcers, so the validator and the gate cannot disagree
about what a skill needs. This is not `needs:` by another name: `needs:` was a
per-workflow edge list an author maintained, duplicating what the skills
already knew.

**A skill that declares neither reads nor writes is not a step candidate.**
`setup`, `metrics`, `handoff` and `ship` itself are skills, not steps, and
that is the whole admission rule. A leg (`leg_of:` set) is not a step either:
a workflow names the entry point, which dispatches.

**Agents are read from the tree**, by the `agents/<skill>-<role>.md`
convention. PRD G8 — every agent file is reachable — is therefore a naming
check (`acs_lib.skills.unreachable_agents`) rather than a registry kept in
step with the tree by hand.

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
  - create-e2e-tests
  - run-e2e-tests
  - docs-sync
  - create-pr

loops:
  - from: review-code
    back_to: code
    max_iterations: 3
    on_exhausted: fail
```

That is the entire file. `workflow.schema.json` **rejects** every key version 2
carried — `when`, `paths`, `requires`, `needs`, `id`, `name`, `stop_after`,
`max_parallel`, `exclusive`, `on_fail`, `boundary`, `delivery` — rather than
ignoring them, and the refusal names where each one went, so a v2 file ports
in one pass rather than three.

The declared order **is** the dependency order and every step runs on every
run. A skill whose applicability was decided by a workflow predicate could not
be run on its own and be trusted, because invoked by hand it never evaluated
the condition the workflow was evaluating for it. So each skill decides for
itself and records why (see *Nothing owed*, below).

`loops:` is the only construct, and it is not a condition: it tests nothing
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

`acs run next` is **the cursor**: the first step in workflow order that is not
`completed`. With no graph there is no ready-set to compute and nothing to
record as skipped. Every verb defaults to this checkout's current run and
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
        per-role models, design source, post_hook path
2. if context.reconcile: reconcile recorded state against reality before continuing
   if context.handoff_summary: read it, light-verify, continue from where it points
3. Reflection loop (max 3 iterations):
     execute -> spawn <skill>-executor(s) (a JSON task; parallel executors
                allowed when outputs cannot conflict; decomposition is coordinator-only).
                There is no plan phase (ADR-0092): iteration 1's executor SURVEYS first —
                mode, inputs, evidence, open questions — records the survey in its
                authoring notes (iter-<n>/authoring.md), and authors from them; an
                open decision comes back as needs_input BEFORE any file is written.
                (/acs:create-impl-plan — which carved /acs:code's plan phase out into its
                 own skill — follows this line exactly, on every run. It cannot vary by
                 delivery path: plan.md is the artifact the path is judged FROM, so the
                 path does not exist yet when it runs — ADR-0095)
     verify  -> spawn <skill>-verifier  (a JSON task; returns a result with findings)
     - every subagent WRITES ITS OWN ITERATION ARTIFACT (see below) and names it
       in its outputs; the message itself stays compact
     - the coordinator persists every message it receives under
       steps/<skill>/iter-<n>/ at the phase boundary, before starting the next
       phase. The messages are JSON, validated in the hook against the schemas
       under plugins/acs/schemas/; there is no second schema language and no
       validate_xml.py.
     - verifier findings == 0 -> done; findings > 0 -> feed findings into next iteration
     - iteration 3 still failing -> stop; final status "failed", findings recorded
4. Write the result document steps/<skill>/result.json
5. python3 <post_hook> --result-file <result.json>                    # MANDATORY final step
```

**No skill has a plan phase (ADR-0092).** The per-iteration re-plan went
first (MAR-71, slice 1b of MAR-69, for `/acs:code`; MAR-300 for
`/acs:docs-sync`; MAR-301 for `/acs:create-project`; MAR-302 for
`/acs:standardize-project`; MAR-305 for `/acs:create-prd`; then
`/acs:create-architecture`, `/acs:create-design`, `/acs:create-requirements`),
leaving a plan step that ran once before the loop. ADR-0092 followed that to
its conclusion: for a skill whose deliverable IS a document, a plan for it is
a second copy of the writing, so the planner role is gone — `/acs:create-docs`
first (ADR-0094), the other twelve authoring skills in ADR-0092's stage 2 —
and the survey a planner used to make is iteration 1's executor's first job,
recorded in its authoring notes. The loop body for every one of the fourteen
skills that run one (the twelve authoring skills, `/acs:code` and
`/acs:create-docs`) is execute → verify only: on iteration 2+, verifier
findings feed straight into the next iteration's **executor** `<context>`,
with no plan phase in between, and the executor authors the remediation.

### Phase artifacts (written by the subagents themselves)

Subagents persist their full work products into the partition — the XML result
carries references, never the bodies (docs/requirements/functional/reflection.md: subagents write their states,
findings, error details, and stop reasons into workspace files):

| Phase | Artifact (under `steps/<skill>/`) | Written by | Contents |
|-------|------------------------------------------------|------------|----------|
| authoring | `iter-<n>/authoring.md` (every authoring skill — the class-D author's notes, ADR-0092/ADR-0094; there is no `plan` row: no skill writes `iter-<n>/plan.md` any more. `/acs:create-impl-plan` is the one skill whose DELIVERABLE is a plan — its executor's survey goes into the same notes and its draft is the per-ticket `plan.md` (MAR-70). It runs BEFORE any delivery path exists — the path is judged from the plan it produces (§3.2) — so it has no per-path shape and no coordinator-authored fast path: every run spawns the executor) | executor | the survey the draft was authored from, iteration 1 (mode with its evidence; inputs read and what each settled; the Upstream inventory — every upstream fact the document was tailored on, cited with a verbatim excerpt, which the verifier corroborates through `citation_check.py` where the skill uses it; ADR-0012 consistency findings; decisions, assumptions and open questions) and, on iteration 2+, the findings addressed; the verifier's `authoring-conformance` dimension judges the draft against these notes |
| execute | `iter-<n>/execute.json` (parallel executors: `iter-<n>-execute-<k>.json`) | executor | artifacts produced, repo files changed, commands/tests run with outcomes, problems hit, clarifications used |
| verify | `iter-<n>/verify.md` | verifier | the full verification report: every check performed with its evidence, every finding in detail (the XML `<finding>` entries summarize this file) |

**The verifier also writes a verdict** (MAR-527):
`steps/<skill>/iter-<n>/verdict.json`, or one `lens-<A..E>.md` per lens for
`/acs:review-code`. It carries a per-dimension result table (by the numbers in
the verifying agent's own charter, where `n/a` is a real answer), the findings, and
`passed` — which is **derived, not asserted**: `passed` is true exactly when no
finding is `blocking`. `acs_lib.verdict.validate_verdict` enforces that, and the
SubagentStop hook runs it, so a verdict claiming a pass over a blocking finding
is refused rather than believed. `verdict.schema.json` pins the shape; that
function pins the meaning, and says so. On full depth the coordinator runs
`acs.py verdict merge` — the conjunction of `passed`, the union of findings, the
worst result per dimension — which is arithmetic over the lens files, not a
second opinion. `states.verifier_passed` is **derived by the post hook** from
the verifier's `verdict.json` (MAR-523) — never copied from the coordinator's
result document, and never concluded from a findings count by hand.

**The XML snapshot is written by the SubagentStop hook** (MAR-528), not by the
coordinator remembering to. The hook fires on `^acs:`-matched agents, validates
the returned message against the SubagentStop hook, and files it at
`steps/<skill>/iter-<iteration>-<phase>.xml` — a path taken entirely from the
message's own `skill`, `phase` and `iteration` attributes, so nothing about it
has to be carried in the coordinator's head. An invalid message sends the
subagent back with the errors, at most twice (`BLOCK_LIMIT`); a still-invalid
third message is let through and the coordinator records the failure, because a
hook that can refuse forever is a hung session. Two consequences worth knowing:
a `<handoff>` is the run's outcome, not a phase artifact, so it validates but
files nothing; and since the schema reads an *absent* `iteration` as `1`, a
subagent must echo its task's `iteration` — one that omits it on iteration 3 is
claiming to be iteration 1, and the hook says so on stderr rather than guessing
at a counter it cannot see. The coordinator still writes the snapshot itself for
work it performs **inline** (TRIVIAL/SMALL lanes, `/acs:merge-pr`), where no
subagent runs and therefore no SubagentStop fires.

**Every statement in a phase artifact must be grounded**: decisions and
analysis cite the file (path + line/section) they are based on; claims about
behavior quote the command run and its relevant output; anything unverifiable
is marked as an assumption for the coordinator to resolve. Each agent body
carries the binding "Grounding (anti-hallucination)" section; ungrounded
plans/reports are a verification finding.

The coordinator's `iter-<n>-<phase>.xml` snapshots plus these artifacts are
what reconcile mode reads on resume — a crash can lose at most the in-flight
phase. Phase persistence + the `in_progress` run entry give the three resume
levels: between steps (gates), within /ship (ledger), and mid-skill
(reconcile mode).

### Why not Claude Code's native plan mode

The reflection loop deliberately does NOT use plan mode
(`EnterPlanMode`/`ExitPlanMode`) for the executor's survey: plan mode's
contract is *interactive user approval*, but the executor and the verifier run
as spawned subagents (no user to approve; under `/ship` the whole step is
headless — that is what the `needs_input` handoff is for), plugin agents cannot
set `permissionMode`, and resumability comes from the phase artifacts + gates,
not from plan-mode state. The verifier's read-only discipline is enforced by
its tool allowlist and charter instead (Write is permitted solely for its own
`steps/<skill>/` artifacts); the executor's survey is bounded by the file
map guard and its own charter. A user
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
- **Metrics**: iterations <n>/<cap> · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: <exact command(s), e.g. `/acs:create-pr SHOP-123`, or what unblocks>
```

**The `iterations` element.** A skill that runs no reflection loop omits it
entirely rather than reporting a fraction of a loop it never ran. That is a
property, not a list: it covers the inline apply-work skills (`create-ticket`,
`create-pr`, `merge-pr`), the unhooked utilities (`setup`, `update`, `metrics`,
`usage`, `test`, `release`, `install-hooks`), and the orchestrators that drive
other skills' loops without running one of their own (`ship`, `handoff`). The
fourteen skills that run an execute → verify loop (the twelve authoring
skills, `/acs:code` and `/acs:create-docs`) report it.

`<cap>` is a constant **3** for thirteen of those fourteen. Only `/acs:code`
varies, and it varies by which of its four delivery-path legs ran: 2 on
`code-trivial` and `code-small`, 3 on `code-standard` and `code-complex`. Each
leg's SKILL.md states its own ceiling — there is no table to look it up in and
nothing to derive it from, which is the point of ADR-0095.

**Sanctioned substitutions.** A skill that runs without a ticket drops
`<ticket-id>` from the heading and replaces the **Ticket** line with a
one-line label naming what the run covered — **Scope** for the
configuration and reporting utilities (`setup`, `update`, `metrics`,
`usage`, `install-hooks`), **Run** for the two run-oriented ones (`test`,
`release`), whose subject is an execution rather than a scope. `/acs:handoff`
additionally puts the `continue_with` command in **Next**. No other label
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
  "tokens":   {"input": 0, "output": 0},
  "cost_usd": 0.0,
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
| `verifier_passed` | the verifier's `iter-<n>/verdict.json` for the highest iteration (MAR-527), whose own `passed` is derived from its findings | **`false`** — this key answers "may the next step run", and with no evidence the answer is no |
| `tests` | the last iteration's `iter-<n>-execute*.json` reports (`coverage_target` from `settings.test_coverage_percent`) | the coordinator's value is kept |
| `pr` | `gh pr list --head <branch>` | the coordinator's value is kept, flagged unverified |
| `review.iterations` | the verify artifacts on disk | the coordinator's value is kept |
| `review.guard_denials` | the length of `invocations[-1].guard_events` on `steps/<skill>/state.json` | **absent, not `0`** — a run that never tripped the file-map guard carries no key |

A disagreement is recorded, never silently resolved: `runs[-1].derived_states`
carries `values`, a one-line `provenance` for every key considered (including
the ones it declined to compute, and why), and `overrode` — the
supplied-vs-derived pairs — which is also printed on stderr. `verifier_passed`
is derived only for `code`, the one skill whose verdict `/acs:create-pr` gates
on. **A coordinator cannot open that gate by writing `true`.**

`tokens`/`cost_usd` above are legacy fields: accepted for backward compatibility but
silently ignored since MAR-1 — `finalize_run` measures both itself (see the
Token/cost usage exception noted above) rather than trusting a coordinator-supplied
value. Emitting them is harmless but has no effect.

`post-<skill>.py` finalizes `runs[-1]`, merges `states` (replaces `findings` /
`errors` when present), updates `run.json`, `tickets-index.json`,
`metrics.json`, releases the `.lock`, and performs per-skill extras
(create-pr → ticket `in_review` + prs.created; merge-pr → ticket `done`,
epic auto-done check, partition archived to `archive/<ticket-id>/`).

### Canonical `states` keys per skill

The next skill, a ship.yaml predicate, or a gate brake reads these — keep the
names exact. `acs_lib/derive.py` owns only `DERIVED_KEYS`
(`verifier_passed`, `tests`, `pr`, `review`) and `VERDICT_SKILLS` (`code`);
every other key below is persisted verbatim from the result document:

| Skill | Required `states` keys on success |
|-------|-----------------------------------|
| create-prd | `prd` `{path, files:[...]}`, `pr` `{number, url, branch}` |
| create-architecture | `architecture` `{path, hld:[...], lld:[...]}`, `pr` `{...}` |
| create-project | `scaffold` `{build, lint, tests, coverage_tooling: true/false}`, `pr` `{...}` |
| create-ticket | `ticket_id`, `type`, `needs_design`, `children: [ids]`, `prd_trace` `{feature, divergence}` |
| create-design | `design_path` (the published `design.md` — the docs folder, or the partition when there is no checkout), `decision` (one line) |
| analyze-requirements | `ready_for_planning: true/false`, `api_surface: true/false` (the `api_surface_changed` predicate), `questions_open` (int) |
| create-impl-plan | `plan_path`, `plan_approved: true/false` (written by `plan-approval.py`), `file_map` (object) |
| create-api-contract | `contract_path`, `items` (int), `traced_acs: [...]` |
| create-test-docs | `cases` (int), `e2e_cases` (int), `untraced_acs: [...]` (empty on a completed run) |
| code | `verifier_passed: true/false` (the /create-pr BRAKE), `branch`, `specs_implemented: [...]`, `tests` `{passed, failed, coverage_percent, coverage_target}`, `docs_updated: [paths]`, `review` `{iterations, findings_open}` (plus `guard_denials`, derived, only when the file-map guard denied a write) |
| create-e2e-tests | `suites_written: [...]`, `cases_covered: [...]` |
| create-pr | `pr` `{number, url, branch, base}` (the /merge-pr brake) |
| merge-pr | `merged: true/false`, `merge_strategy`, `readiness` `{ci, approvals, conflicts, protections}` |

On failure, keep whatever is true (e.g. `/code` coverage hard-fail records
`verifier_passed: false`, achieved coverage, and the reason in `stop_reason`).

The exempt non-ticket merge path (`/acs:merge-pr --pr <n>`) has **no** result
document and writes **none** of the merge-pr ticket states above — there is no
partition. It bumps only the repo-level `pr_merged` metric via
`post-merge-pr.py --pr <n>` and touches no ticket index, pipeline, or archive.

### The Build and Test skills at a glance

Six skills were carved out of what `/acs:code` and `/acs:test` used to do
alone, so each produces ONE artifact another step can read, and each is
runnable on its own:

| Skill | Reads | Writes | Downstream use |
|---|---|---|---|
| `analyze-requirements` | the ticket, PRD/requirements/architecture, the codebase | `analysis.md` (front matter `ticket`, `ready_for_planning`, `api_surface`, `stakes_recommendation`, `needs_design_recommendation`) | the `api_surface_changed` predicate; `/acs:create-impl-plan`'s executor plans from the impact map; a not-ready analysis returns `needs_input` |
| `create-impl-plan` | `analysis.md`, `design.md`, the ticket | `plan.md` + the executor file map, plan approval on STANDARD/COMPLEX | `/acs:code`'s input gate; `on_replan` re-runs it when execution finds the plan wrong |
| `create-api-contract` | `plan.md`, `analysis.md`, the architecture set, existing contracts where the repo keeps them (else `docs/api/`) | `api-contract.md` + machine-readable contract files | code implements it; create-test-docs derives contract cases; `/acs:review-code` checks conformance |
| `create-test-docs` | the ticket's ACs, `plan.md` and `api-contract.md` when present | `test-cases.md` (`TC-n`, traced AC, type unit/integration/e2e, steps, expected, target suite) | the executor writes tests from it; `create-e2e-tests` reads its e2e-typed rows |
| `create-e2e-tests` | the e2e-typed rows of `test-cases.md`, `settings.e2e`/`suites.e2e` | e2e suites at the repo's configured location, on the ticket branch | `run-e2e-tests` executes them |
| `run-e2e-tests` | the ticket's suites (from `test-cases.md`, falling back to the plan's Test-plan section) | the run artifact + triage | `on_fail: {relay_to: code}` with the fix-loop cap |

`/acs:code` keeps execute → verify, the escalation triggers, the coverage gate
and the boundary — it lost only the plan phase, and gained `plan.md` as a hard
input. When execution finds the plan wrong it ends `failed` with
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
`skill`, `phase`, `iteration`.

- `phase` is `execute` or `verify` (no skill has a plan phase). A lens spawn's
  verify result carries its lens back as `lens="A|B|C|D|E"`, which is how the
  hook finds that lens's verdict file.
- Subagents receive the `<task>` inside their prompt and must return the
  `<result>` as the final content of their reply — nothing after it.
- `<handoff>` is only for step-coordinator -> /acs:ship returns: compact
  (~1 KB), referencing workspace files rather than inlining detail.
- Subagents never spawn sub-subagents; parallel executors are the
  coordinator's call; the verifier runs after all executors complete.

**Phase results are JSON.** What a step ends with is `result.json`, validated
against `result.schema.json` by `acs result validate` and by the post-hook —
in the language the kernel is written in.

## Subagents

32 agent files named `<skill>-<role>` in `plugins/acs/agents/`, 32 reachable —
every one of them: the files on disk are exactly the roles the naming
convention makes reachable (`acs_lib.skills.unreachable_agents` is empty)
declares under `agents` (ADR-0092), which is what
`tests/acs/test_docs_reflection_topology.py` asserts. There are two roles,
**executor** and **verifier**; no skill has a planner. The twelve
**authoring skills** (`analyze-requirements`, `create-impl-plan`,
`create-api-contract`, `create-test-docs`, `create-e2e-tests`, `create-prd`,
`create-design`, `create-architecture`, `create-project`, `docs-sync`,
`standardize-project`, `create-requirements`) each ship the pair: the executor
surveys on iteration 1, records the survey in its authoring notes and authors
the deliverable from them; the verifier judges the deliverable fresh, against
those notes among its other dimensions (ADR-0092 class D, stage 2). Two of
those twelve are the registry's **internal legs** (`create-project`,
`standardize-project`): the entry-point fold left their pairs untouched,
which is exactly why it is a fold and not a collapse. **`/acs:create-docs`**
was the first to drop its planner (ADR-0094): one executor authors any of the
four doc sets from its templates and one verifier judges it, the set riding
in the task constraints — 2 files for four sets where the four former legs
shipped 12. **`/acs:code`** ships an executor and a verifier: its plan phase
became `/acs:create-impl-plan`, whose executor's survey inherited the former
`code-planner.md` charter. The three **apply-work skills** (`create-ticket`,
`create-pr`, `merge-pr`) run inline and use only their executor, and ship
only that: their six planner/verifier files were orphaned from the day the
skills were inlined (MAR-60) and ADR-0092 deleted them. No agent file is
orphaned.
Conventions:

- Frontmatter: `name`, `description` (when the coordinator spawns it), and
  `model: inherit` — the *actual* model/effort comes from `settings.json`
  (`models.<role>`, `models.overrides.<skill>.<role>`), resolved by
  skill-start into `context.models` and applied by the coordinator at spawn
  time. An unknown model id or unsupported effort fails at spawn — surface the
  error, never silently fall back.
- Verifiers are read-only with ONE exception: each writes its own phase
  artifact under `steps/<skill>/` (the verification report — see
  Phase artifacts above). Only executors mutate
  real targets (the repo for /code and the product-level skills, the
  workspace artifacts — specs, and the ticket-document DRAFTS under
  `steps/<skill>/` — for the rest; a document in the ticket
  docs tree is published by the coordinator from the verified draft, never
  written by a subagent, which the file-map guard enforces), and they record
  what they changed in their execute report. The verifier must judge fresh —
  it never sees the executor's reasoning, only artifacts.
- Verifiers re-run the actual checks (tests, coverage, builds, doc diffs) —
  trust nothing recorded that they can cheaply re-verify.

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
  tickets-index.json  counters.json  metrics.json
  runs-index.json                       # every run: id, workflow, subject, status
  sessions/<checkout-id>/               # ONE directory per checkout, not five files
    pointer.json                        #   the current RUN and STEP
    session.json  cost.jsonl  runtime.json
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
        execute.json  verify.md  verdict.json  lens-<A..E>.md ...
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
- **The docs tree is a control input.** `acs_lib/filemap.py` denies an executor
  write under `<checkout_root>/docs/tickets/` with exit 2 and
  "`<target>` is the ticket docs tree (`docs/tickets/`), a control input only
  the coordinator and the ticket skills write." — the same polarity as the
  guard's own `active-agents/` and `iter-*-filemap.json` records: an executor
  that can rewrite the ticket can rewrite its own scope.

### Concurrency: two mechanisms, both fail closed

**Repo-level guards.** `tickets-index.json`, `metrics.json` and `counters.json`
are read-modify-written by any session in any worktree, so each write holds an
`O_EXCL` guard file beside it (`repo_guard`, a bounded spin: `ACS_GUARD_ATTEMPTS`
× 0.05s, default 200 → 10s, clamped at `GUARD_ATTEMPTS_MAX` since a longer spin
only outlives the 25-second bound Claude Code puts on the pre-hook). **Exhausting
the budget raises `GuardTimeout` and writes nothing.** It used to write anyway, which meant the guard covered every
case except the one it exists for. A refused write is recoverable; a clobbered
one is invisible — and for `counters.json` it means two sessions holding the
same ticket id. In `post-<skill>.py` the refusal exits 1 and says which half
landed: the run, `ticket.json` and `run.json` are already durable, the
index self-heals on the next post hook, and that run's tokens and cost are lost
from `metrics.json` — except after **merge-pr**, the terminal post hook, where
nothing runs afterwards and the message says so instead. Every other entry point
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
| Unit + coverage | /code executors, tests-first (TDD) per the spec's Test plan | Executors iterate against the AFFECTED tests only. The full suite runs **once per iteration, in verify**: the verifier runs it, and reads coverage off that same run vs `test_coverage_percent` — hard fail below target (`docs_only` relaxes only this layer's authoring, never the suite-must-stay-green rule). It records both in `iter-<n>/verdict.json`, and `states.tests` derives from there, so the recorded numbers are the review's independent finding rather than the executor's self-report; `acs_lib.derive_tests` falls back to the execute reports when a verdict carries none |
| E2E (`settings.e2e`: command + optional setup/teardown) | /create-e2e-tests writes the ticket's e2e suites after /code; /code executors run the AFFECTED e2e tests for a spec that declares e2e impact; /create-project scaffolds the harness for greenfield repos with a user-facing surface; /setup detects and offers the config | **`/acs:run-e2e-tests` owns the full suite** (setup → command → teardown always) — `workflows/ship.yaml` runs it after `create-e2e-tests`, which is the first point at which the suite is complete. The /code verifier judges the DIFF instead: a spec declaring e2e impact with no matching e2e test change is blocking. `per_iteration` is accepted and inert — it existed to skip a verifier e2e run that no longer happens |
| CI (scaffolded by /create-project; runs unit + e2e on the PR) | — | /merge-pr readiness reads CI status — report-only, never auto-fixed |

The chain of declarations keeps e2e honest: `test-cases.md` types each `TC-n`
case (unit / integration / e2e) and traces it to an acceptance criterion → the
implementation plan maps the unit and integration cases into executor tasks →
`/acs:create-e2e-tests` writes suites for the e2e-typed cases → the verifier
demands matching test diffs. A repo without `settings.e2e` /
`settings.suites.e2e` skips the layer entirely — `e2e_configured` is false, so
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

1. **Research first.** An executor never asks what the repo, docs,
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
   `/acs:analyze-requirements` is where requirement questions now belong: it asks the
   user through `AskUserQuestion` when one is reachable and records each
   question through `clarify.py`, falling back to `--source assumption`
   otherwise; `/acs:create-ticket` parks anything needing the codebase read for
   it rather than asking up front.
3. **Record everything.** Every answer received — interactively or via a
   /ship relay when re-invoking a step — is recorded with `clarify.py add/answer`
   BEFORE acting on it; coordinators feed the ledger into subagent `<context>`,
   and executors cite the `C-n` ids they relied on (`clarifications_used`).
4. **Assumptions are visible debt.** When no user is available (or the user
   says "you decide"), the decision is recorded as `assumed` with a
   rationale; assumptions surface in the completion report's Findings line
   and the PR body until a user confirms (flips to `answered`) or overrides
   them. A silent default is a verifier finding.

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
  `/acs:docs-sync`'s executor names the HLD files and `lld/flows/` diagrams
  to update, from the diff, in its authoring notes after `/acs:code`
  completes; `docs-sync`'s
  verifier derives the architectural impact from the diff itself (a
  positive, evidenced conclusion — never a default) and blocks before
  `/acs:create-pr` runs when impact exists without matching doc changes.
- **Drift repair (boy-scout)** — commits that bypass the pipeline can still
  desynchronize docs. Both the design executor's and the implementation
  executor's surveys (`create-impl-plan-executor.md`, which inherited the
  former `code-planner.md` charter) compare the touched area's docs against
  current code and schedule stale sections for repair as part of the ticket
  (on TRIVIAL/SMALL this survey is **best-effort** and coordinator-carried
  instead of executor-carried, since no executor is spawned on those lanes —
  MAR-72; its omission there is never a finding); widespread drift triggers a
  recommended
  /create-architecture re-run (the full reconcile, shipped as its own
  delivery ticket + docs PR).

Net effect: after every merge the doc set matches the code — "update the
architecture" is not a separate activity but a blocking dimension of every
change that has architectural impact.

The same induction maintains the **living requirements**
(the repo's requirements set, else `docs/requirements/`, one file per feature
area): per-ticket specs are archived change-deltas, so the CURRENT
behavioral contract accumulates here instead — `/acs:docs-sync`'s executor
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
   slice sized for a single /code executor pass; the spec count is a size
   *signal*, never a release valve.
3. **Sizing today.** The mid-decomposition "stop and recommend a
   split" step this bullet described through the standalone spec-authoring era belonged
   to the deleted spec-authoring planner (ADR 0066 supersedes ADR 0006);
   `create-impl-plan-executor.md`'s survey (which inherited the former
   `code-planner.md` charter when the plan phase moved and ADR-0092 retired
   the planner role) migrated the narrower **Spec-simplicity gate** — when
   a materially simpler decomposition satisfying the same acceptance criteria
   exists, it is surfaced as a question, never a stop — plus (ADR 0069) a
   non-blocking **oversize signal** on the same charter item: when the
   decomposition itself exceeds `create-ticket/SKILL.md`'s sizing rubric's
   `~4-spec`/`~400-line`/`~7-AC` rubric, the implementation executor records
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
FILE` gives the CLI the same seam. The **jira** path stays in prose: it goes
through `acli`, not `gh`.

Four rules keep the two flows honest about what they did:

- **The issue body is a precondition, not an argument.** `tracker sync` posts
  each partition's `tracker-body.md`, and the executor charter is what tells
  the executor to write it. A partition without one is reported under `failed`
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

Setup configures conventions and the CI that enforces them — the ticket
prefix, the `formats.*` strings, and the convention and tests gates — and
nothing else; every other setting keeps its default until someone edits
`.acs/settings.json` by hand.

- **`acs.py setup detect`** — read-only. Which settings exist and **in which
  scope**, the resolved workspace, whether both ignore layers are in place and
  whether a broad rule is swallowing `.acs/settings.json` or `.acs/ci/`, the
  toolchain, plausible test commands, which CI installs are already present,
  and which retired keys (ADR-0102) a settings file still carries.
- **`acs.py setup apply --answers FILE`** — the project settings, both ignore
  layers, the workspace create-and-probe, and the CI copies. An answer equal to
  its built-in default is never written, and is removed when an earlier run
  wrote it (`defaulted` in the result), so the file carries only choices.

**Idempotence is the contract.** `/acs:setup` is re-run whenever a format
changes, and a repo initialised by an older acs is expected to be *repaired* by
a re-run. So every settings write is a read-update-write merge (unknown keys
preserved for forward compatibility, nested objects merged rather than
replaced), every ignore entry is added only when `git check-ignore` says it is
missing — probed **with** its trailing slash, since a directory-only rule does
not match a bare path that does not yet exist — and every CI copy is a refresh.
The result splits into `changed` and `unchanged`, so a re-run is visibly a
no-op rather than silently one; `warnings` is what setup must relay but must
not fix (a `!.acs/` negation is the user's configuration to decide); and
`--dry-run` reports without writing.

## Settings, formats, templates

- Resolution: `settings.local.json` -> project `settings.json` -> user
  `~/.acs/settings.json`, deep-merged per key (defaults in `acs_lib/settings.py`).
  A linked worktree without its own gitignored `settings.local.json` inherits
  the main checkout's.
- Inline formats are validated by every pre-hook (unknown placeholder = exit 2;
  `branch_name` must embed `{ticket_id}`).
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
- `enforcement` (opt-in, /setup Step 2): repo-side CI that holds *every* PR to
  the same conventions, so the pipeline can't be silently bypassed. /setup copies
  `templates/ci/check-conventions.py` -> `<repo>/.acs/ci/` and
  `templates/ci/acs-conventions.yml` -> `<repo>/.github/workflows/`. The checker
  is intentionally **standalone (stdlib only, no `acs_lib` import)** because it
  runs on a CI runner with no acs install — it re-derives the conventions by
  compiling the committed `formats.*` strings to regexes ({ticket_id} ->
  `PREFIX-\d+`, {type} -> `epic|story|task`, {slug} -> lower-kebab, free text ->
  `.+`), reading `ticket_prefix` + `formats` from the committed project
  `settings.json`. It is fail-closed and tested by `tests/test_conventions_check.py`.
  The CI check is necessary-but-not-sufficient (workspace proof lives off-repo),
  so the real gate is a required status check on a protected default branch;
  `exempt_branches`/`exempt_label` are the escape hatch for non-ticket PRs.
  The sanctioned way to LAND such a PR is `/acs:merge-pr --pr <n>` (also `#n` or
  a PR URL): a non-ticket mode that runs the same four readiness dimensions and
  branch/worktree cleanup as the ticket path but resolves no ticket, writes no
  partition/state, and skips tracker sync and archiving — `acs step start --pr`
  validates the PR carries the `exempt_label` (or an `exempt_branches` head) and
  refuses + redirects to `/acs:merge-pr <ticket-id>` when the PR looks
  ticket-backed. acs writes nothing into a consumer's `CLAUDE.md`: that file is
  the repo's own project instructions, and the enforcement above is what keeps
  a hand-made PR from bypassing the pipeline.
  The same checker runs three modes off one config: `--mode pr` (CI: branch,
  commit, pr_title, acs_label, pr_description), `--mode pre-push` (local hook:
  branch + commit subjects of the push range), `--mode commit-msg` (local hook:
  the commit subject as written). Each mode's checks are `MODE_CHECKS[mode]`
  intersected with the `enforcement.checks.*` toggles, so local hooks and CI
  enforce identical, user-configured `formats.*` — laptop and runner never drift.
  Local hooks install via the pre-commit framework (tracked/shared) or raw
  `.git/hooks/*` (per-clone), both `--no-verify`-bypassable. The per-clone
  install is the unhooked, user-invoked skill `/acs:install-hooks` (wrapping the
  committed `.acs/ci/install-hooks.sh`, which a teammate can run without the
  plugin) — the `pre-commit install` equivalent for acs.

## Consumer-repo prerequisites

`git`, `python3` (3.9+, stdlib only), `gh` (PRs; also tracker sync when
`tracker.provider=github`), `pre-commit` (recommended — shared local convention
hooks) and `acli` (only when `tracker.provider=jira`). `xmllint` is no longer
one of them: the XSD and `validate_xml.py` are gone, and what a subagent
returns is checked in-process (see Subagent messaging above), so nothing acs
runs needs an external XML tool. `acs_lib.check_toolchain()` is
the single source of truth for this list (kind = required | recommended |
optional, with per-platform install commands); `/setup` Step 1
(`setup detect`) reports it and names each missing required/recommended tool
with its install hint before configuring anything, so a gap surfaces up front
rather than mid-pipeline.
