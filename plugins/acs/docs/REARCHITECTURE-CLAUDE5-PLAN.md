# acs re-architecture for Claude 5 — execution plan

Companion to [REARCHITECTURE-CLAUDE5.md](REARCHITECTURE-CLAUDE5.md) (the
findings). This document turns every finding into ticket-shaped work with
scope, acceptance criteria, dependencies, and order. Nothing here is minted
yet; each epic below is written so `/acs:create-ticket` can take it verbatim.

## 1. Goals, non-goals, constraints

**Goals**

1. Every finding in the report has an owner ticket (traceability table in §9).
2. The pipeline's integrity stops depending on coordinator goodwill: gates,
   phase results, verdicts, and the finish step are enforced by hooks and
   scripts.
3. Prompt volume drops by more than half while preserving every behavioral
   guarantee the requirements docs state.
4. Topology and effort are tuned per lane and per role, with measured
   evidence before the expensive choices are cut.
5. Consumers can upgrade in place: workspace state files stay
   backward-compatible; `/acs:update` migrates what must change.

**Non-goals**

- No change to the ticket → code → docs-sync → PR → merge spine or to the
  human gate before merge.
- No second agent runtime (Codex) — the adapter is deleted, not finished.
- No new tracker integrations.

**Constraints that shape the order**

- Each epic ships alone behind green CI and is dogfooded through
  `/acs:ship` on this repo before release.
- Measurement (E7) runs its baseline *before* topology (E5) changes anything.
- Prose tests are converted in the same PR that rewrites the prose they pin;
  a PR never deletes a test without adding the structural check that replaces
  it.
- Requirements docs (`docs/requirements/`) and ADRs change first in each PR,
  then INTERNALS, then skills/agents, then tests, then CHANGELOG (the repo's
  existing rule).

## 2. Work breakdown

Sizes: S ≤ 1 session / 1 PR; M = 2–3 PRs; L = 4+ PRs. "Tests" names the
test change that lands with the work. "Supersedes" names ADRs to write.

### E0 — Correctness fixes and hygiene (no architecture change)

Ships as 0.4.9. Every item is independent; one PR per row or batched.

