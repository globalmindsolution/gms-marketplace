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
| Skills | `plugins/acs/skills/<name>/SKILL.md` | 30 |
| Subagents | `plugins/acs/agents/<skill>-<role>.md` | 40 files, all reachable. Each skill owns only the roles its own work needs, named for that work (`create-prd-surveyor`, `create-impl-plan-plan-reviewer`, `code-implementer`), and each role has a kind in `acs_lib.skills.ROLE_KINDS` — `survey`, `write` or `judge` (ADR-0109). `breakdown-ticket`, `create-pr` and `merge-pr` own none: their coordinators run the steps inline. There is no declaration to keep level with the tree: `acs_lib.skills.skill_agents()` reads the roles from the file names |
| Hooks | `plugins/acs/hooks/hooks.json` + `hooks/scripts/` | dispatcher + 20 pre + 20 post |
| Helper CLIs | `hooks/scripts/{acs,citation_check,clarify,codeowners,front_matter_check,handoff,mermaid_lint,migrate_workspace,new-ticket,plan-approval,pr-conventions,prd_conformance_check,record-external,release_notes,setup_wizard,structure_lint}.py` (the `hooks/scripts/*.py` files with a `__main__` entry point, excluding the dispatcher + 20 pre + 20 post hooks counted in the row above; the `acs_lib/` package, `claude_code_adapter.py`, `markdown_headings.py`, `consistency_findings.py`, the three `release_notes_*` siblings MAR-531 split out and the `acs_cli.py` / `acs_commands.py` / `acs_state_commands.py` siblings split out of `acs.py` are importable libraries with no CLI entry point and are excluded; `skill-start.py`, `pipeline-step.py` and `validate_xml.py` are gone with the surfaces they served — `acs step start`, the run ledger's single writer, and the XML message contract — and `statusline.py`, `subagent-statusline.py` and `cost_sampler.py` went with the status line (ADR 0103), and `metrics_aggregate.py`, `metrics_render.py`, their siblings and `usage_reader.py` with the usage dashboards (ADR 0104); the count is derived from disk by `HelperCliInventoryTest`, so it stays right on its own; this list is the prose that has to be kept level with it) | 16 |
| Workflow files | `plugins/acs/workflows/ship.yaml` | 1 (the default delivery pipeline; a consumer may override it at `<repo>/.acs/workflows/ship.yaml`) |
| JSON Schemas | `plugins/acs/schemas/*.schema.json` | 13 |
| XML schema | `the SubagentStop hook` | 1 |
| Templates | `plugins/acs/templates/*.md` | 8 (5 description templates — `pr-default`, `epic/story/task/bug-default` — plus `design-default` and the two audit-report templates, `audit-design-report` and `audit-security-report`, whose sections the audits' post-hook checks; ADR-0123) |

Skills are invoked namespaced: `/acs:setup`, `/acs:ship`, `/acs:create-ticket`, …
(The requirements docs write `/setup`, `/ship`, … — same skills, plugin-namespaced
by Claude Code.)

## Hook event binding (resolves the open question in docs/requirements/functional/hooks.md)

Claude Code has no "skill completed" hook event, so the pre/post contract maps
onto the plugin hooks API like this:

1. **Pre-hooks — deterministic, enforced.** `hooks.json` registers a
   `PreToolUse` hook matching the `Skill` tool. `dispatch.py pre` extracts the
   skill name from the tool input (handling the `acs:` namespace), no-ops
   (exit 0) for anything that is not one of the twenty hooked skills, and
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
| `SUBJECT_GATES` | the SUBJECT TICKET the invocation names | `create-tech-design` (requirements to design from — any ticket, a prompt, documents or a current run; no ticket flag, ADR-0139), `merge-pr` (a PR reference recorded by a completed step) |

It is consulted **unconditionally**, before the workflow is read,
because a safety brake must not be switchable off by editing `ship.yaml`. A
repo DOCUMENT precondition is not a hook's to check: no setting says where the
PRD or the architecture set lives, so the skill that reads one finds it at
Start. `create-architecture` takes the PRD as its primary input and, without
one, works from the run's subject (a document in its arguments, else the
focus notes plus the codebase) and confirms goals, NFRs and constraints
through the clarification ledger (ADR-0102). A
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
run's artifact in its phase folder, then a legacy `docs/tickets/<ID>/`, then
the partition, then a legacy path
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
| `acs changes snapshot` | a git tree id of the whole working tree, untracked files included (`{ok, tree}`) — what a review records as `reviewed_sha` (see "Commits: only /acs:create-pr") |
| `acs changes diff [--since <tree-or-commit>] [--name-only\|--stat\|--patch] [--run R]` | what this run changed: `<since>` (default: the baseline's `base_sha`) against a fresh snapshot, minus the paths already dirty at the baseline that did not change again; `--name-only` prints `{files: [{path, status}]}` |
| `acs pr plan-commits [--ticket ID] [--run R] [--out FILE]` | the commit groups `/acs:create-pr` previews: `{branch, base, groups: [{id, subject, layer, paths}], left_out, excluded}` |
| `acs pr commit --plan FILE` | execute a (possibly edited) plan: switch to its branch when not on it, then one `git add -- <paths>` + `git commit` per group; never pushes |
| `acs requirements show [--run R]` | the run's requirements (ADR-0128): `{path, sources, acceptance_criteria, features, feature}` — `path` is `<run>/requirements.md` (see "Requirements of a run") |
| `acs requirements add --args "…"` | parse more sources (ticket ids, documents, a prompt) into the run: deduplicated, appended to `subject/sources.json`, `requirements.md` regenerated; a source is never replaced |
| `acs requirements refine --from FILE\|-` | record `/acs:analyze-requirements`' refined acceptance criteria, features and feature into `<run>/requirements-refined.json` and `requirements.md`'s `## Refined`; also patches the ticket, as `ticket save` does, when the run has one. A `needs_design` key is refused with a GateError naming ADR-0139 |
| `acs handoff send --ticket ID [--note TEXT\|--note-file F] [--attach PATH]… [--replace] [--dry-run] [--remote NAME]` | package the ticket's resume set as one commit and push it to `refs/acs/handoff/<ID>`; the sender's state is untouched; `--dry-run` reports the package and the attachments without building or pushing (see "Ticket handoff") |
| `acs handoff receive ID\|--ticket ID [--replace] [--keep-ref] [--remote NAME]` | fetch, `git apply --3way` the work onto a clean tree, restore the run with local paths, raise the counters, delete the remote ref; prints `continue_with` |
| `acs handoff list [--details] [--remote NAME]` | the handoffs waiting under `refs/acs/handoff/` (`git ls-remote`); `--details` adds each one's sender, time and note |
| `acs ticket references (--ticket ID \| --features a,b [--parent ID]) [--fetch] [--write] [--render]` | the documents the standard layout holds for a ticket (its own and its parent epic's records included), or for features not minted yet (`--parent` adds that epic's records) (ADR-0140): `{ok, ticket_id \| features+parent, references, default_branch, web_base, web_base_reason, remote_checked, written}` plus `block` with `--render`, the `## References` markdown; `--fetch` first runs a best-effort `git fetch origin <default>` (`remote_checked: false` when it fails); `--write` (with `--ticket` only) stores `references` on the ticket. Exactly one of `--ticket` and `--features` (see "Tickets") |
| `acs artifacts show [--run R \| --ticket ID]` | where one run's documents resolve — its phase folders, a legacy `docs/tickets/<ID>/`, or the partition — and, for a ticket, its derived status |

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
  `run.in_progress_step` is the first of them, the one a session pause or a
  Stop reminder names.
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
        per-tier models, design source, references, post_hook path; the run's first
        start also writes <run>/baseline.json (ADR-0127)
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
       each carrying slice="<id>", at most settings.parallel.max_agents
       (default 4) per message (see "Fan-out inside a skill")
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
   inline skills (breakdown-ticket, create-pr, merge-pr) run no loop and spawn
   no subagent; create-ticket runs at most two iterations (ADR-0138).
4. Write the result document steps/<skill>/result.json      # acs.py write, never the Write tool
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
a disjoint **slice**, and waits for all of them before the next phase.

**The cap is a setting: `settings.parallel.max_agents`** (default 4, an
integer from 1 to 16; `acs_lib/settings.py`, `schemas/settings.schema.json`;
ADR-0125). It is the most subagents a skill spawns in one message; work
beyond it runs in **waves of that size**, each wave one message, the next only
after the last returned. Every skill reads it from the `settings` its context
JSON carries — no SKILL.md hard-codes a number. A skill with its own SMALLER
structural cap keeps it (`/acs:code-small` 2, `/acs:code-trivial` 1),
and one fan-out is a fixed shape
rather than a wave: `/acs:review-code`'s five lenses are one message whatever
the setting. Three kinds of work fan out:

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

**Parallel writers commit nothing** (ADR-0127): each writes its own disjoint
files into the working tree and lists them in its report, so there is no
`index.lock` to meet. The join is the reports plus the file-map guard;
`/acs:create-pr` commits the result.

**Cost.** Wall time falls wherever work splits; token cost rises with sliced
judges, which re-read shared inputs once per slice, and the per-message cap
bounds it.

#### Jobs: commands beside the agents (ADR-0125)

Subagents stay in the foreground — the coordinator waits on their results,
never on a clock. A long DETERMINISTIC command (a build, a lint, a test
suite) is different: it needs no model, so it runs as a **job**, started in
the same turn as the spawn it runs beside, and collected when its result is
needed:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job start --name <n> [--cwd <dir>] -- <command>
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job wait --name <n> [--name <m> …] [--timeout <s>]
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job status --name <n> [--name <m> …]
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job stop --name <n>
```

- `start` runs the command detached (default cwd: the checkout root) and
  returns at once. A job of the same name still running is refused; a
  finished one is replaced.
- `wait` is ONE blocking call that returns the moment every named job has
  ended, with each job's state, exit code and the tail of its log. It exits
  **0** when all passed, **1** when one failed or was stopped, **3** when the
  timeout (default 540 s, under the Bash tool's ceiling) passed with a job
  still running — call it again. This is not polling: never wrap it, or
  anything else, in a `sleep` loop.
- `status` answers without waiting (`running|passed|failed|stopped|missing`);
  `stop` kills a running job's process group.
- Jobs belong to the run: `<run>/jobs/<name>.json` (the record),
  `<name>.log` (combined output) and `<name>.exit` (the exit code, written
  only after the command ends). Names are lowercase letters, digits, `-`
  and `_`.

A job is safe only over a tree nothing else is writing — read-only agents, or
a command that does not read what the agents write. Where it runs:
`/acs:review-code` starts the gate (`gate-build`, `gate-lint`, `gate-suite`)
beside its lenses and reads it only when nothing blocks;
`/acs:create-impl-plan` starts the repo's existing suite (`suite`) beside
iteration 1's planner, once per run, and its `tests` plan-review slice reads
it.

**Deterministic checks go beside the judge, not after it.** A $0 check a
coordinator runs on a draft (`front_matter_check.py`, `structure_lint.py`,
`prd_conformance_check.py`, a coverage grep) needs no review result, so it
runs as soon as the draft is written, in the same turn as the judge spawn, and
its failures are blocking findings of THAT iteration — never a second failure
after a passing review.

### Phase artifacts (written by the subagents themselves)

Subagents persist their full work products into the partition — the XML result
carries references, never the bodies (docs/requirements/functional/reflection.md: subagents write their states,
findings, error details, and stop reasons into workspace files). Every one of
these files is written through `acs.py write`, never the `Write` tool (see
"State files: `acs.py write`" under Workspace layout):

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
work it performs **inline** (`/acs:breakdown-ticket`, `/acs:create-pr`,
`/acs:merge-pr`, and `/acs:create-ticket`'s materialisation), where no subagent runs and therefore no SubagentStop fires.

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
enforced by its tool allowlist and charter instead (no `Write` tool; its own
`steps/<skill>/` artifacts go through `acs.py write`); a write role is bounded by the
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
property, not a list: it covers the inline apply-work skills (`breakdown-ticket`,
`create-pr`, `merge-pr`), the read-only audits — `audit-design`, whose gap
analysts survey and nothing is written for a judge to judge, and
`audit-security`, whose adjudicators rule once on each auditor's candidate
findings with no writer between them — the unhooked utilities
(`setup`, `update`, `test`, `release`, `set-doc-status`, `handoff`), and the orchestrator that drives other skills'
loops without running one of its own (`ship`). The
twelve skills that run a write → judge loop over their own subagents
report it, with a constant `<cap>` of **3** (`create-ticket`'s is **2**,
ADR-0138). `/acs:code` reports the
iteration of ship.yaml's review-code → code loop it is on, whose ceiling is
that loop's `max_iterations`, the same on every delivery path.

**Sanctioned substitutions.** A skill that runs without a ticket drops
`<ticket-id>` from the heading and replaces the **Ticket** line with a
one-line label naming what the run covered — **Scope** for the
configuration utilities (`setup`, `update`) and for `set-doc-status`, **Run** for the
two run-oriented ones (`test`, `release`), whose subject is an execution
rather than a scope. The ticketless document skills — the audits,
`create-prd` and `create-architecture` (ADR-0127) — put their scope or mode in
the heading's place and keep the **Ticket** label, reading `none — …`. `/acs:handoff receive` additionally puts the `continue_with` command in **Next**. No other label
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

**Six `states` keys are DERIVED, not read (MAR-523, MAR-578, ADR-0137).**
`run_post` computes `verifier_passed`, `tests`, `pr`, `review.iterations`,
`review.guard_denials` and `/acs:docs-sync`'s `implemented` from the artifacts
before persisting the document, and the computed value wins:

| Key | Source | When it cannot be computed |
|---|---|---|
| `verifier_passed` | `/acs:review-code`'s `iter-<n>/verdict.json` for the highest iteration (MAR-527), whose own `passed` is derived from its findings | **`false`** — this key answers "may the next step run", and with no evidence the answer is no |
| `tests` | the review's own suite run, else the last iteration's `iter-<n>/implementer*.json` reports (`coverage_target` from `tests.coverage`; a run started before ADR-0109 has `execute*.json`, read the same way) | the coordinator's value is kept |
| `pr` | `gh pr list --head <branch>` | the coordinator's value is kept, flagged unverified |
| `review.iterations` | `/acs:review-code`'s verdict, lens and adjudication artifacts on disk | the coordinator's value is kept |
| `review.guard_denials` | the length of `invocations[-1].guard_events` on `steps/<skill>/state.json` | **absent, not `0`** — a run that never tripped the file-map guard carries no key |
| `implemented` (`docs-sync` only, `IMPLEMENTED_SKILLS`) | each listed design document's own version front matter, read from the checkout: only a document that reads `status: implemented` is kept; one missing, unversioned or at another status is dropped (ADR-0137) | the listed paths are kept unchecked when there is no checkout root, and the provenance says so |

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
(`verifier_passed`, `tests`, `pr`, `review`, `implemented`) and `VERDICT_SKILLS` (`review-code`);
every other key below is persisted verbatim from the result document:

| Skill | Required `states` keys on success |
|-------|-----------------------------------|
| create-prd | `prd` `{path}`, `files: [...]` (the PRD and roadmap, left uncommitted for `/acs:create-pr`) |
| create-architecture | `architecture` `{path, hld:[...]}`, `files: [...]` (every HLD path written, left uncommitted) |
| create-ticket | `ticket_id`, `type`, `children: [ids]`, `prd_trace` `{feature, divergence}` |
| breakdown-ticket | `ticket_id`, `type` (always `epic` after the run), `converted_from` (`story`/`task` when a split converted the ticket, else `null`), `children: [ids]` (the parent's full list), `minted: [ids]` (this run's), `design_status` (the tech design's status, or `null`) — ADR-0138 |
| create-tech-design | `design_path` (the published `tech-design.md` — the run's Design folder `lld/<feature>/<id>/`, or the partition when there is no checkout), `decision` (one line) |
| create-data-design | `feature: [...]`, `files: [...]` (every path written, repo-relative — left as uncommitted changes for `/acs:create-pr`), `types: [...]` (the owned LLD types written), `gaps` `{undocumented, unimplemented, drifted}`, `entities` (int) |
| create-flows | `feature: [...]`, `files: [...]` (as create-data-design's), `types: [...]`, `gaps` `{undocumented, unimplemented, drifted}`, `flows` (int), `state_machines` (int) |
| create-api-contract | `contract_path` (where the per-run record `api-contract.md` went — `lld/<feature>/<id>/` when shared, the partition when kept local), `feature: [...]`, `files: [...]` (every path written, repo-relative: the living api documents, any `lld` README rows and the shared record), `types: [...]` (`["api-contract"]`, or `[]` when the type is disabled — `outcome: type_disabled`), `interfaces: [...]` (the living `lld/<feature>/api/<interface>.md` files written or bumped), `items` (int), `traced_acs: [...]`, `gaps` `{undocumented, unimplemented, drifted}` — documents only, no machine-readable contract files (ADR-0134) |
| analyze-requirements | `ready_for_planning: true/false`, `questions_open` (int) — no `api_surface` since ADR-0134 (an older state file that carries it still validates; nothing reads it) |
| create-impl-plan | `plan_path`, `plan_approved: true/false` (written by `plan-approval.py`), `file_map` (object) |
| create-test-docs | `cases` (int), `e2e_cases` (int), `untraced_acs: [...]` (empty on a completed run) |
| docs-sync | `files: [...]` (every doc it edited or bumped, left uncommitted), `implemented: [...]` (the living LLD documents it moved `approved → implemented`, derived from their front matter — ADR-0137) |
| code | `branch`, `delivery_path`, `plan_path`, `plan_approved`, `file_map`, `specs_implemented: [...]`, `files: [...]` (the uncommitted paths; `commits` is legacy and optional) (plus `review.guard_denials`, derived, only when the file-map guard denied a write) |
| review-code | `verifier_passed: true/false` (the /create-pr BRAKE, derived from `verdict.json`), `reviewed_sha` (the working-tree snapshot tree the review judged), `review` `{iterations, findings_open}`, `tests` `{passed, failed, coverage_percent, coverage_target}` |
| create-e2e-tests | `suites_written: [...]`, `cases_covered: [...]` |
| create-pr | `pr` `{number, url, branch, base}` (the /merge-pr brake), `branch`, `commits: [...]` (the shas `acs pr commit` made) |
| merge-pr | `merged: true/false`, `merge_strategy`, `readiness` `{ci, approvals, conflicts, protections}` |
| audit-design | `audit` `{scope, report, unimplemented, planned, undocumented, drifted, unversioned, tickets:[...]}` — the counts per gap kind and the tickets minted from them; the post-hook re-counts the gap kinds from `report.md` |
| audit-security | `audit` `{scope, report, critical, high, medium, low, advisory, refuted, scanners:[...], skipped:[...]}` — the confirmed findings per adjudicated severity, the `needs-context` ones (`advisory`) and the refuted ones, the scanners the dependency auditors ran and the slices not run; the post-hook re-counts every count from `report.md` (ADR-0123) |

**`files`, wherever a skill writes repo files** (ADR-0127): every repo-relative
path the step wrote and left uncommitted — `analyze-requirements`,
`create-impl-plan`, `docs-sync` and the rest record it beside the keys above.
It is what `acs pr plan-commits` groups; a changed path no step recorded is
left out of every group and listed.

On failure, keep whatever is true (e.g. a `/acs:review-code` coverage
hard-fail records `verifier_passed: false`, achieved coverage, and the reason
in `stop_reason`).

The exempt non-ticket merge path (`/acs:merge-pr --pr <n>`) has **no** result
document and writes **none** of the merge-pr ticket states above — there is no
partition. It has no post step either: it touches no ticket index, pipeline,
or archive, and there is nothing repo-level to record (ADR 0104).

### The Development skills at a glance

Five skills were carved out of what `/acs:code` and `/acs:test` used to do
alone (a sixth, `create-api-contract`, was one of them until ADR-0134 made it a
Design skill), so each produces ONE artifact another step can read, and each is
runnable on its own:

| Skill | Reads | Writes | Downstream use |
|---|---|---|---|
| `analyze-requirements` | the run's requirements (a ticket, documents, a prompt), PRD/requirements/architecture, the codebase, the ledger, the feature's living analysis and its own previously published analysis — the folder, or a single `analysis.md` from before ADR-0133 (the survey starts from them) | three stages — survey the impact, clarify with the user (one grouped ask; confirmed criteria, features and the feature recorded via `acs.py requirements refine`, which also patches a ticket), store — ending in an `analysis/` folder (ADR-0133: `README.md` with front matter `ticket` or `feature` and `ready_for_planning`, plus one file per bounded context; an interface change is named in its Next as work for `/acs:create-api-contract`, ADR-0134) published to the feature's living analysis `<prd_dir>/features/<f>/analysis/` when run on its own (Discovery), or to `<development_dir>/<f>/<id>/analysis/` as a Development step | `/acs:create-impl-plan`'s planner plans from the impact map, and `create-test-docs` reads it; the Design skills — `create-api-contract` among them — read the feature's living analysis; the next analysis starts from it; a not-ready analysis returns `needs_input` |
| `create-impl-plan` | the analysis (`analysis/README.md` first, then the context files it needs — ADR-0133), `tech-design.md` (a legacy `design.md` when that is all there is; its status stated in the report, a warning when not approved — ADR-0135) and the approved API contract (`api-contract.md` and the feature's `lld/<feature>/api/` files, ADR-0134) when present, else the run's requirements | `plan.md` + the executor file map, plan approval on STANDARD/COMPLEX; when the repo keeps machine-readable contract files (OpenAPI, JSON Schema, proto, AsyncAPI), the plan items that create or update them from the contract | `/acs:code` implements it; `on_replan` re-runs it when execution finds the plan wrong |
| `create-test-docs` | the requirements' ACs (`AC-n`, refined when analysed), `plan.md`, and the API contract (`api-contract.md` through `artifacts show`, plus the living `lld/<feature>/api/`) when present | `test-cases.md` (`TC-n`, traced AC, type unit/integration/e2e, steps, expected, target suite) | the implementer writes tests from it; `create-e2e-tests` reads its e2e-typed rows |
| `create-e2e-tests` | the e2e-typed rows of `test-cases.md`, `settings.tests.e2e` | e2e suites at the repo's configured location, left uncommitted | `run-e2e-tests` executes them |
| `run-e2e-tests` | the ticket's suites (from `test-cases.md`, falling back to the plan's Test-plan section) | the run artifact + triage | `on_fail: {relay_to: code}` with the fix-loop cap |

`/acs:code` keeps the implementers, the escalation triggers and the boundary;
its plan phase is `/acs:create-impl-plan` and its review is
`/acs:review-code`. It reads `plan.md` when there is one and otherwise works
from the run's requirements. When execution finds the plan wrong it ends `failed` with
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

40 agent files named `<skill>-<role>` in `plugins/acs/agents/`, 40 reachable —
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
| `create-architecture` | `architect` (write) · `gap-analyst` (survey — one per survey area, spawned beside the survey only when `hld/` already holds documents; ADR-0122) · `reviewer` (judge) |
| `create-tech-design` | `designer` (write) · `reviewer` (judge — adds flows ↔ api ↔ data consistency and snapshot freshness; ADR-0135) |
| `create-data-design` | `designer` (write — a survey pass, then ONE write pass over both documents, which must agree) · `gap-analyst` (survey — one per survey area, spawned beside the survey only when the feature's `data/` already holds documents; ADR-0126) · `reviewer` (judge — three slices) |
| `create-flows` | `designer` (write — a survey pass, then parallel write slices, one per flow group plus `write-states` and `write-components`, and an `integration` pass only when a slice reports a seam) · `gap-analyst` (survey — as create-data-design's, over `flows/` and `components/`) · `reviewer` (judge — three slices; ADR-0126) |
| `create-api-contract` | `contract-author` (write — sliced per interface, with an `integration` pass only when a slice reports a seam) · `gap-analyst` (survey — one per existing interface document, spawned in the same message as the survey only when the feature's `api/` already holds documents; ADR-0134) · `contract-reviewer` (judge) |
| `create-impl-plan` | `planner` (write) · `plan-reviewer` (judge) |
| `create-test-docs` | `test-designer` (write) · `trace-reviewer` (judge) |
| `code` (and its four legs) | `implementer` (write), one per file-map partition |
| `review-code` | `lens` · `adjudicator` (judge) |
| `create-e2e-tests` | `test-writer` (write) · `suite-runner` (judge) |
| `docs-sync` | `doc-updater` (write — one per doc area: `requirements`, `architecture`, `lld`, `adr`, `general`) · `gap-analyst` (survey — one per run feature, in the same message as the doc-updaters in iteration 1; ADR-0137) · `drift-reviewer` (judge — three slices over seven dimensions) |
| `audit-design` | `gap-analyst` (survey — one per top-level code area); read-only, no writer and no judge (ADR-0122) |
| `audit-security` | `auditor` (survey — one per category: `code` per code area, `secrets-config`, `dependencies`, `threat-model`) · `adjudicator` (judge — one per candidate finding, prompted to refute it); read-only, no writer (ADR-0123) |
| `create-ticket` | `epic-author` · `story-author` · `task-author` · `bug-author` (write — ONE per run, for the type the coordinator chose; each writes only the draft `steps/create-ticket/iter-<n>/draft.json` and `draft.md` through `acs.py write`, reading the shared `references/authoring-rules.md`, and never mints a ticket or touches the tracker) · `reviewer` (judge — concrete, testable acceptance criteria, PRD trace and `features`, the type's completeness, sizing honesty, no invented facts); at most two iterations, then the coordinator confirms and materialises inline from `references/materialize.md` (ADR-0138) |
| `breakdown-ticket`, `create-pr`, `merge-pr` | none — the coordinator runs the steps inline from its SKILL.md and `skills/<skill>/references/` (create-pr's `publish.md`, merge-pr's `merge.md`) |

The surveyor runs on iteration 1 only and freezes its notes; the author
writes from them. The lifecycle hooks do not track `review-code`'s lenses and
adjudicators (`acs_lib.lifecycle.UNTRACKED_ROLES`): they fan out one per lens
and one per finding, and the coordinator persists what they return itself.
`UNTRACKED_ROLES` is keyed by role name, so `audit-security`'s adjudicators —
one per candidate finding — are untracked the same way, and each writes its own
`iter-<n>/adjudication-<id>.json`; its auditors are tracked.

Conventions:

- Frontmatter: `name` (`<skill>-<role>`) and `description` (what the role does
  for `/acs:<skill>`, ending "Spawned by the /acs:<skill> coordinator with a
  JSON task; not for direct invocation."). Survey and judge roles carry
  `tools: Read, Glob, Grep, Bash` (no `Write`: they write only state, through
  `acs.py write`, ADR-0136); write roles carry
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
  artifacts above), through `acs.py write` to the absolute path under the
  task's `partition`. Only write roles mutate real targets (the repo for /code
  and the product-level skills, the workspace artifacts — specs, and the
  document DRAFTS under `steps/<skill>/` — for the rest; a run's document in
  its phase folder is published by the coordinator from the reviewed draft,
  never written by a subagent), and
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
write, and keyed by `run_id` with an optional `ticket_id`: the loop runs on any
subject (ADR-0128). The coordinator performs ONE action at a time and reports it:

| Verb | Reads / does | Moves the loop to |
|---|---|---|
| `next` | read-only: prints the one action (`plan`, `survey`, `synthesize`, `clarify`, `draft`, `review`, `publish`, `completed`, `blocked`, `failed`) with every path it involves | — |
| `plan --areas a,b` | declares the survey lanes once: the analyst's `requirements` lane + one `impact-analyst` lane per area (`repo` when none; `requirements`, `synthesis`, `survey`, `repo` are reserved → `area-<name>`) | `survey` |
| `record-survey` | every lane's `<result>` snapshot, notes and JSON report; joins the notes into `iter-1/authoring.md` | `synthesize` (always: ≥ 2 lanes) |
| `record-synthesis` | the synthesis snapshot and notes; re-joins with the synthesis last | `clarify` |
| `record-clarify [--blocking-open]` | the joined notes and the ledger's open count | `draft` (with `--blocking-open`, the not-ready arm: published, then `blocked` needs_input) |
| `record-draft` | the draft snapshot, the draft folder `iter-<n>/analysis/` (ADR-0133), `iter-<n>/analyst.json` (and `iter-<n>/authoring.md` on n ≥ 2); records the draft folder's digest (`draft_sha256`, over every file's sha256) and runs the folder checks (`acs_lib.analysis_folder`: `front_matter_check` and the structure checks on README and on every context file, see "The analysis folder" below) — beside the review, not after it (ADR-0125) — listing their findings as the `review` action's `draft_checks` | `review` |
| `record-review` | the three judge slices' snapshots and reports; joins them into `iter-<n>/impact-reviewer.md`; parses every `<finding severity dimension file>`, and folds in the draft's check findings (slice `draft-checks`) | `publish` on a pass; else `failed`/`stalled`, `failed`/`cap` (iteration 3), or `draft` n+1 |
| `publish` | refuses unless the last review passed and the draft folder is the reviewed files — its digest unchanged (whose checks ran clean at `record-draft`); copies every draft file byte-for-byte into `analysis_publish.resolve_target`'s folder — the feature's living analysis `<prd_dir>/features/<feature>/analysis/` for a standalone (Discovery) run, `<development_dir>/<feature>/<id>/analysis/` for a Development run (ADR-0128, ADR-0133) — and removes a context file the new analysis no longer has, only inside that `analysis/` folder — refusing, with a message naming `acs.py requirements refine` and the feature ask, a run with no recorded feature; exits 2 naming `acs.py docs decide` while `docs where` reports an answer owed (the share choice for a Development run, the folder for either phase), and with run documents kept local publishes to `steps/analyze-requirements/local/analysis/` instead — `publication` records the path, `local`, `share_scope` and the report phrase `destination`, and lists no `files` for `/acs:create-pr` (ADR-0132); records `path` (the README), `dir`, the folder digest `sha256`, `file_shas` (each file's sha256), `removed` (the context files it deleted) and `superseded` (a single pre-ADR-0133 `analysis.md` left beside the folder, which every reader now passes over); never stages, commits or pushes (ADR-0127) | (unchanged) |
| `record-publication` | re-derives the publication from the working tree: every file in `file_shas` still the reviewed bytes, and no `.md` file in the folder the review never judged | `completed` |

Rules the code holds, each with a transition test in
`tests/acs/test_analysis_loop.py`:

- **Derived, never asserted.** No verb takes a verdict. An iteration passes
  iff every judge slice returned `status="completed"` with zero
  `severity="blocking"` findings and the draft's deterministic checks found
  nothing; a slice with `status="failed"` contributes a `review-failed`
  blocking finding.
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

### The analysis folder (`acs_lib/analysis_folder.py`, ADR-0133)

An analysis is always a folder, never one long file — even a single-context
one. The draft is `steps/analyze-requirements/iter-<n>/analysis/`; when
iteration n fails, the controller seeds `iter-<n+1>/analysis/` with a copy of
iteration n's files, so the next draft pass revises in place (and may delete a
context file). It publishes to:

| Run | Folder |
|---|---|
| Discovery | `<prd_dir>/features/<f>/analysis/` (the feature's living analysis) |
| Development | `<development_dir>/<f>/<key>/analysis/` |
| kept local (ADR-0132) | `<run>/steps/analyze-requirements/local/analysis/` |

The folder holds `README.md` and at least one context file. Every other name
matches `^[a-z0-9]+(-[a-z0-9]+)*\.md$`; `index.md`, any other name, a
subfolder or a non-`.md` file is refused. `record-draft` runs the checks below;
a finding fails the iteration like a judge's blocking finding (ADR-0125).

**`README.md`** — the entry, rendered when the folder is opened on the forge.
Front matter is the old `analysis.md` spec: `ticket` (must match the run's) or
`feature`, and `ready_for_planning` (a boolean; an `api_surface` key left by
an analysis published before ADR-0134, or a `needs_design_recommendation` left
by one published before ADR-0139, is ignored, never refused), plus `status`, `version`, `tickets` (ADR-0122) on a Discovery
analysis. Title `# Analysis — <ticket-id or feature>: <subject>` (not
checked). Required `##` headings, in this order, each non-empty:

1. `## Scope and summary`
2. `## Contexts`
3. `## Refined acceptance criteria`
4. `## Cross-cutting risks and decisions`
5. `## Questions and assumptions`
6. `## Verdict`

`## Contexts` holds a Markdown table — suggested columns
`| Context | File | Purpose |`, only the links are checked — and each row
links one context file by a bare relative link, `[order-checkout.md](order-checkout.md)` — no `/`, no `..`,
no anchor. Findings: `broken-link` (a link that resolves to no file in the
folder), `unlisted-context` (a context file the table does not link),
`no-contexts` (a table that lists none).

Each finding names `file: analysis/<name>` with the text `line N: [rule] msg`;
besides `front_matter_check` / `structure_lint`'s own rules, the folder rules are
`missing-folder`, `missing-readme`, `index-file`, `bad-name`, `unexpected-entry`,
`unreadable`, `no-contexts-table`, `unlinked-row`, `bad-link`, `broken-link`,
`no-contexts`, `unlisted-context`, `no-context-files`, `context-mismatch` and
`feature-mismatch`. The controller's `draft` action names the folder (`draft`),
its `readme`, the `previous_draft` already copied in on n ≥ 2, and the `shape`
it must have; the `review` action lists `draft_files`, README first.

**A context file `<slug>.md`** — one bounded context, named in plain words.
Front matter `context: <slug>`, equal to the file stem; on a Discovery run with
no ticket — exactly when README carries the version keys — also `feature`,
`status`, `version`, `tickets`. A `feature`, wherever present beside README's,
must equal it. Title `# <Context name in plain
words>` (not checked). Required `##` headings, in this order, each non-empty
(`_None._` counts as content):

1. `## Impact map` — a table whose first column is a repo-relative path (`file:line` allowed)
2. `## Rules and edge cases`
3. `## Risks`
4. `## Open questions`
5. `## API notes`

**Publish** copies every reviewed file byte-for-byte into the target folder,
deletes a context file the new analysis no longer has — only inside that
`analysis/` folder, never beside it — and records each file with its sha256;
`record-publication` verifies every one. **Readers** open `README.md` first and
then only the context files they need. A single `analysis.md` — published
before ADR-0133, or a legacy `docs/tickets/<ID>/analysis.md` — is still read
wherever no `analysis/` folder exists; nothing converts it in place.

## Workspace layout (normative example)

Durable state is split by AUDIENCE. The documents a human reads or reviews live
in the consumer repo and are committed with the change — a run's own documents
only when the repo shares them (ADR-0132, see "Shared or kept local" below);
the run ledger — every
fact a hook or a walk reads — and the ticket itself stay in the gitignored
workspace (and the tracker). A run's documents live **one folder per phase**,
keyed by the run's feature (ADR-0128):

| Phase | Folder | Documents |
|---|---|---|
| Discovery | `<prd_dir>/features/<feature>/` | the feature's living analysis, the `analysis/` folder (ADR-0133; ADR-0122 front matter + `feature` on every file) |
| Design | `<architecture_dir>/lld/<feature>/<ticket-id or run-id>/` | `tech-design.md` (ADR-0135; a legacy `design.md` is still read), `api-contract.md` (the per-run record linking the interface files it wrote, ADR-0134); the living `lld/<feature>/{api,data,flows,components}/` stays edited in place (ADR-0126, ADR-0134) |
| Development | `<development_dir>/<feature>/<ticket-id or run-id>/` | a Development run's `analysis/` folder (ADR-0133), `plan.md`, `test-cases.md` |

`acs_lib.requirements` resolves the three roots deterministically:
`prd_dir(root)` (the PRD the way `/acs:create-prd` finds it — a `CLAUDE.md` or
docs-index mention of a `prd.md`, else a Glob for `prd.md` — default
`docs/product`), `architecture_dir(root)` (the set holding
`hld/tech-stack.md`, default `docs/architecture`) and `development_dir(root)`
(an existing `docs/development/`, default the same); `feature_dir(ctx,
feature)` is `<prd_dir>/features/<slug>/`. The feature is the ticket's first
feature, or the one `requirements refine` recorded; a ticketless run without
one is asked for it in `/acs:analyze-requirements`' grouped ask. **Nothing
writes `docs/tickets/<ID>/`**: no `ticket.md` is rendered, and a folder written
before ADR-0128 is only read, as a fallback.

Who commits the documents (ADR 0127, amending ADR 0090): **only
`/acs:create-pr`**. Every skill that publishes a document — `tech-design.md`,
the `analysis/` folder, `plan.md`, `test-cases.md`, the LLD under
`<architecture_dir>/lld/<feature>/`, the PRD, the HLD — writes it into the working
tree on whatever branch is checked out and lists it in its result's
`states.files`; `/acs:create-pr` commits the run's documents first, and each
other doc set as its own.

### Commits: only `/acs:create-pr` (ADR-0127)

No skill creates or switches a branch, stages, commits or pushes — except
`/acs:create-pr`, plus `/acs:release`'s own `release/*` PR (ADR-0052) and
`/acs:merge-pr`'s merge and post-merge cleanup — and `/acs:handoff`'s snapshot
commit, pushed to the hidden ref `refs/acs/handoff/<ID>`, never to a branch
(ADR-0131, see "Ticket handoff"). The changeset is the working
tree, so reading it takes three pieces in `acs_lib/changes.py`:

- **Baseline** — `runs/<run-id>/baseline.json`, written once by the run's first
  `acs step start` and never overwritten (ticketless runs too): `{base_sha,
  branch, dirty: [paths dirty or untracked at that moment, with their blob ids],
  first_step, adopts_dirty, recorded_at}`. A file the user was already editing is
  not the run's — unless the run's FIRST step reads existing work (`review-code`,
  `docs-sync`, `create-pr`, `run-e2e-tests`: `adopts_dirty`), where the hand-written
  changes already in the tree are exactly its subject and stay in the changeset.
- **Snapshot** — `acs changes snapshot`: a tree id of the full working tree,
  untracked non-ignored files included, built through a throwaway
  `GIT_INDEX_FILE` so the real index and the tree are untouched. The verdict's
  `reviewed_sha` holds one; `/acs:code` asks `acs changes diff --since
  <reviewed_sha>` what changed after the review.
  An embedded repository the user never committed — a Claude Code worktree at
  `.claude/worktrees/<name>/`, a stray `git init` — is never part of it: untracked
  embedded repos are excluded from the `add`, and any gitlink the base tree does not
  hold is dropped from the temporary index (`changes.drop_new_gitlinks`, also run by
  `handoff receive` after `git apply --cached`). A submodule already in `HEAD` stays.
- **Changeset** — `acs changes diff`: `<since>` → a fresh snapshot, the
  baseline's dirty paths excluded unless they changed again. It replaces every
  `git diff <default>...HEAD` / `git log <branch>` read; a scope check snapshots
  at step start and diffs `--since` that tree.

`/acs:create-pr` then runs `acs pr plan-commits` (`acs_lib/commit_plan.py`):
deterministic groups from the run's recorded results (`states.files`, the
analysis publication, the implementer reports' `files_changed` per slice or
partition, the plan's file map, docs-sync's files, the e2e suites) intersected
with the changeset — the run's documents, the design docs, per slice its tests then
its code, docs-sync's updates, the e2e suites. Tests and code split on the
repo's test-path conventions (a `test`/`tests`/`__tests__`/`spec` segment, or
`test_*`/`*_test.*`/`*.spec.*`/`*.test.*`); subjects follow
`conventions.COMMIT_SUBJECT`. Changed but unrecorded paths are `left_out`,
baseline-dirty ones `excluded`; both are listed in the preview the user
confirms (and may edit) before `acs pr commit --plan <file>` commits each group
by pathspec — never `git add -A`. An analysis folder (ADR-0133) is one
documents group, every file of it together: the publication's `files`, plus
its `removed` context files, whose deletions go in the same commit. A run document kept local (ADR-0132) lives in
the workspace, never in the working tree, so it is in no group and never
`left_out` — no special case, and a test holds it. `/acs:create-pr` takes a ticket id or a
prompt; with no argument it continues this checkout's current run. A run whose
steps recorded nothing — a prompt given with no current run — is planned in
`uncommitted` mode: every uncommitted change against HEAD, grouped by layer
(documents by doc set — the PRD, `hld/`, each `lld/<feature>/`, the ADRs, the
run's documents — then tests, then code), placing each file by the paths other runs
recorded in `states.files`. The `verifier_passed` brake applies only when the
run has a code step, and a commit subject names a ticket only when there is one.

**Limitation.** Two tickets in flight in one checkout share one working tree and
so one changeset; use a separate worktree per concurrent ticket.

```
<checkout>/<prd_dir>/features/<feature>/analysis/             # Discovery: the living analysis (README.md + <context>.md, ADR-0133)
<checkout>/<architecture_dir>/lld/<feature>/<id>/              # Design: tech-design.md  api-contract.md (per-run records)
<checkout>/<architecture_dir>/lld/<feature>/{api,data,flows,components}/  # Design: the living LLD (api/<interface>.md, ADR-0134)
<checkout>/<development_dir>/<feature>/<id>/                   # Development: analysis/  plan.md  test-cases.md
<checkout>/docs/tickets/<ticket-id>/                           # LEGACY, read-only fallback (doc_layout.LEGACY_TICKETS_PATH)

<workspace>/<repo-id>/                  # repo-id from git remote: owner-name
  tickets-index.json  counters.json
  runs-index.json                       # every run: id, workflow, subject (+ sources), status
  sessions/<checkout-id>/               # ONE directory per checkout, not five files
    pointer.json                        #   the current RUN and STEP
  <ticket-id>/                          # THE TICKET (workspace + tracker are its only homes)
    ticket.json
    clarifications.json                 #   a ticket run's clarification ledger
  archive/<ticket-id>/                  # moved here by post-merge-pr
  runs/<run-id>/                        # THE PARTITION -- a run, not a ticket
    run.json                            #   the run machine (§4.3); subject + subject.sources
    subject/
      sources.json                      #   [{kind, ref, sha256, copy}] (ADR-0128)
      <n>-<basename>                    #   a document copied in from outside the repo
    requirements.md                     #   regenerated from the sources; never hand-edited
    requirements-refined.json           #   `acs requirements refine`: the ## Refined section
    clarifications.json                 #   a TICKETLESS run's ledger only
    lock.json  lock-events.jsonl  agents/<agent_id>.json  handoff-context.md
    baseline.json                       #   the run's starting point: base_sha, branch, dirty paths (ADR-0127)
    steps/<skill>/
      state.json                        #   the step machine (§4.4)
      result.json                       #   the post-hook's input
      plan.md  api-contract.md  ...     #   CURRENT artifacts
      iter-<n>/                         #   the AUDIT TRAIL, one dir per iteration
        authoring.md  <role>.json  <role>.md  <role>-message.xml
        authoring-<id>.md  <role>-<id>.json|.md  <role>-<id>-message.xml   # sliced
        verdict.json  lens-<A..E>.md ...
```

### How state is written: `acs.py write` (ADR-0136)

**The root does not move.** `repo.default_state_root(cwd)` derives
`<main-checkout>/.acs/state-machine` from `git rev-parse --is-bare-repository`
and `--git-common-dir`, and refuses a bare repository and a submodule with a
`GateError` (ADR-0086, ADR-0102). Every linked worktree, `.claude/worktrees/<name>/`
included, resolves the same folder at the main checkout's root — never one of
its own. Two Claude Code rules decide whether a worktree session can write it.
Worktree isolation refuses the `Write`/`Edit`/`NotebookEdit` tools on any
main-checkout path, and any Bash call whose working directory is the main
checkout or that points git at it; a Bash call run from the worktree that
writes with Python is neither, so `acs.py write` is not stopped. The Bash
sandbox, when on, lets Bash write only the working directory, `$TMPDIR`, added
directories and `sandbox.filesystem.allowWrite` paths, and settings path rules
anchor at the session's working directory; so `/acs:setup` offers an
`allowWrite` entry naming the folder's **absolute** path (see "Bootstrap"
below).

