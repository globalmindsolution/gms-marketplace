# Authoring guide — skills & subagents

Best practices for writing and changing the `acs` plugin's SKILL.md files and
agent definitions. The binding *contract* (lifecycle, file shapes, canonical
keys) lives in [INTERNALS.md](INTERNALS.md); this guide is about writing the
components well. The business requirements in the repo's `docs/` folder always
win — change them first, then the implementation.

## Skill definitions (`skills/<name>/SKILL.md`)

### Frontmatter

| Field | Rule |
|-------|------|
| `name` | Equals the directory name, kebab-case. Users invoke `/acs:<name>`. |
| `description` | 1–2 sentences: what it does **and when to use it** — this text is what drives model auto-invocation, so write the trigger condition into it ("Use when …"). Keep it under ~2 lines; details belong in the body. |
| `argument-hint` | Always set for skills taking arguments (`"[ticket-id]"`, `"<request or remote-key>"`). |
| `disable-model-invocation` | **Do not set.** No skill carries it: the CLI refuses a Skill call to a skill that sets it, and every entry point (`/acs:code`, `/acs:project`) dispatches to its internal legs — listed in `acs_lib.skills.SKILL_LEGS` — with a real Skill call. `/ship` invokes each step skill the same way. |
| `disallowed-tools` | `Edit, NotebookEdit` on every hooked skill and `/ship`: coordinators orchestrate — they Write workspace files but never edit repo source themselves (a fix is a remediation iteration through the skill's write role, not a coordinator hot-patch). `/setup` and `/handoff` stay unrestricted (user-present utility skills; `/setup` legitimately edits `.gitignore`). |
| `model` / `effort` / `context` / `agent` | **Do not set.** Hooked skills must run in the invoking context so they can talk to the user; `context: fork` would break clarifying questions. Model/effort for *subagents* comes from `settings.json`, not frontmatter. |

### Body

1. **Address the coordinator, imperatively.** "You are the coordinator of
   `/acs:<skill>`. … Run X. If Y, stop and report Z." No narrative prose, no
   options left to taste.
2. **Deterministic work belongs in scripts, not prose.** Anything a Python
   script can decide (gating, id allocation, state writes, locking) is done by
   `hooks/scripts/*` — the SKILL.md *calls* the script and parses its JSON. If
   you find yourself writing "carefully update the JSON so that …", add a
   helper script instead. ORDER is declared in `workflows/ship.yaml` and walked
   by `acs.py run next` — never restated in prose, and never enforced by
   asking the model to behave.
3. **Follow the hooked-skill skeleton** (INTERNALS.md lifecycle) section by
   section: Start → Resume & reconcile → Reflection loop → User interaction →
   Context pressure → Finish. The Finish section must make the post-hook call
   unconditional — including on failure.
4. **Exact commands, exact paths.** Every command is copy-runnable with
   `${CLAUDE_PLUGIN_ROOT}` paths; every artifact has its partition-relative
   path spelled out. A SKILL.md with a "TODO" or an ambiguous path is a bug.
5. **State lives on disk, never in conversation.** A skill must work in a
   fresh session from recorded state alone. If an instruction depends on "what
   was said earlier", rewrite it to read a file — and make sure something wrote
   that file. Which file depends on the audience: the run ledger
   (`<skill>-state.json`, `run.json`, phase artifacts) stays in the
   workspace partition; the documents a human reads or reviews (`ticket.md`,
   `design.md`, `analysis.md`, `api-contract.md`, `plan.md`, `test-cases.md`)
   live in the repo's ticket docs tree. NEVER hard-code either path: resolve a
   ticket artifact with `acs_lib.artifacts.artifact_path(...)` (or
   `workflow.ticket_artifact_path(...)` from a predicate), which looks in the
   docs folder, then the partition, then the legacy location, and which returns
   the correct WRITE target when nothing exists yet — that one helper is what
   keeps a partition built before the move working instead of broken. A repo
   document (the PRD, the architecture set, the ADR folder) has no setting
   either: find it the way any session does — `CLAUDE.md`, the docs index it
   points at, then a search — and create a missing one at its `docs/`
   convention (ADR-0102).
6. **Work from what you find, not from what ran before you.** A gate checks
   safety brakes only; neither "X has not completed" nor "X's artifact is
   missing" is a reason to refuse, and a SKILL.md must not claim its pre-hook
   enforces an order or an input. Write the Start section to read the upstream
   artifacts that exist and to say what the skill does without each one —
   fall back to the run's subject (the ticket's acceptance criteria, the
   prompt or the document) — and expect to be invoked on your own, out of
   order, with a one-line advisory on stderr.