| Id | Scope | Acceptance criteria | Tests | Size |
|---|---|---|---|---|
| E0.1 | `skill-start.py --allocate` allocates only when no partition exists for the resolved id; `create-ticket/SKILL.md` Start passes the ticket id on resume | Resuming `/acs:ship` on an incomplete create-ticket reuses the ticket; fresh runs still mint | new case in `test_skill_start*.py`; s03-style eval seed | S |
| E0.2 | `update_pipeline(..., extra=None)` merges arbitrary step fields; ship's `fix_loops` bookkeeping goes through it; `fix_loops` resets when `/acs:test` is re-entered after a `failed` cap | `steps.test.fix_loops` observable in `pipeline-state.json`; resume after cap re-runs test once | `test_acs_lib_state_locks.py` | S |
| E0.3 | `/acs:test --for-ticket` writes `steps.test` to `pipeline-state.json` (or `gate_docs_sync`'s remedy names the command that actually does); pick the former | Following the gate's error message opens the gate | `test_acs_lib_gates.py` | S |
| E0.4 | `templates/CLAUDE.acs.md`, root `CLAUDE.md`, README pipeline lists, `setup/SKILL.md` step list, `story-default.md` "spec", `pr-default.md` verifier wording: current pipeline order incl. docs-sync/test | grep for `create-spec` in templates/README/skills returns nothing | `test_templates*.py` | S |
| E0.5 | merge-pr approvals rule: require `APPROVED` only when the repo's branch protection requires reviews **or** the invocation is agent-initiated (ship); setup and merge-pr agree | Solo maintainer with 0-review protection can merge via skill; ship-invoked merge still requires review | `test_merge_pr*.py` | S |
| E0.6 | `dispatch.py`: catch `TimeoutExpired` → exit 2 with message; call `GATES[skill]` in-process (delete 15 `pre-*.py`); one `post.py --skill` (delete 15 `post-*.py`, keep `--pr` branch) | Hung gate blocks; forwarders gone; `.coveragerc` omit list shrinks | `test_dispatch*.py`, `test_hook_entrypoints.py` | S |
| E0.7 | `_read_result_from_argv`: empty/missing result → exit 1, never default `status: completed` | `post.py` with no result fails closed | `test_acs_lib_hook_entrypoints.py` | S |
| E0.8 | `settings.schema.json` `models.overrides.propertyNames` derived from `HOOKED_SKILLS` (drop `ship`, add 8 missing); `validate_models` checks effort enum and override skill names | Unknown skill/effort rejected at gate with clear message | `test_acs_lib_settings.py` | S |
| E0.9 | Unpin model ids: `test_settings_models_pinned.py` and `test_setup_offers.py` assert shape + one `RECOMMENDED_MODELS` constant; setup prose reads the same constant | Changing the recommended id is a one-line change | those two tests | S |
| E0.10 | Delete dead code: `codex_adapter.py` (+test), `consistency_findings.py`, `PIPELINE_STEP_ORDER`, `backfill_distinct_pr_count`, `validate_batch`/`batch_overall_ok`, `<metrics>` branch in `validate_xml.py`, `create-spec` residue in statusline/subagent-statusline/validate_xml, six orphaned agent files, six executor "Delivery" steps, `mmdc` mention | `git grep create-spec plugins/acs` empty; agent count 39 | registry/topology tests updated | S |
| E0.11 | Fix stale prose facts: "across N dimensions" examples, `tokens`/`cost_usd` in result examples, `iterations <n>/3` on non-iterating skills, completion-report label substitutions per INTERNALS, README merge-pr invocability, status vocabulary (`needs_input` added to `result.json` enum; create-pr stops mapping it to `failed`) | INTERNALS and skills agree; one status vocabulary | `test_skill_contracts.py` sections | S |
| E0.12 | Cost-sampling adapter: isolate the five undocumented Claude Code interfaces into `cc_transcript.py`; accept fractional-second timestamps; record `claude --version` with samples | Degradation is a single switch; timestamp format change no longer zeroes usage | `test_usage_reader.py`, `test_cost_sampler.py` | S |

Exit: 0.4.9 tagged; all eight report bugs closed.

### E1 — Deterministic kernel

Ships in 0.5.0 with E2 and E3. Supersedes nothing; strengthens ADR 0001.

| Id | Scope | Acceptance criteria | Tests | Size |
|---|---|---|---|---|
| E1.1 | `hooks/scripts/acs.py` single CLI: `gate`, `start`, `finish`, `lane derive\|escalate\|deescalate`, `stakes recommend`, `plan check`, `phase validate`, `context`, `readiness`, `pr metadata fill`, `tracker sync`, `setup wizard` (skeleton; filled by E1.4–E1.6). Old entry points remain as shims for one release | Every Python function a SKILL.md names today has a subcommand; no SKILL.md contains `import acs_lib` or a heredoc after E4 | `test_acs_cli.py` contract tests over JSON I/O | M |
| E1.2 | Split `acs_lib.py` into `acs/{settings,repo,state,gates,lanes,setup_helpers,metrics}.py` with a facade; table-drive the six `hld/tech-stack.md` gates; unify heading scanners on `structure_lint`; collapse the three apportioners and the two cost folders | No behavior change; module sizes < 800 lines; duplicate functions removed | existing suite green; new `test_gates_table.py` | M |
| E1.3 | Derived `result.json`: `acs finish` computes `verifier_passed` from the verifier's `verdict.json` (E1.7), `tests`/coverage from recorded command output in the execute report, `pr` from `gh pr view`; coordinator-supplied values for these keys are ignored (logged when they disagree) | A coordinator that writes `verifier_passed: true` without a passing verdict cannot open the create-pr gate | `test_finish_derivation.py` | M |
| E1.4 | `acs readiness <pr>`: merge-pr's four readiness dimensions as a pure function of `gh pr view --json`; skill keeps only gray-zone judgment | Readiness verdict reproducible from a fixture JSON | `test_readiness.py` | S |
| E1.5 | `acs pr metadata fill` (create-pr 6a Project fields, labels, assignee, CODEOWNERS) and `acs tracker sync` (create-ticket step 5) | create-pr/create-ticket prose for these steps shrinks to one command each | fixtures with recorded `gh` JSON | M |
| E1.6 | `acs setup wizard`: drives the questionnaire, defaults, file writes, gitignore/exclude edits, CLAUDE.md block, statusline, CI copies; the skill handles conversation only | `setup/SKILL.md` ≤ 200 lines; wizard idempotent on re-run | `test_setup_wizard.py` | M |
| E1.7 | Verifier `verdict.json`: verifier writes `{passed, findings[], dimensions{}}` next to its report; `SubagentStop` hook (E1.8) validates and copies it to `phases/<skill>/iter-<n>-verdict.json` | Verdict exists for every verify phase; coordinator never writes it | schema + hook test | S |
| E1.8 | Hooks: `SubagentStop` (matcher `^acs:`) → `acs phase validate` + snapshot; `Stop` → block when `runs[-1].status == in_progress` for this checkout and no `result.json` (message: run the finish step); `PreCompact` → write `handoff-context.md` from state; `SubagentStart` records active agent for E1.9 | Ending a hooked skill without finishing is blocked; compaction never loses in-flight state | hook payload fixtures in `test_hooks_*.py` | M |
| E1.9 | Executor file-map guard: `PreToolUse` on `Edit\|Write\|NotebookEdit` while an `acs:*executor` is active denies paths outside the task's file map (read from the current `<task>`/plan) with the executor's `needs_input` message | Out-of-map write is blocked deterministically; prose rule becomes one sentence | hook test with fixture map | S |
| E1.10 | Locks and writes fail closed: `_guarded_repo_write`/`allocate_ticket_id` error after the spin budget; `lock_is_stale` documents its cross-host limits and adds a `--force-unlock` CLI with audit entry | No silent fail-open path remains in state writes | `test_acs_lib_state_locks.py` | S |

Exit: every gate-relevant fact in state is script-derived; `Stop` enforces finish.

### E2 — Phase messaging

Ships in 0.5.0. Supersedes ADR 0005; amends 0069, 0074 (D-4), 0082 §5;
amends `requirements/functional/reflection.md:239-252`,
`architecture/lld/contracts.md:6-25`.

Decision D-XML (maintainer, before E2.2): return format. Default here is a
one-line JSON pointer; alternative is keeping the `<result>` XML element as
the return *format* while still removing the ritual. Both share E2.1/E2.3.

| Id | Scope | Acceptance criteria | Tests | Size |
|---|---|---|---|---|
| E2.1 | `schemas/phase-result.schema.json` (one schema for plan/execute/verify/handoff results; enum sourced from `HOOKED_SKILLS`); subagents write `iter-<n>-<phase>.json`; `acs phase validate` stamps `skill/phase/ticket/iteration` from context and validates | One enum source; `xmllint` removed from `ci.yml` and `.acs/settings.json`; the four enum mirrors are gone | schema tests; `test_message_schema_skill_enum.py` replaced | M |
| E2.2 | Return channel per D-XML: subagent's final message is a pointer (`{"result": "<path>"}`) or the XML element; either way no self-check Bash, no coordinator validate step, no re-request loop in prose — validation is E1.8's hook | Zero `validate_xml.py` references in skills/agents; message round trips per phase drop from 3 tool calls to 1 | `test_skill_contracts.py` sections rewritten | M |
| E2.3 | `<task>` input envelope: keep XML tags; rendered by `acs task render --skill --phase --ticket --iteration --inputs … --constraints …` so attributes come from context, not the model | Coordinator prose for messaging is one command per phase | `test_task_render.py` | S |
| E2.4 | Delete `validate_xml.py`, `acs-messages.xsd` (or demote XSD to documentation if D-XML keeps the element), `.xml` snapshots (hook writes `.json` snapshots), `test_metrics_self_estimate_removed.py`, `TestValidators` | Repo has one validator path | — | S |

Exit: no model-side validation ritual; one schema family.

### E3 — Model and effort plumbing

Ships in 0.5.0. Amends ADR 0082 P4; requirements `configuration.md`;
`prd.md:187,395`; `roadmap.md:268`.

Decision D-AGENTS (maintainer, before E3.1): shape A (3 role agents +
charters), B (generated per-skill agents), and whether C (setup-rendered
project agents) ships now or later. Plan assumes A + C.

| Id | Scope | Acceptance criteria | Tests | Size |
|---|---|---|---|---|
| E3.1 | Role agents `agents/planner.md`, `executor.md`, `verifier.md` with frontmatter `effort` defaults (high/medium/high), `tools`/`disallowedTools`, `maxTurns`; body = role base (I/O contract, grounding, hard rules once); task prompt names `skills/<skill>/references/charter-<role>.md` | 3 agent files + charters replace 39; description budget well under 15K tokens | `test_agent_registry.py` rewritten; charter presence per skill | M |
| E3.2 | Coordinator spawn rule: pass `model` per call from `context.models.<role>`; delete "fail if effort rejected"; verify full-id acceptance on the CLI build during dogfood and record the result in INTERNALS | Settings `model` reaches the spawn; effort documented as frontmatter default | contract test on `skill-start` output; manual dogfood note | S |
| E3.3 | (C) `acs setup wizard` renders `.claude/agents/acs-<role>.md` from `templates/agents/<role>.md` with `model`/`effort` from settings and the agent-scoped hooks; coordinator prefers `acs-<role>` when present; `/acs:update` re-renders on template change; setup documents the trust requirement | A consumer's `effort: medium` for executors is honored; re-render idempotent | `test_setup_agents_render.py` | M |
| E3.4 | `usage_reader`/`subagent-statusline` attribution keyed on role, not skill-role suffix; recognizes all skills | Attribution complete for every spawn | `test_usage_reader.py`, `test_subagent_statusline.py` | S |

Exit: model and effort configurable and observable (`/tasks` shows both).

### E4 — Prompt collapse and Claude 5 register

Ships in 0.6.0 (largest volume, lowest behavior change). One PR per skill
group; each PR converts the prose tests it touches.

| Id | Scope | Acceptance criteria | Tests | Size |
|---|---|---|---|---|
| E4.1 | `skills/_shared/coordinator-protocol.md` (Start, Resume & reconcile, loop mechanics, clarification ledger, finish, completion report) + a style guide section in AUTHORING for Claude 5 register (positive scope statements, one rule once, no caps, delegation guardrail once per role, keep concrete re-run commands, drop exhortations) | Every hooked skill references the shared file instead of restating | `test_coordinator_protocol.py` (structure) | S |
| E4.2 | `code/SKILL.md` rewrite: ≤ 200 lines; lane table; every lane/escalation/plan-approval step is one `acs …` command; strip MAR/D-n/AC-n/ADR refs; move plan-approval verbatim clauses to `acs plan check` (section presence + AC↔test mapping) | Line count; zero identifiers; `plan check` replaces `plan_approval_eligible` string matching | `test_code_skill_structure.py` replaces `test_lane_conditional_planning.py`, `test_code_verifier_plan_anchoring.py` phrase pins | M |
| E4.3 | `code` charters (planner/executor/verifier): verifier dimensions regrouped (merge `required-sections`+`structure`, `features`+`acceptance-criteria`; `audience-style` → info); grounding once; remove "trust nothing recorded" exhortations, keep re-run commands | Verifier charter ≤ 150 lines; dimension list ≤ 10 | topology tests → structural | M |
| E4.4 | ship / create-ticket / create-pr / merge-pr / docs-sync / test / release / handoff / update / install-hooks / metrics / usage rewrites against the shared protocol; deterministic steps replaced by E1 CLIs; progressive disclosure (`references/` for setup integrations, PR troubleshooting, fan-out/split modes) | Each ≤ 150 lines core; all skills under budget | per-skill structure tests | L |
| E4.5 | Doc-family and project skills rewritten on the shared protocol (or folded by E5.4/E5.6 first, then rewritten once) | as above | as above | M |
| E4.6 | Prose-test conversion policy: `tests/acs/structure/` asserts required sections and command presence via `structure_lint`; delete phrase-pinning assertions as their prose is rewritten | Count of modules reading `SKILL.md` text for wording falls below 15 | — | runs across E4 |

Exit: skills ≈ 4,000 lines total (from ≈ 11,900); agents ≈ 600 + charters.

### E5 — Topology by lane

Ships in 0.6.0 after E7's baseline exists. Supersedes ADR 0004 (and 0073,
0077–0079, 0083, 0084 chain), 0067, 0074, 0076; amends 0034, 0042;
`reflection.md:24-140`; INTERNALS lifecycle.