**State files: `acs.py write`** (`acs_write_commands.py`). No skill or agent
writes a state file with the `Write` or `Edit` tool. The one form is

```
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write <path> [--append] [--run R] <<'ACS_EOF'
…content…
ACS_EOF
```

with the delimiter quoted so the content is taken verbatim. stdin is the
content, byte for byte (a terminal on stdin is refused). An absolute `<path>`
must resolve, symlinks followed, inside the workspace root; a relative one is
resolved against the run directory — `--run R`, else this checkout's current
run (`acs.py context` reports it as `run_id`/`run_dir`; neither → exit 2). A
coordinator hands its agents the absolute `partition`, and agents write
absolute paths (`<partition>/<path>`): a subagent in its own worktree has no
current run. `/acs:review-code`'s lenses and adjudicators, whose tasks carry no
`partition` and which run in the coordinator's checkout, use the run-relative
form. Escaping the
root (`..`, a symlink) and the machine-owned ledgers with verbs of their own —
`run.json`, `steps/<skill>/state.json`, `lock.json`, `runs-index.json`,
`tickets-index.json`, `sessions/`, `active-agents/`, any `filemap.json` — are
refused with exit 2 and nothing written. Parent directories are created; the
write is a temporary file in the same directory and `os.replace`, `--append`
included. stdout: `{"ok": true, "path", "bytes", "appended", "total_bytes"}`.
Repo files are still written with `Write`/`Edit`, by write roles only, inside
the session's worktree; the file-map guard still judges those.