7. **Plan for the headless case.** Any point where you would ask the user must
   specify the `/ship` behavior too: return a `<handoff status="needs_input">`
   with `<questions>` instead of guessing.
8. **Length budget 180–330 lines.** Shorter usually means missing failure
   paths; longer usually means prose that belongs in INTERNALS.md or a script.
9. **Failure paths are first-class.** Iteration cap, coverage hard-fail,
   blocked gates, lock contention, dirty resume — each needs an explicit
   instruction (status, stop_reason, what to tell the user).
10. **End with the standard completion report.** Every skill closes with a
   "Completion report (normative)" section instantiating the standard block
   from INTERNALS.md — same labels, same order, every terminal status,
   rendered only after the post-hook succeeded. Only the Results/Next content
   is skill-specific; under `/acs:ship` the `<handoff>` XML replaces it.

## Subagent definitions (`agents/<skill>-<role>.md`)

### Frontmatter

| Field | Rule |
|-------|------|
| `name` | `<skill>-<role>`, where the role is named for what it does for that skill (`surveyor`, `author`, `plan-reviewer`, `implementer`, `build-checker`, …) and appears in `acs_lib.skills.ROLE_KINDS` with its kind — `survey`, `write` or `judge` (ADR-0109). A new role is one line there. Never reuse an agent across skills — the per-skill charter is the point. |
| `description` | One sentence saying what this role does for `/acs:<skill>`, ending "Spawned by the /acs:<skill> coordinator with a JSON task; not for direct invocation." |
| `tools` | Survey and judge roles: `Read, Glob, Grep, Bash, Write` (Write *solely* for its own `steps/<skill>/` artifacts — restate this in the body; Bash is for read-only inspection and running tests/builds). The allowlist deliberately omits `Agent` and `Skill`. Write roles: omit `tools` (they need broad file/shell access) but set `disallowedTools: Agent, Skill` — decomposition is the coordinator's job, and a skill invocation from inside a subagent would re-enter the hook pipeline. |
| `disallowedTools` | `Agent, Skill` on every write role (see above). |
| `model` / `effort` | **Never set.** The coordinator resolves `settings.json` `models.<tier>` / `models.overrides.<skill>.<tier>` for the role's tier — `planner` for survey roles (and `create-impl-plan`'s planner), `executor` for write roles, `verifier` for judge roles (`acs_lib.skills.model_tier`) — and applies them at spawn; frontmatter values would silently fight user configuration. |

### Body (the system prompt)

1. **One role, one job.** A skill owns only the roles its own logic needs,
   and each role's charter states what it does *for this skill* — not
   generic filler. When the work has two jobs (a read-only survey that ends in
   questions, then a write after the answers), make them two roles — a survey
   role on iteration 1 whose notes are frozen, and a write role that authors
   from them — rather than one agent that does both. Otherwise the write
   role carries a `## Survey — what you establish before you write
   (iteration 1)` section and a `## The authoring notes (mandatory, every
   iteration)` section that records it. The judge must be meaningfully
   different from the writer; if its checks read like the writer's survey, it
   will rubber-stamp. A mechanical sequence of commands that nothing
   independent reviews needs no subagent at all: the coordinator runs it
   inline from `references/` (`create-ticket`, `create-pr`, `merge-pr`).
2. **Spell out the I/O contract.** Input: an XML `<task skill="<skill>"
   phase="<role>" …>` (objective, file `<inputs>`, constraints,
   prior-iteration findings in `<context>`). The phase is the role. Output:
   the **final message is only** an XML `<result>` per
   `the SubagentStop hook's message check` — nothing after it. Malformed XML gets
   re-requested once, then the run fails; don't make the coordinator parse
   prose. Every constraint the agent reads must be a name in the XSD's
   `constraintName` vocabulary (ADR-0093): name it there before naming it in
   the charter, spell it identically in the SKILL.md that emits it, and never
   invent a per-agent spelling — the validator refuses a name outside the
   vocabulary, and `tests/acs/test_message_schema_derivation.py` refuses a
   vocabulary entry no prose consumes.