Decision D-LENSES (maintainer, after E7.3 data): keep 4 lenses on COMPLEX,
cut to 2, or 1. Plan assumes 2. Decision D-APPROVAL: plan approval becomes a
gate, or `plan-approval.py` and verifier dimensions 15/16 are deleted; plan
assumes deletion, with `acs plan check` as the deterministic floor.

| Id | Scope | Acceptance criteria | Tests | Size |
|---|---|---|---|---|
| E5.1 | `reflection` settings: `max_iterations` per lane (defaults 1/1/2/3), `lenses` (default 2 on COMPLEX); `VERIFY_ITERATION_CAP` reads settings | Settings validated; defaults documented | `test_acs_lib_settings.py` | S |
| E5.2 | `/acs:code` lane topology: TRIVIAL = executor + deterministic checks (tests, coverage, lint, `plan check`) + optional `type: prompt` rubric hook; SMALL = + 1 verifier; STANDARD = planner + N executors + 1 verifier; COMPLEX/high = 2 lenses merged by coordinator; git-history lens only when touched paths have revert history | Spawn counts per lane match table in an eval fixture | `test_code_topology.py` (structural + eval s03 variants) | M |
| E5.3 | Convergence rule: `acs findings compare iter-<k> iter-<k-1>`; substantively repeated findings stop the loop with `needs_input` | Repeated identical finding never burns the cap | unit test on comparator; eval seed | S |
| E5.4 | `create-docset <set>`: one skill replacing quality/principles/standards/operations, driven by `DOC_SETS` table (settings key, files, upstream slice, audience profile, sentinel); `required_sections` derived from template headings; coordinator-authored; gates: `structure_lint`, `citation_check`, docs-only diff; optional single reviewer for stack conformance; `--all` replaces `create-docs` | Four skills + 12 agents + create-docs deleted; behavior parity on this repo's doc sets | `test_create_docset.py`; eval: bootstrap on a fixture repo | L |
| E5.5 | prd / architecture / requirements / design → author + reviewer (author writes `iter-1-plan.md` inline first); planners folded | Spawns per run drop from 3 to 2; rubric unchanged | topology tests | M |
| E5.6 | docs-sync → single fresh-context executor; reviewer only on `full` depth; cap by `verify_depth` | Light-lane docs-sync is one spawn | tests + eval | S |
| E5.7 | create-project / standardize-project: fold planner; keep the build-running verifier; optional merge into `create-project --mode brownfield` with mode-gated dimensions | Decision recorded; if merged, one skill | tests | M |
| E5.8 | Remove optional executors from create-ticket / create-pr / merge-pr / release (inline only) | No agent spawn in apply-work skills | topology tests | S |
| E5.9 | Lane escalation: `acs lane escalate --trigger … --to-stakes high` performs guard/escalate/persist/event atomically; de-escalation `acs lane deescalate --clarify-ref C-n`; SKILL prose is two sentences | Escalation event and axes always consistent (one writer) | `test_lanes_cli.py` | S |
| E5.10 | Autonomy: `autonomy: confirm\|recommend\|auto` setting; create-ticket presents one summary with defaults; due date asked once | Under `auto`, create-ticket completes headless with recorded assumptions | tests + eval s02 variant | S |