### Ticket handoff: the resume set over a hidden ref (ADR-0131)

`/acs:handoff` moves one ticket in mid-flight from one member to another, on
another machine. The workspace never crosses; a **package** does.
`acs_lib/team_handoff.py` (send, list) and `acs_lib/team_handoff_receive.py`
behind `acs.py handoff send|receive|list` (`acs_handoff_commands.py`) do the
work, reusing `acs_lib.changes`' `snapshot`, `_run_git`, `head_sha` and
`current_branch`; the skill asks one grouped question and reports.

**The ref.** One commit at `refs/acs/handoff/<ID>` on `origin`. A ref outside
`refs/heads/` and `refs/tags/` is not fetched by a default refspec, shows no
branch and cannot back a pull request — but anyone with read access can fetch
it by name. The commit's parent is the run's `baseline.base_sha` (HEAD when
there is none); it is built
through a temporary `GIT_INDEX_FILE` (`hash-object -w`, `update-index
--cacheinfo`, `write-tree`, `commit-tree`), so the sender's HEAD, index,
branches and working tree are never touched. It is the one commit an acs skill
makes outside `/acs:create-pr` (and `/acs:release`, `/acs:merge-pr`): never on
a branch, never merged (amending ADR-0127). Transport is `git push` /
`git fetch`, as `/acs:create-pr` pushes; `gh` is not involved.