3. **Mandate the phase artifact, named after the role.** Whoever surveys
   writes `iter-<n>/authoring.md` (the survey, then the findings addressed)
   before the deliverable; every survey and write role writes
   `iter-<n>/<role>.json` (parallel implementers: `iter-<n>/implementer-<k>.json`);
   every judge writes `iter-<n>/<role>.md` (see INTERNALS.md "Phase
   artifacts") and references it in `<outputs>`. The SubagentStop snapshot is
   `iter-<n>/<role>-message.xml`, so never name a report that. Resumption
   depends on these files existing even when the run dies right after the
   role. There is no `iter-<n>/plan.md` (ADR-0092). `/acs:create-impl-plan`'s
   deliverable is itself a plan — its planner's draft is the single
   per-ticket `plan.md` (MAR-70), and `plan.md` is the only name ever read or
   written for it, in every case, including on resume. `/acs:code` ships one
   implementer and READS the plan artifact.
4. **No memory assumptions.** The subagent shares nothing with the
   coordinator: every fact it needs must come from `<inputs>` file paths it
   reads itself. Never write "as discussed" or rely on the ticket being "the
   current one" — the ticket id is in the task.
5. **No sub-subagents, no scope creep.** Decomposition is the coordinator's
   job; a subagent that spawns agents or "helpfully" fixes things outside its
   role breaks the audit trail. Write roles change only what their task's
   file map covers.
6. **Grounding is mandatory.** Every agent body ends with the standard
   "Grounding (anti-hallucination)" section (identical wording in every agent
   file — copy it from any existing agent): every decision/claim/finding cites the
   file (path + line/section) or quotes the command output it rests on;
   nothing unobserved is asserted; missing inputs go to `<errors>`;
   unverifiable points are flagged as assumptions, never silently defaulted.
   Judges treat ungrounded notes and reports as findings, and every judge's
   charter says it will "police grounding".
7. **Judges: independence is the value.** List every check dimension for
   the skill explicitly (e.g. `/acs:review-code`'s review dimensions plus
   spec conformance, tests, coverage). Re-run cheap checks rather than
   trusting recorded results. All findings block — write findings the
   write role can act on (file, expectation, observed behavior), one
   `<finding>` per issue, full detail in the judge's `iter-<n>/<role>.md`.
8. **Length budget 60–140 lines** per agent (the grounding section counts).

## Tool-restriction policy (summary)

| Component | Restriction | Enforces |
|-----------|-------------|----------|
| Hooked skills + `/ship` | `disallowed-tools: Edit, NotebookEdit` | coordinators orchestrate; only write roles mutate sources |
| `/setup`, `/handoff` | none | user-present utility skills |
| Survey and judge roles | `tools: Read, Glob, Grep, Bash, Write` | read-only discipline + own phase artifacts; no spawning, no skill calls |
| Write roles | `disallowedTools: Agent, Skill` | no sub-subagents; no re-entering the hook pipeline |

Be honest about what this buys: with Bash granted (judges must run
tests/builds, writers run everything), these lists are
**guardrails against accidental scope creep, not a sandbox** — a shell can
touch anything. The *enforced* boundaries remain the deterministic layer:
pre-hook safety brakes, the file-map guard (armed while a write role runs), locks, and the fact
that a skipped post-hook leaves the step un-satisfied in the ledger the workflow
walk reads. Tighten tool lists for signal and accident-prevention; never rely on
them for ordering or safety guarantees.

## Cross-cutting rules

- **Clarification ledger.** All requirement Q&A goes through
  `clarify.py` into `<partition>/clarifications.json` (see INTERNALS.md
  "Requirement clarification"): research first, ask once at the cheapest
  phase, record everything, assumptions are visible debt. A skill that asks
  the user something the ledger already answers — or acts on an answer
  without recording it — is defective.
- **Altitude boundaries between pipeline artifacts.** Each artifact owns one
  altitude and does not duplicate the next one down: `ticket.md` owns the WHY
  and the acceptance criteria; `design.md` owns options/decision/architecture;
  `analysis.md` owns the impact map, assumptions and risks; `api-contract.md`
  owns the external surface; `test-cases.md` owns the WHAT to prove — `TC-n`
  cases traced to ACs; `plan.md` owns the HOW — the authoritative file map,
  implementer decomposition, concrete failing tests, commands. A skill reads the
  upstream artifacts that EXIST and works without the ones that do not (each is
  produced by a step that may legitimately have been skipped or not yet run);
  it re-litigates an upstream artifact only on contradiction with reality.

- **Namespaced invocations everywhere** users/models will type them:
  `/acs:ship`, not `/ship`.
- **Schema changes are additive.** State files tolerate unknown keys; never
  rename canonical `states` keys (INTERNALS.md table) without migrating every
  reader (gates in `acs_lib/gates.py`, downstream SKILL.mds, tests).
- **Plan mode:** never instruct skills or agents to enter native plan mode —
  see INTERNALS.md "Why not Claude Code's native plan mode".
- **Test the deterministic layer.** Any change to `hooks/scripts/*` needs a
  test in `tests/` (`python3 -m unittest discover -s tests`); CI also
  byte-compiles scripts and checks every SKILL.md / agent file has
  `name` + `description` frontmatter.
- **Keep docs honest.** A behavior change updates, in this order: `docs/`
  requirements (+ decision-log row) → INTERNALS.md contract → SKILL.md /
  agents → tests → CHANGELOG.md.

## Adding a skill

A new skill is a directory. There is no registry and no per-skill manifest
(ADR-0109): a skill exists because `skills/<name>/SKILL.md` exists, and it
owns the agents named after it. In order:

1. **Write `skills/<name>/SKILL.md`** to the rules above, with its procedures
   under `skills/<name>/references/` and, when it is hooked, the `states` keys
   and `outcome` vocabulary it records in `skills/<name>/state.schema.json`.
2. **Give it only the subagents its work needs**, one
   `agents/<name>-<role>.md` per role, each role named for what it does and
   listed in `acs_lib.skills.ROLE_KINDS` with its kind. A skill whose work is a
   sequence of commands nothing independent reviews owns none and runs them
   inline. `acs_lib.skills.unreachable_agents()` must stay empty.
3. **Decide whether it is HOOKED.** A hooked skill gets: an entry in the
   matching list in `acs_lib/_common.py` (`PRODUCT_SKILLS` /
   `WORKFLOW_SKILLS` / `PLANNING_SKILLS` — never a fourth list), thin
   `hooks/scripts/pre-<name>.py` and `post-<name>.py` wrappers, and a line in
   `.coveragerc`'s forwarder omit list. `HOOKED_SKILLS` is derived from the
   three lists, so `acs step start --step`, `dispatch.py`, the SessionEnd net
   and `models.overrides` all follow for free. An UNHOOKED skill (a utility)
   needs none of this and must appear in `UNHOOKED_SKILLS` instead.
4. **Decide whether it is a LEG.** A skill another skill dispatches to (as
   `/acs:code` dispatches to its delivery-path legs) is listed in
   `acs_lib.skills.SKILL_LEGS` with its entry point, and a workflow never
   names it.
5. **Decide whether it is a PIPELINE STEP.** Adding a step is one line in
   `workflows/ship.yaml`'s `steps`, in the position it should run. The list
   only keeps the order: `acs workflow validate` checks that each step is a
   skill that ships and not a leg, and that every loop goes back — never what
   a step needs. `merge-pr` and `release` are never steps.
6. **Brake only on damage.** A pre-hook refusal is for a safety brake —
   running now would do something re-running cannot undo — added to `BRAKES`
   in `acs_lib/brakes.py` (a step) or `SUBJECT_GATES` in `acs_lib/gates.py`
   (a skill that is not a step). Never refuse because another skill has not
   run or its artifact is missing: the skill falls back to the run's subject.
   A repo document the skill needs is not a hook's to check — no setting says
   where it lives — so the skill finds it at Start (ADR-0102).
7. **Add the skill-surface tests.** Several modules enumerate the inventory
   (skills on disk, agent files, hooks entries, README rows, INTERNALS
   sections); grep for an existing skill's name to find them all, and update
   each — they exist precisely so a half-registered skill cannot ship.