Exit: spawns per STANDARD `/code` run ≤ 1 + N + 2 per iteration; doc family
is one skill.

### E6 — Ship as a driver

Ships in 0.6.0. Amends ship requirements; deletes the full-verify boundary.

| Id | Scope | Acceptance criteria | Tests | Size |
|---|---|---|---|---|
| E6.1 | `acs pipeline next <ticket>` returns the next step, or the blocker, from ledger + gates; ship loops on it | Ship prose ≤ 150 lines; no inline Python | `test_pipeline_next.py` | S |
| E6.2 | Each step runs as an isolated Agent (a step-coordinator agent whose prompt is the step skill via `skills` preload or `context: fork` — pick after a dogfood spike); ship reads only `handoff.json` | Ship's context stays under a measured bound across a full pipeline; full-verify boundary deleted | eval: end-to-end ship on fixture | M |
| E6.3 | Automatic epic fan-out and child dispatch; children with disjoint file maps run in parallel | One command from epic to child PRs, stopping before merge | eval s07 extension | M |
| E6.4 | needs_input relay through the ledger (`clarify.py`) rather than `Q:/A:` args; one status vocabulary | Relayed answers are recorded before the step resumes | tests | S |
| E6.5 | Optional spike: Workflow-tool script for child fan-out; adopt only if it simplifies E6.3 | Decision recorded | — | S |