**The package tree** is the **resume set** — what a resume reads, nothing a
resume does not:

```
work/                     # changes.snapshot: tracked edits, deletions, untracked non-ignored files
acs/ticket/               # ticket.json  clarifications.json
acs/run/                  # run.json  requirements.md  requirements-refined.json  baseline.json
                          # handoff-context.md  subject/sources.json
  steps/<skill>/          #   the files at the step's root: state.json  result.json  <current artifacts>
    iter-<n>/verdict.json #   the verdicts only, never the rest of the audit trail
attachments/              # outside-repo subject copies, ONLY those passed with --attach
note.md                   # done / in flight / next / decisions
manifest.json             # format, ticket, sender, time, base, branch, withheld attachments, counters_next
trees/<id>                # every tree id the state cites (baseline.tree, a verdict's reviewed_sha)
```

Absolute paths in the resume set travel as the tokens `${ACS_RUN_DIR}`,
`${ACS_REPO_DIR}` and `${ACS_CHECKOUT}` (`team_handoff.TOKENS`) and are
rewritten to the receiver's paths on the way in. The manifest is checked
against `schemas/handoff-manifest.schema.json` and its `format` before
anything is written.

**Left out** (`team_handoff.EXCLUDED_RULES`), because a resume never reads it
or it is machine-local: `steps/*/iter-*/` except `verdict.json`, a step's
sub-directories, `jobs/`, `agents/`, `lock.json`, `lock-events.jsonl`, logs,
`sessions/`, and every outside-repo attachment not passed with `--attach`.