### E7 — Measurement

Starts in parallel with E1; baseline captured before E5 lands.

| Id | Scope | Acceptance criteria | Tests | Size |
|---|---|---|---|---|
| E7.1 | `Sandbox.run_skill(model=…, settings_override=…)`; `--model` and `--settings` flags on `run_evals.py` | Same scenario runnable on Opus 5 and Sonnet 5 | harness tests | S |
| E7.2 | Baseline JSON per scenario: iterations-to-pass, findings count, spawns, cost, wall time, tokens; `--compare baseline.json` reports deltas | Regression visible as a diff | harness tests | S |
| E7.3 | Verifier-accuracy scenarios: seeded defect must block; seeded AC omission must block; clean run must pass; run with 1, 2, 4 lenses | Data for D-LENSES | new eval s09 | M |
| E7.4 | Relax s04 (sanctioned first-skill set) and s02 (schema validity, not classification); allow `needs_input` as a valid terminal for headless runs | Smarter path choices do not fail evals | eval edits | S |
| E7.5 | Adopt `claude plugin eval` with `llm` graders when available to the org; mirror the free tier | Optional | — | S |
| E7.6 | Dogfood settings: `e2e.command` no longer launches the paid suite from inside verifier iterations; paid suite becomes the release gate only | Verifier iterations spawn no `claude -p` | settings + docs | S |

### E8 — Documentation and release

| Id | Scope | Size |
|---|---|---|
| E8.1 | ADRs: supersede 0005, 0004 chain, 0067, 0074, 0076; amend 0034, 0042, 0069, 0082, 0022; new ADRs for kernel CLI, hook enforcement, role agents, lane topology, phase results | M |
| E8.2 | Rewrite INTERNALS (lifecycle, hook binding, phase artifacts, subagents, messaging) and AUTHORING (budgets, style guide, charter rules) | M |
| E8.3 | Requirements docs: reflection, configuration, hooks, workspace-and-state; PRD facts (agent counts, topology) and roadmap rows | M |
| E8.4 | `/acs:update` migrations: render project agents (E3.3), drop `.xml` snapshots, settings key additions; CHANGELOG with breaking-change flags; versions 0.4.9 / 0.5.0 / 0.6.0 | S |

## 3. Sequencing

```
E0 ─────────────► 0.4.9
E7.1–E7.4 (parallel from the start; baseline captured before E5)
E1.1 ─► E1.2 ─► E1.3/E1.7/E1.8 ─► E1.9/E1.10
E1.1 ─► E2.1 ─► E2.2/E2.3 ─► E2.4
E3.1 ─► E3.2 ─► E3.3 ─► E3.4              (needs E1.8 for hook capture)
E1 + E2 + E3 + E8 (partial) ─────────────► 0.5.0
E4.1 ─► E4.2/E4.3 ─► E4.4 ─► E4.5 (with E4.6 throughout)
E7.3 data ─► D-LENSES ─► E5.1–E5.3 ─► E5.4–E5.8 ─► E5.9/E5.10
E6.1 ─► E6.2 ─► E6.3/E6.4 ─► E6.5
E4 + E5 + E6 + E8 (rest) ────────────────► 0.6.0
```