**Send** refuses an archived ticket, a run that is not about a ticket, an
`--attach` that is not one of the run's attachments, and an existing ref unless
`--replace`; every push carries a lease (`--force-with-lease`), so a ref that
changed since it was read is not overwritten. `--dry-run` reports the package
and the attachments and builds nothing. After a successful push the sender's
state is untouched — work, run and lock stay where they were, and no workspace
file, index or local ref is written; a handoff is a copy.

**Receive**, refusing before anything is written: fetches the ref and
validates the manifest; refuses a local run or ticket partition with the same
id unless `--replace`, which moves them under
`<workspace>/<repo-id>/handoff-backups/<ID>-<stamp>/`; refuses a dirty working
tree; dry-runs `git diff --binary <base> <work> | git apply --3way` in a
temporary index, so a receiver whose HEAD moved on still applies and a conflict
is reported with its paths while the checkout is untouched. Then it applies for
real (the changes land unstaged), restores `acs/` with this machine's paths,
upserts `tickets-index.json` and `runs-index.json`, raises `counters.next` to
at least the sender's, and points this checkout's
`sessions/<checkout-id>/pointer.json` at the run. It keeps the commit under
the local ref `refs/acs/received/<ID>` (the cited trees stay reachable) and
deletes the remote ref unless `--keep-ref`. It prints `continue_with` — the
interrupted or in-progress step's skill, else the run's cursor, else
`/acs:ship <ID>`. **List** reads `git ls-remote <remote> 'refs/acs/handoff/*'`;
`--details` fetches each for its sender, time and note. Every verb takes
`--remote NAME` (default `origin`).

**Pause is not handoff.** The internal **session pause** is unchanged and keeps
its names: a coordinator under context pressure flushes and runs `handoff.py`
(finalize the in-flight step `interrupted`, `stop_reason: context_pressure`,
release the lock, print `continue_with`), and the `PreCompact` hook writes
`handoff-context.md`. It stays on one checkout and touches no remote. The
`/acs:handoff` skill never calls `handoff.py`, and `handoff.py` never pushes.

### Requirements of a run (`acs_lib/requirements.py`, ADR-0128)

Skills receive **requirements**; a ticket id, documents and a prompt are only
the containers they arrive in, and one invocation may mix them
(`/acs:analyze-requirements SHOP-12 ~/Downloads/spec.pdf "also bulk export"`).
No skill requires a ticket.

- **Parsing.** `parse_sources(text, ctx)` splits the argument text with
  `shlex` (whitespace on an unbalanced quote): a `<PREFIX>-<n>` token is a
  ticket, a token naming an existing FILE — repo-relative, absolute or
  `~`-expanded — is a document (`{path, abs, sha256, inside_repo}`), and the
  rest is joined, in order, into ONE prompt (a text with neither stays the
  prompt verbatim). `primary_subject` keeps today's single subject
  (ticket > document > prompt) for run ids, resume-by-ticket and every reader
  of `run.json.subject`, and stores the whole list as `subject.sources` when
  there is more than one. `gates.subject_from_payload` and `acs step start
  --args` both delegate here. A ticket id with no partition is refused, naming
  `/acs:create-ticket`.
- **Materialising.** `materialise(rdir, ctx, sources)` — idempotent, called
  by the Skill pre-hook that creates or adopts the run AND by `acs step
  start`, so a hookless host gets it — writes `<run>/subject/sources.json`
  (`[{kind, ref, sha256, copy, added_at}]`), copies every document from
  outside the repo to `<run>/subject/<n>-<basename>` (nothing is added to the
  repo for it), and regenerates `<run>/requirements.md`: a front block (run
  id, `generated_at`, sources), then `## Ticket <ID>` (title, description,
  acceptance criteria numbered `AC-1…` in ticket order, features),
  `## Prompt` (verbatim), `## Documents` (markdown and text
  inlined under `### <ref>`; any other type cited by its run copy for the
  model to Read) and `## Refined`. The file is GENERATED — nothing edits it by
  hand.
- **Adding.** `add_sources` (`acs requirements add --args "…"`) appends a
  later invocation's new sources, deduplicated by ticket id, digest or prompt
  text, and regenerates; a repo document edited since keeps one entry with its
  new digest. A source is never replaced silently.
- **Refining.** `refine(rdir, ctx, data)` (`acs requirements refine`) stores
  `/acs:analyze-requirements`' refined `acceptance_criteria`,
  `features`, `feature` and, when it must be explicit, `phase` in
  `<run>/requirements-refined.json`, re-renders `## Refined`, and — only when
  the run has a ticket — patches the ticket as `ticket save` does. A
  `needs_design` key is refused with a `GateError` naming ADR-0139: a run's
  requirements carry no design flag, and a refined file written before it that
  still holds the key is read as if it did not.
- **Reading.** `summary(rdir, ctx)` is the `requirements` block of the
  step-start context and of `acs requirements show`: `{path, sources,
  acceptance_criteria, features, feature, phase, feature_analysis,
  refined}`, for every run, ticket or not. Skills read acceptance criteria
  from it, never from `ticket.json`.