Critical path: E1.1 → E1.8 → E2.2 → E3.3 → E4.2 → E5.2 → E6.2. Parallel
tracks: E7 (independent), E0 items (independent), E5.4 doc-family collapse
(depends only on E1.1 and E4.1).

Decision gates the maintainer must clear, in order:

| Decision | Before | Options |
|---|---|---|
| D-XML | E2.2 | JSON pointer return (default) / keep XML element as return format |
| D-AGENTS | E3.1 | A + C (default) / B / A only |
| D-LENSES | E5.2 | 2 (default) / 4 / 1, from E7.3 data |
| D-APPROVAL | E5.2 | delete plan approval (default) / make it a gate |
| D-PROJECT | E5.7 | merge standardize-project into create-project / keep separate |
| D-STEPS | E6.2 | step agents via `skills` preload / `context: fork` / Workflow |

## 4. Release plan

| Version | Contents | Breaking? | Migration |
|---|---|---|---|
| 0.4.9 | E0 | No | none |
| 0.5.0 | E1, E2, E3, E7.1–E7.4, E8 partial | Yes: `.xml` snapshots → `.json`; `result.json` gate keys derived; `pre-*/post-*` shims deprecated | `/acs:update` renders project agents, warns on custom `settings.models` effort semantics, converts nothing in workspace (readers accept both) |
| 0.6.0 | E4, E5, E6, E8 rest | Yes: four doc skills replaced by `create-docset`; `create-docs` removed; ship boundary removed; iteration caps configurable | `/acs:update` maps old skill names to `create-docset <set>` in ledgers and docs; CHANGELOG lists removed skills |

Each release: paid eval tier + E7.2 baseline comparison as the gate; dogfood
one real ticket through `/acs:ship` on this repo first.

## 5. Test strategy across the plan

- **Kernel**: contract tests over `acs.py` JSON I/O (stdin/stdout), fixture
  workspaces via the existing `AcsWorkspaceCase`. Every subcommand has a
  failure-path test.
- **Hooks**: payload fixtures for `PreToolUse`, `SubagentStart/Stop`, `Stop`,
  `PreCompact`, `SessionEnd`; assert decisions and file side effects.
- **Prompts**: `tests/acs/structure/` asserts required sections, referenced
  commands exist, line budgets, zero ticket identifiers, zero
  `validate_xml` references. Phrase pins are deleted as their prose is
  rewritten, never before.
- **Behavior**: eval scenarios s01–s09 with the E7.2 baseline; model matrix
  Opus 5 / Sonnet 5 for planner/executor/verifier combinations on s03 and
  s09.
- **Coverage gate**: unchanged (90%); `.coveragerc` omit list shrinks as
  forwarders disappear.

## 6. Risk register