- **The tech design is found, not required** (ADR-0139). Beside
  `requirements`, the step-start context carries `design: {exists, dir,
  source}` for every run, ticket or not, from `gates.design_source(ctx, tdir,
  ticket, rdir)`: the ticket's (or a ticketless run's) own `tech-design.md` —
  a legacy `design.md` still read, the lookup `acs.py artifacts show design`
  uses — with `source: own`, else its parent epic's with `source: parent`, else
  `exists: false` and `source: null`. `dir` is the folder holding the design
  file that was found (normally `<architecture_dir>/lld/<feature>/<id>/`), never
  the ticket partition, and `null` when none exists. The planning, code, test-docs and review
  skills read the design when `exists`, and proceed without one otherwise —
  no advisory. Nothing records whether a design is *required*.
- **The run's references are found, not searched for** (ADR-0140). Beside
  `design`, the step-start context carries `references`, from
  `requirements.run_references(ctx, rdir)`: for each ticket source
  `doc_links.references_for_ticket(ctx, ticket)`, for a ticketless run with
  refined features `doc_links.references_for_features(ctx, features)`, else
  `[]` — local only, never a fetch. `materialise` renders the same list as
  `requirements.md`'s `## References` section (title, kind, path, url), from
  the same function, so the context and the file cannot drift. Every hooked
  skill that runs on a ticket reads the documents relevant to its step from
  `context.references` before working and never searches the repo for them
  (one shared Start line, read through `skill_contract`).
  `run_feature` is the refined `feature`, else the refined `features`' first,
  else the first feature the run's ticket traces to; `run_phase` is
  `development` for a run with a ticket or one `/acs:ship` drives, else
  `discovery`, unless `refine` set it.

### Run documents (`acs_lib/doc_layout.py`, `acs_lib/run_docs.py`)

A run's documents are resolved by RUN, not by ticket — its feature, its phase
and its key (the ticket id, else the run id):

| Document | Written to |
|---|---|
| `analysis.md` (the `analysis/` folder, ADR-0133) | Discovery: `<prd_dir>/features/<f>/analysis/` (the feature's living analysis); Development: `<development_dir>/<f>/<key>/analysis/` |
| `plan.md`, `test-cases.md` | `<development_dir>/<f>/<key>/` |
| `tech-design.md` (legacy `design.md`), `api-contract.md` | `<architecture_dir>/lld/<f>/<key>/` |

`doc_layout` computes the roots and folders — `prd_dir`, `architecture_dir`,
`development_dir`, `feature_dir`, `feature_analysis_path`, `design_run_dir`,
`development_run_dir`, `document_target` — as pure path computations that
create nothing. `run_docs.run_layout` places every document of one run: the
file a reader opens is the first that exists of the phase-folder target, the
LEGACY `docs/tickets/<ID>/<name>` (`doc_layout.LEGACY_TICKETS_PATH`, read,
never written) and the ticket's partition; the write target is the phase
folder, `None` while the run has no feature (until `requirements refine` or
analyze-requirements' grouped ask names one). `acs artifacts show [--run R |
--ticket ID]` prints that view — the feature, phase, key, the three roots,
each document's existing file and write target, the legacy folder when there
is one, and a ticket's derived status.

`tech-design.md` (ADR-0135) is read with a fallback: wherever it is absent, a
`design.md` at the same place — a design published before the rename — is the
file a reader opens, and the run artifact keeps its key `design` (`acs.py
artifacts show design`, with `tech-design` an alias), resolving the run's draft
in `steps/create-tech-design/`, else an older run's `steps/create-design/`.
Only `tech-design.md` is ever written.

The analysis is a folder (ADR-0133), so its keys keep their name and change
what they hold: `artifacts["analysis.md"]` is the folder's `README.md` (else a
single `analysis.md` published before the folder — beside it, in
`docs/tickets/<ID>/` or in the partition); `analysis_files` lists every file
of the folder as absolute paths, README first (`[that file]` for a single
legacy file, `[]` when there is none); `analysis_dir` is the folder the
analysis was read from (`null` for a single legacy file); `paths["analysis.md"]`
is the write target `…/analysis/README.md` and `analysis_target_dir` its
folder. The feature's living analysis gets the same pair, `feature_analysis`
(its README) and `feature_analysis_files`. `acs docs where --doc analysis.md`
resolves the same folder: its `path`, `abs_path`, `shared_path` and
`local_path` name the folder, and `entry_path` / `abs_entry_path` its
`README.md`. The file-map guard denies an executor the living analysis folder
(and the single file it replaced) as it did `analysis.md`.

### Shared or kept local; asked before a folder is created (`acs_lib/doc_share.py`, ADR-0132)

Two answers decide where a run's documents land, each asked once and saved,
never inferred:

- **Share** — `docs.share_run_documents` (`true` | `false`; absent = not
  decided) covers the five per-run documents: a Development analysis (the `analysis/` folder),
  `plan.md`, `test-cases.md`, `tech-design.md`, `api-contract.md`. Shared, each is
  published to its phase folder (the table above). Local, it is kept at
  `<run>/steps/<skill>/local/<name>` — the analysis at
  `steps/analyze-requirements/local/analysis/` — (`doc_share.LOCAL_STEPS` names the step;
  `local/` keeps it apart from the step's working draft) and nothing of it
  reaches the repo. The living documents — PRD and roadmap, HLD, LLD, a
  feature's Discovery analysis — are always shared (`living:prd`,
  `living:architecture`).
- **Location** — `doc_layout.resolve_dir(root, kind)` returns `{path,
  source}` for each kind (`prd`, `architecture`, `development`): `setting`
  (a `docs.<kind>_dir`), `discovered` (a PRD or `hld/tech-stack.md` found, or
  the default folder already present) or `default` (acs's built-in fallback,
  a folder that does not exist yet). No writer creates a `default` folder
  without the user's answer.

Two CLI verbs carry the questions and the answers; the skills ask and record,
the code decides nothing on its own:

| Verb | Prints / does |
|---|---|
| `acs.py docs where --doc <name> [--run R]` | `<name>` is a per-run document or `living:prd` / `living:architecture`. Read-only: `{ok, doc, kind, path, share, share_scope, location_source, needs, proposed_path, …}` — `path` repo-relative when shared, run-relative when local, `null` while `needs` is non-empty; `share` is `true`, `false` or `null` (a living document is always `true`); `needs` holds `share` while undecided and `location` while the folder's source is `default` and the document would be shared |
| `acs.py docs decide [--share yes\|no --scope user\|team] [--location KIND=PATH]… [--doc NAME] [--run R]` (`acs_docs_commands.py`) | merges the answer into the scope's file — `user`: the main checkout's `.acs/settings.local.json`, added to `.git/info/exclude` when nothing ignores it yet (`ignored_via`); `team`: the checkout's `.acs/settings.json`, where every repeatable `--location` (KIND `prd`, `architecture`, `development`) lands as `docs.<kind>_dir` — creating the file when absent and touching no other key (`setup_wizard.merge_json_file`; an unreadable file is refused, nothing written); prints `{ok, written: [{file, scope, keys, changed}], warnings}` plus the new `where` of `--doc`, else `documents` — every document's `where`; `warnings` names a more specific settings file that still overrides a share answer |

**An undecided write is refused, not guessed.** Every code path that writes
a run document into the repo (`analysis publish` first among them) calls
`doc_share.require_decided` and exits 2 naming `acs.py docs decide` and each
question owed. A local decision redirects the write into the run folder and
the step's `publication` records that target. `run_docs` / `acs artifacts
show` report `paths[name]` by the decision — the local path, the phase
folder, or `null` plus `needs` — while `artifacts[name]` reads the existing
file wherever it is: phase folder, run folder, legacy `docs/tickets/<ID>/`.
`doc_share.describe_choice` gives the phrase a completion report names a
destination with ("kept local (team default)", "shared to …"). A headless
skill run with no saved answer writes locally for that run and saves
nothing. The file-map guard is unchanged: shared paths are guarded as before,
and run-folder writes were already allowed.

### Tickets (`acs_lib/artifacts.py`)

A ticket is not a document (ADR-0128): it lives in its workspace partition
(`<workspace>/<repo-id>/<ticket-id>/ticket.json`, beside its clarification
ledger) and in the tracker. Nothing renders a `ticket.md`.

- **`status` is DERIVED, never stored.** `derive_status(tdir, ticket=None)`
  computes it from the ledger — `done` when the partition is archived,
  `merge-pr` completed, or (for an epic) every child is done; `in_review` when
  `create-pr` completed (the delivery-ticket skills that once opened their own
  PR are gone, ADR-0127); `in_progress` when any step other than
  `create-ticket` has a non-`skipped` status (or any child is not open);
  `open` otherwise. `load_ticket()` puts it back in the returned dict, so
  callers are unchanged.
- **`load_ticket` / `save_ticket` are the seam.** `load_ticket(tdir)` reads
  `ticket.json`, else a legacy `docs/tickets/<ID>/ticket.md` (ADR-0090), else
  follows `ticket.json.moved`; a corrupt file warns on stderr and reads as
  absent. `save_ticket(tdir, ticket)` writes `ticket.json`.
  `acs_lib.state.load_ticket`/`save_ticket` delegate here with unchanged
  signatures. A legacy `ticket.md` is parsed from the END of its body (the
  last `## Clarifications`, the last `## Acceptance criteria` before it, the
  first `## Description` before that), so a description holding its own `## `
  headings survives.