| Risk | Mitigation |
|---|---|
| `SubagentStop`/`Stop` hook semantics differ for background subagents or in `-p` mode | E1.8 spike first on the current CLI in both interactive and headless runs; keep the `Stop` block message actionable; fall back to the next-gate check that exists today |
| Full model ids rejected by the Agent tool on some builds | E3.2 dogfood check; `RECOMMENDED_MODELS` can hold aliases; document |
| Plugin agents cannot carry hooks → file-map guard only via `hooks.json` | E1.9 uses `SubagentStart` to know the active agent; project agents (E3.3) carry it natively |
| Prose rewrite breaks 78 tests at once | E4.6 policy: one skill group per PR, tests converted in the same PR |
| Topology cut degrades review quality | E7.3 runs before E5; D-LENSES made on data; `reflection.lenses` lets a consumer restore 4 |
| Workspace state incompatibility across versions | Readers accept old and new shapes for one release; `/acs:update` migration; state schemas stay additive |
| Doc-family collapse loses set-specific nuance | `DOC_SETS` table carries per-set audience profile and upstream slice; parity check against this repo's existing doc sets in E5.4 |
| Ship isolated-step spawn needs user interaction (`AskUserQuestion` unavailable in subagents) | E6.2: step agents return `needs_input` handoffs; ship (main context) asks the user and relays through the ledger (E6.4) |

## 7. Definition of done (per epic)

- Requirements docs and ADRs updated first; INTERNALS/AUTHORING match.
- All tests green on 3.9 and 3.12; coverage ≥ 90%.
- Free-tier evals green in pre-commit; paid tier run locally for the release.
- Dogfooded: at least one ticket shipped through `/acs:ship` on this repo
  using the changed component.
- CHANGELOG entry with a breaking flag where applicable.
- Metrics from `/acs:usage` for the dogfood run recorded in the PR body
  (spawns, iterations, cost) for before/after comparison.

## 8. Effort estimate

| Epic | PRs | Sessions (rough) |
|---|---|---|
| E0 | 4–6 | 3 |
| E1 | 6–8 | 8 |
| E2 | 3 | 3 |
| E3 | 3–4 | 4 |
| E4 | 8–10 | 10 |
| E5 | 8–10 | 10 |
| E6 | 4 | 5 |
| E7 | 4 | 4 |
| E8 | 3 | 3 |
| Total | ≈ 45–50 | ≈ 50 |

## 9. Traceability: report finding → plan item

| Report section | Finding | Plan |
|---|---|---|
| 3.1 | effort unreachable; overrides enum; model ids pinned; validation gaps | E3.1–E3.3, E0.8, E0.9 |
| 3.2 | prompt size; ticket refs; verbatim clauses; Python-by-name; restatements; hand-holding; context prose; stale examples | E4.1–E4.6, E1.1, E1.6, E0.11 |
| 3.3 | duplication (doc family, protocol, grounding, gates, scanners, apportioners, forwarders) | E5.4, E4.1, E3.1, E1.2, E0.6 |
| 3.4 | triad where it does not earn its cost; no convergence | E5.2–E5.8, E5.3 |
| 3.5 | two hook events; post-hook goodwill; self-reported gates; fail-open dispatcher; dead code; attribution drift | E1.8, E1.3, E1.7, E0.6, E0.7, E0.10, E3.4, E0.12 |
| 3.6 | bugs 1–8 | E0.1–E0.8 |
| 3.7 | XML ritual and mirrors | E2.1–E2.4 |
| 3.8 | ship isolation premise; boundary; manual fan-out; dead prose | E6.1–E6.4, E4.4 |
| 3.9 | prose-pinning tests; conformance-only evals; paid suite inside verifier | E4.6, E7.1–E7.6 |
| 3.10 | weak-model compensations catalogue | E4.3, E5.9, E1.9, E5.1, E5.3 |
| 4 | Claude 5 register and platform features | E4.1 style guide, E1.8, E3.1, E6.5 |
| 5.9 | settings changes | E5.1, E5.10, E0.8 |
| 10 | open decisions | §3 decision gates |