- **Four types, and the fields a bug adds** (ADR-0138). `TICKET_TYPES` is
  `epic`, `story`, `task` and `bug` — the same enum in `ticket.schema.json`,
  `tickets-index.schema.json` and `new-ticket.py --type`, with one
  description template each (`templates/<type>-default.md`,
  `conventions.TICKET_TEMPLATES`) and one GitHub Project `Type` option each
  (`TYPE_OPTIONS`: `Epic`, `Story`, `Task`, `Bug`; a Project with no `Bug`
  option gets the usual "option missing" finding). A bug may carry five
  optional strings, `acs_lib.BUG_FIELDS` — `severity` (`BUG_SEVERITIES`:
  `critical`, `high`, `medium`, `low`; separate from `priority`),
  `reproduction`, `expected`, `actual` and `environment` — which
  `/acs:create-ticket`'s bug author proposes and `new-ticket.py --severity …
  --reproduction …` or `acs.py ticket save` writes. Both validate them, and
  both refuse a bug field on a ticket that is not a bug (exit 2); an older
  `ticket.json` without them still validates. `ticket.md`'s front matter
  orders them `… type, priority, severity, parent, … due_date, reproduction,
  expected, actual, environment, created_at, updated_at`. A bug runs like a
  story: only an `epic` is refused by `/acs:code`'s and
  `/acs:analyze-requirements`' gates, and its branch is `bug/<ID>-<slug>`.
- **No design flag** (ADR-0139). A ticket carries no `needs_design`: it left
  both ticket schemas (`required` and `properties`), `new_ticket_doc`, the
  index entry and `_FRONT_MATTER_ORDER`, and `new-ticket.py --needs-design`
  exits 2. `additionalProperties` stays `true`, so an older `ticket.json` or
  index entry that still carries the key validates and the key is ignored.
  Whether a change gets a tech design is the user's call; whether one exists
  is `context.design` (see "Requirements of a run").
- **References** (ADR-0140). A ticket may carry `references`, an optional
  array placed after `features` in `_FRONT_MATTER_ORDER` (`ticket.schema.json`:
  objects with `kind` and `path` required, `additionalProperties: true`), which
  `tickets.new_ticket_doc` and `acs.py ticket save` accept. Each entry is
  `{kind, path, title, status, version, published, url}`, derived by
  `acs_lib/doc_links.py` from the STANDARD LAYOUT — never chosen — and ordered
  by kind, then path: `prd` (`<prd_dir>/prd.md`, `path` carrying the `#anchor`
  of the heading that names each feature, GitHub's anchor algorithm with
  `-1`, `-2` … for duplicates), `analysis` (the feature's living analysis,
  `README.md` first), `hld` (`hld/overview.md` and the views whose text names
  the feature), `lld` (the living `lld/<f>/{api,data,flows,components}/**`, no
  sidecars), `design` (`lld/<f>/<id>/tech-design.md` and `api-contract.md`, for
  the ticket and its parent epic) and `development` (`<development_dir>/<f>/<id>/`'s
  `analysis/**`, `plan.md`, `test-cases.md`). A ticket with no `features`
  falls back to an id glob (`lld/*/<id>/`, `<development_dir>/*/<id>/`, the
  parent's records) and `prd.md`. `status` and `version` come from ADR-0122's
  front matter when present; `title` is the first H1, else the file name.
  `url` is `<web_base>/blob/<default>/<path>` (`/-/blob/` on gitlab hosts,
  `/src/` on bitbucket hosts; `web_base` knows `github.com`, `*.ghe.com` and
  any host with a `github`, `gitlab` or `bitbucket` label) only when the
  document is **published** — on `origin/<default>`, checked with
  `changes.blobs` — and `null` otherwise or with no web remote
  (`web_base_reason: "no-web-remote"`). Stored references are a snapshot for
  the tracker; readers derive the list again (`context.references`), so a
  ticket that never stored any still gets one. The description templates
  carry a `## References` heading over an empty `<!-- acs:references -->` …
  `<!-- /acs:references -->` pair before `## Notes`; `doc_links.render_block`
  fills it (a published entry `- [<title>](<url>): <kind>, vN status`, a
  published one with no web remote ``- `<path>`: <kind>, vN status``, a
  pending one ``- `<path>`: <kind>, pending: not on `<default>` yet``, none
  `_No documents for this ticket's features yet._`) and `apply_block`
  replaces only the text between the markers — inserting them under an
  existing `## References`, else appending the section before the trailing
  `acs-ticket:` line — idempotently.
- **A child inherits its parent's `features`.** `new-ticket.py --parent <epic>`
  copies the parent's `features` onto the child unless `--features` is given
  (`--features ""` traces it to none), and reports `features_inherited`. It
  still refuses a parent that is not an epic: `/acs:breakdown-ticket`
  converts a story or task it splits into an epic first — `acs.py ticket
  save` with `{"type": "epic"}`, same id — then mints
  its children (ADR-0138).
- **`acs.py artifacts migrate` is retired** (ADR-0128): tickets are no longer
  stored in the docs tree, so it reports and writes nothing.
- **The run's documents are a control input.** `acs_lib/filemap.py` denies a
  writing agent's write under the legacy `<checkout_root>/docs/tickets/` ("the
  ticket docs tree (`docs/tickets/`), a control input only the coordinator and
  the ticket skills write") and under the run's own Development and Design
  folders ("this run's documents (`<folder>/`), a control input only the
  coordinator and the document skills write") with exit 2 — the same polarity
  as the guard's own `active-agents/` and `iter-*-filemap.json` records: a
  writer that can rewrite the plan it is checked against can rewrite its own
  scope.

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
holds the ticket lock releases it first: a skill that did not start, a session pause
(`handoff.py`) that did not pause, or a SessionEnd net that did not release would otherwise
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
steps.create-e2e-tests = {status: "completed", outcome: "no_e2e_owed",
                          summary: "CLI-only change; no browser flow to drive"}
```

This is strictly more than the `skipped` status it replaces. `skipped`
recorded that a workflow predicate was false, which never distinguished *the
plan says nothing is owed* from *nobody asked* — and it cost the same as this
does, which is nothing.

**Silence is not permission to skip.** A plan that does not mention an
artifact leaves the step to do its work. The alternative — treating absence as
`false` — would let an old plan silently disable a step.

The three steps that can owe nothing, and what each consults:

| Step | Reads | Outcomes |
|---|---|---|
| `create-test-docs` | `owes.test_cases` | `cases_written` · `no_cases_owed` |
| `create-e2e-tests` | `owes.e2e` | `tests_written` · `no_e2e_owed` |
| `run-e2e-tests` | the repo's harness | `passed` · `no_harness` · `nothing_to_run` |

A plan written before ADR-0134 may still carry `owes.api_contract`: it is
accepted and ignored (`plan_contract.OWES_KEYS` is `test_cases` and `e2e`).
`/acs:create-api-contract` is a Design skill now — run before the plan, not a
step of the run — so nothing settles it from the plan.

A failure is **not** an outcome. A step that could not do its work records
`status: failed` with an error — the distinction is what keeps "nothing was
owed" from being confused with "something went wrong".

Ticket flags still steer the skills that read them (`docs_only` drops
tests-first and the coverage hard fail in `/acs:code`), but they are inputs to
a skill, never predicates in a workflow. A ticket carries no design flag
(ADR-0139): `/acs:create-tech-design` runs when the user asks.

## Testing layers — unit always, e2e by configuration, CI at the gate

Tests belong to the same changeset as the change (like docs), and *executing*
unit suites is verification, which `/acs:review-code`'s final gate owns — so there is
deliberately no skill that "writes the unit tests" as a separate step. What the
test steps add is the layer the code loop cannot cover from inside itself:
`/acs:create-test-docs` writes the traced `TC-n` case set (before `/acs:code`, so
the cases exist before the code does), `/acs:create-e2e-tests` turns the e2e-typed
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

Clarification is governed by one ledger and four rules. The ledger is
`clarifications.json` (schema shipped; append-only via
`hooks/scripts/clarify.py` — add / answer / list), and where it lives depends
on the run, not on the step (ADR-0128): a **ticket run** keeps the ticket
partition's `<workspace>/<repo-id>/<ticket-id>/clarifications.json`, shared by
every run of that ticket; a **ticketless run** keeps its own
`runs/<run-id>/clarifications.json`, resolved from `--run` or this checkout's
pointer (`--ticket` is optional). Every Q&A of the ticket or run
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
   /create-ticket, design trade-offs at /create-tech-design, requirement
   clarification (impact, assumptions, refined acceptance criteria) at
   /analyze-requirements, execution-level behavior at /code — batched, not dribbled.
   `/acs:analyze-requirements` is where requirement questions now belong: its
   survey pass ends with `## Questions for the user` (open questions,
   conventional defaults to confirm, refined criteria — nothing about
   design, ADR-0139), and between that survey and its draft pass the
   coordinator asks every one the ledger does not answer in ONE grouped
   `AskUserQuestion` (at most one follow-up round), records each through
   `clarify.py`, and records confirmed criteria and the
   feature with `acs.py requirements refine` (which patches the ticket when
   there is one). Only when no user is reachable does a default fall
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
  the SAME branch/PR: /create-tech-design conforms or lists required doc changes;
  `/acs:docs-sync`'s doc-updater names the HLD files and `lld/flows/` diagrams
  to update, from the diff, in its authoring notes after `/acs:code`
  completes, and its `lld` area brings the run's features'
  `lld/<feature>/` documents in line with the code from its gap analysts'
  notes (ADR-0137); `docs-sync`'s
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
  /create-architecture re-run (the full reconcile, left as uncommitted
  documents for `/acs:create-pr`).

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

### Design versions (ADR-0122, ADR-0130)

Every HLD and LLD document — and, since ADR-0130, the PRD's `prd.md` and
`roadmap.md` and each feature's living analysis — opens with a version
front-matter block that says where the document stands
([ADR-0122](../../../docs/architecture/adr/0122-design-versions-and-gap-detection.md),
[ADR-0130](../../../docs/architecture/adr/0130-prd-versions-and-set-doc-status.md)):

```yaml
---
status: approved        # proposed | approved | implemented | deprecated
version: 3              # an integer >= 1, bumped on every change to the document
tickets: ["SHOP-12"]    # the tickets that changed it, oldest first
feature: wishlist       # LLD documents (under lld/) only: the PRD feature slug
status_by: Ada Lovelace <ada@example.com>   # who made the last status move
status_at: 2026-10-05T09:14:00Z             # when
status_reason: approved in design review    # why, when one was given
---
```

The three `status_*` keys are written only by `design status --set` and sit
after the ADR-0122 keys. A status move never changes `version`; a move given
no `--reason` drops an older `status_reason`, and a `design bump` that re-opens
an approved or implemented document drops all three, since they described the
status it left.

The block is **derived, never asserted**: it is written only through
`acs.py design` (`acs_design_commands.py` over `acs_lib.design_docs`), never by
hand-editing it, and every verb prints one JSON object:

| Verb | Does |
|---|---|
| `design check <doc>...` | status, version and the problems per document; exits 0 whatever it finds (`ok` says whether every document is clean) — a missing or invalid block is a problem, not an error; a path that is not a file exits 2 |
| `design init --status S [--ticket ID] [--feature F] <doc>...` | the first block, `version: 1`; a document that already has one is left alone (`already_versioned`) |
| `design bump [--ticket ID] <doc>...` | a change: `version + 1`, the ticket appended, and the document re-opened as `proposed`; a `deprecated` document is refused |
| `design status --set S [--ticket ID] [--by NAME] [--reason TEXT] <doc>...` | a legal transition (`acs_lib.design_docs.TRANSITIONS`): `proposed → approved \| deprecated`; `approved → proposed \| implemented \| deprecated`; `implemented → proposed \| deprecated`; `deprecated` is final. Records `status_by` (`--by`, default `git config user.name <user.email>`, else `unknown`), `status_at` (ISO-8601 UTC, one instant for the whole call) and `status_reason` (`--reason`). **All or nothing** (`design_docs.set_status_many`): every document is validated — it exists, its block is valid, the transition is legal — before any is written, and the refusal names each refused document and why; a document already at the target is left untouched and reported `unchanged`, so a no-op never rewrites who moved it, when or why (ADR-0130) |
| `design list [--phase discovery\|design] [--feature F] [--root DIR]` | the versioned documents (`design_docs.list_documents`), read-only, exits 0 whatever it finds: `{ok, groups: [{phase, key, label, feature?, docs: [{path, status, version, problems, allowed}]}]}`, Discovery then Design. Discovery — `<prd_dir>/{prd,roadmap}.md` (group `PRD`) and each feature's living analysis (`feature <f> analysis`) — one group holding every file of `<prd_dir>/features/<f>/analysis/`, `README.md` first, each with its own status (a single `analysis.md` from before ADR-0133 still lists as itself); Design — `<architecture_dir>/hld/*.md` (`HLD`) and `lld/<f>/{api,data,flows,components}/**` (`LLD <f>`), and from a run's design-record folder `lld/<f>/<id>/` its `tech-design.md` only, in the feature's group and labelled with its key `<id>` (ADR-0135) — never that folder's other files, nor a legacy `design.md`, which has no block; a README only when it carries a status. Paths are repo-relative; `allowed` is the legal moves other than the current status, empty when the document has `problems`. The folders come from `acs_lib.doc_layout.prd_dir` / `architecture_dir`, the grouping from `acs_lib.doc_sets` — the same `doc_set` / `doc_order` `/acs:create-pr`'s commit plan uses. `/acs:set-doc-status` is its reader |

A refused write verb exits 2 and writes nothing for the document it refused;
`design status` over several documents writes none of them when any is refused.
`/acs:create-architecture`'s architect inits a new HLD file `implemented`
when it documents the code as built and `proposed` when it designs ahead of it,
and bumps a file it changes; its reviewer runs `design check` on every in-scope
file. `/acs:create-prd`'s coordinator inits a new `prd.md` or `roadmap.md`
`proposed`, bumps a changed one and runs `design check` on both in its $0
floor; its author's byte-for-byte rule and its reviewer exempt the leading
block, and `/acs:code`'s implementer bumps either when it reconciles a factual
claim in it. `/acs:create-tech-design` inits a new
`tech-design.md` `proposed` and bumps a revised one (ADR-0135). Approval is recorded with `/acs:set-doc-status` — an unhooked,
inline Utility skill that reads `design list`, asks one grouped question for
the documents and one for the target, and runs a single `design status --set`;
it commits nothing, and the docs PR `/acs:create-pr` opens carries the
approval for review (ADR-0130).
`acs_lib.design_docs` assigns the move to `implemented` to `/acs:docs-sync`,
and docs-sync runs it (ADR-0137). Its `lld` doc area owns
`<architecture_dir>/lld/<feature>/{api,data,flows,components}/**` for the run's
features (`context.requirements.features`, else the ticket's `features`; none
→ the area has no work); `architecture` keeps the HLD and the flat
`lld/flows/`, and a run's record folder `lld/<feature>/<key>/` is never edited.
One `docs-sync-gap-analyst` per feature, beside the doc-updaters in iteration
1, classifies every element of every living document `matches`,
`unimplemented`, `undocumented` or `drifted` with evidence, records the
document's `status`/`version` from `design check`, and marks it
`implemented-candidate` when every element matches; its notes,
`iter-1/gaps-<feature>.md`, are joined into `iter-1/gaps.md`. The `lld`
doc-updater updates and bumps a `proposed` (or unversioned) document; drift
in an `approved` or `implemented` one is a question in the one grouped ask —
update the document (bumped, so back to `proposed` for re-approval) or keep it
and send the code back as a blocking finding — recorded headless as a
blocking finding and `needs_input`, never decided; a `deprecated` one is left
alone. After the review passes the coordinator moves every candidate in one
`design status --set implemented --by acs --reason "<run-id>: the code
matches" <doc>...` call, and the result lists them in `states.implemented`
(every document it bumped or edited stays in `states.files`). A document with
an element still unimplemented stays `approved`, so a design delivered across
tickets reaches `implemented` with the last of them. The drift reviewer's
seventh dimension, `lld-currency`, in its `placement` slice, checks those
updates, bumps, answers and moves. A `design status --set implemented` by
hand is still legal. The gap
analysts (`create-architecture-gap-analyst` beside that skill's survey,
`docs-sync-gap-analyst` per run feature, and `/acs:audit-design`'s over the
whole set) read the status: an element designed
but not built is *planned* in a `proposed` or `approved` document and a
regression in an `implemented` one.

**Audit reports follow a template** (ADR-0123). Both Audit-phase skills —
`/acs:audit-design` and `/acs:audit-security` — run without a ticket (`acs step
start` opens or resumes a run over the invocation for a skill in
`acs_lib.AUDIT_SKILLS`, and the post-hook concludes it) and write
`steps/<skill>/iter-1/report.md` from `templates/<skill>-report.md`, or the
repo's `.acs/templates/<skill>-report.md` when it has one. The template is the
contract: its `## ` sections must appear in the report in the template's order,
and a section marked `<!-- acs:count <key> -->` is counted — one `### ` entry per
gap or finding. `run_post` checks a completed audit's report with
`acs_lib.audit_report` before writing anything, refuses one that breaks the
template (exit 1, the breaches on stderr), and writes the counts into
`states.audit` over whatever the result document claimed, recording any
disagreement — derived, never asserted.

## Size control: tickets, specs, PRs

The PR is the unit of review, and **the ticket is the PR boundary** — every
spec of a ticket lands on one branch in one PR. Size is therefore controlled
at two levers, with an escalation between them:

1. **Ticket sizing (controls PR size).** `/create-ticket`'s coordinator applies a
   PR-size rubric to the type decision: a story/task should yield one
   reviewable PR — rule of thumb ~≤400 changed lines, one concern, ≤~7
   acceptance criteria, grounded in the codebase survey. Above the bar →
   epic with children cut at PR-sized, independently shippable seams, which
   `/acs:breakdown-ticket <id>` proposes and mints (ADR-0138).
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
   `failed` status and a `/acs:breakdown-ticket <id>` next step instead
   of continuing silently.

The numbers are deliberate rules of thumb for the authors' judgment, not
hard limits enforced by hooks — splitting at a bad seam (e.g. a child that
cannot build alone) is worse than a slightly large PR; feature flags are the
sanctioned way to keep children shippable when a slice alone would break.

## Forge metadata: three commands, two failure policies

`gh` is acs's only transport to GitHub, and everything acs writes through it
beyond the PR or issue itself — labels, assignee, milestone, reviewers, Project
membership and fields, and an issue's `## References` block — goes through
`acs_lib.forge` (MAR-525), reached as three commands:

| Command | Performs | Policy |
|---|---|---|
| `acs.py pr metadata fill --pr N` | create-pr step 6a: assignee, the ticket-type label alongside `ACS`, CODEOWNERS reviewers minus the author, the Project item, Status, and Priority / Story Points / Parent | **non-critical throughout** — the PR already exists, so every failure is one `info` finding carrying the command, and the next sub-step still runs |
| `acs.py tracker sync --ticket … ` | create-ticket step 5's batch (and `/acs:breakdown-ticket`'s, through the same `references/tracker-sync.md`): issue creation, labels, assignee, milestone, Project membership, `Type`/`Status`, and the same Group-B fields | **critical per ticket, soft per batch** — a failed `gh issue create` is an `error` finding naming the ticket and carrying `gh_failure_hint`, `replayable: false`; the batch continues and that ticket keeps `external` unset for a retry |
| `acs.py tracker refresh (--ticket ID \| --pending) [--dry-run]` | ADR-0140: one fetch of the default branch, then per ticket recompute its references, store them when they changed, and — on the `github` tracker, for a ticket with `external.key` — `gh issue view <key> --json body`, `doc_links.apply_block`, and `gh issue edit <key> --body-file <tmp>` only when the body changed; a `local` ticket or one with no issue is `skipped`. `--pending` covers every open ticket with `external.key` whose stored references hold an unpublished entry (`/acs:merge-pr` runs it after a merge); `--dry-run` reads the issue and stores or edits nothing. stdout `{ok, dry_run, tickets: [{ticket_id, references, pending, stored, changed, edited, key \| skipped}], findings, calls, remote_checked, default_branch}` | **non-critical** (ADR-0088) — a failed `gh issue view` or `gh issue edit` is one `info` finding carrying the command and `gh_failure_hint`; the next ticket still runs and the command never stops a skill |

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
  `references/materialize.md` is what tells its coordinator to write it
  (`/acs:breakdown-ticket` writes each child's, ADR-0140). Before `gh issue
  create`, the sync applies the ticket's `## References` block to the body
  (`doc_links.apply_block`, fresh references after one fetch, stored on the
  ticket too), so every synced issue carries real links; a block that cannot
  be written is an `info` finding and the issue is still created. The issue
  URL `gh issue create` prints is kept as `external.url`
  (`record-external.py --url`).
- **The failure class is declared once.** `forge.GH_FLOW_CRITICALITY` maps
  each gh-driven command to its ADR-0088 class — `pr metadata fill`
  non-critical, `tracker sync` critical per ticket and soft per batch,
  `tracker refresh` non-critical — and the skills' failure-policy prose and
  this table quote it. A partition without one is reported under `failed`
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

Setup is optional (ADR-0105): no skill needs it first. It also ignores `.claude/worktrees/`
(where Claude Code puts the worktrees it creates) beside acs's own ignore entries, and
offers acs's Claude Code permission rules (`acs_lib.claude_permissions.RULES`: acs's own
`hooks/scripts/*.py` and read-only git) for `.claude/settings.json` (team) or the main
checkout's `.claude/settings.local.json` (me), or skips them — a shell pattern is a
convenience, not a sandbox; anything that writes (`git add/commit/push`, `gh`) still
prompts. With them it offers the Bash sandbox write rule for the workspace,
`{"sandbox": {"filesystem": {"allowWrite": ["<abs main checkout>/.acs/state-machine"]}}}`
(ADR-0136): the absolute path of the main checkout's folder, also from a linked
worktree, always merged into the main checkout's `.claude/settings.local.json` —
never the team file, even when the permission rules went there — keeping other keys
and entries, adding the entry once. `setup detect` reports it as `sandbox_rule` and
`setup apply` returns what it added. It sets the ticket
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

Where documents go is not a wizard answer: `/acs:setup` shows `acs.py docs
where` for the run documents and the living folders (the share choice and the
scope that holds it, each folder with its resolution `source`) and records a
change through `acs.py docs decide` (ADR-0132).

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
  `true`, the one-line out-of-order notice the pre-hook prints). The
  `docs` block holds **answers**, not up-front configuration (ADR-0132):
  `docs.share_run_documents` and the `docs.*_dir` folders are written by
  `acs.py docs decide` when a user answers, and absent means "not asked yet".
  No key locates the workspace (ADR-0102): a run's documents live one folder per phase
  (ADR-0128 — see "Workspace layout"; a legacy `docs/tickets/<ID>/` is only
  read), the workspace at
  `<main-checkout>/.acs/state-machine`, and a skill finds every other repo
  document through `CLAUDE.md` and the repo itself, creating a missing one at
  its `docs/` convention — the machine-readable API contract files `/acs:code`
  makes from an approved contract (ADR-0134) go where the repo keeps them. The
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
