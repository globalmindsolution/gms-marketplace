# acs re-architecture for Claude Opus 5 / Sonnet 5 — findings and recommendations

Status: research report, 2026-09-02, against `main` at `e8dc309` (acs v0.4.8 +
Unreleased). Nothing in this document changes runtime behavior; it is the
input to the ADRs and tickets that would.

## 0. Summary

acs was designed for Opus 4.x / Sonnet 4.x and it shows: almost every
architectural decision in `docs/adr/` is explicitly a mitigation for a model
that forgets steps, rubber-stamps its own work, hallucinates facts,
self-estimates cost, or runs out of a 200K window. Those mitigations were
correct at the time. Against Opus 5 / Sonnet 5 they now cost more than they
return, and several have decayed into pure ceremony that the model performs
for the benefit of tests rather than the user.

The ten things that matter most:

1. **The `effort` half of the `models` settings block is unreachable.** acs
   forbids `model`/`effort` in agent frontmatter and tells the coordinator to
   "apply them at spawn". Claude Code supports subagent `effort`, but only
   as a frontmatter field; the per-invocation Agent parameter is `model`
   alone. So `effort: high` in every consumer's settings has never had an
   effect, and the "fail the run if the runtime rejects it" clause can only
   fire on `model`. Plugin agents also silently drop `hooks`, `mcpServers`,
   and `permissionMode`, which constrains how the fix can be shipped (§5.5).
2. **The prompts are the runtime, and they have become a changelog.** The
   `code` skill is 922 lines against the authoring guide's own 180–330
   budget; `setup` is 1003. The growth is almost entirely ticket-slice prose
   (MAR-56/57/71/72, D-1..D-4, AC-3/4, ADR 0069) baked into the live
   instruction stream. 136 ticket/ADR/AC identifiers appear inside
   skills and agents; no runtime reader can resolve any of them.
3. **The three-role triad is applied uniformly where it does not earn its
   cost.** For the four template-consumer doc skills the planner decides a
   file-exists test, the executor fills a 20–30 line template, and the
   verifier runs two scripts. That is 3 spawns, 6 XML round-trips, and
   ~1,000 lines of prompt per skill to produce ~100 lines of markdown that a
   human then reviews in the PR anyway.
4. **Duplication is the dominant cost.** The quality/principles/standards/
   operations skills are 62–78% identical text (≈3,200 lines carrying ≈300
   lines of distinct content). The 17-line Grounding block is pasted into 45
   agent files. The clarification-ledger paragraph is in 16 skills. A 40-line
   ADR-0012 block with the same JSON example is in 8 planners.
5. **The deterministic layer is thinner than INTERNALS claims.** Only two
   hook events are registered (PreToolUse on Skill, SessionEnd). All 15
   post-hooks are Bash calls the coordinator must remember to make. The
   fields that gate the pipeline (`verifier_passed`, coverage numbers, PR
   reference) are written by the coordinator into `result.json` and trusted
   verbatim. The dispatcher fails open on a hung gate.
6. **The XML message contract is small but the ceremony is large:** validate
   every message via Bash, persist every raw message, self-check before
   returning, four hand-synced skill-name enums, and an `xmllint` CI
   dependency, all to carry ~10 fields that already live in files on disk.
7. **`/acs:ship`'s isolation premise is false.** Steps run inline in ship's
   own context, so its "keep your context tiny" rule cannot hold, and the
   "full-verify pipeline boundary" (stop after `/code` on full-depth lanes)
   is a 200K-window workaround shipped as product behavior.
8. **Eight logic bugs** surfaced during the audit, independent of model
   choice (§3.6). Two of them make documented remediation paths
   unsatisfiable.
9. **78 of 145 test modules pin prose wording**, not behavior. That test
   debt, not the code, is the main cost of any rewrite. Evals assert
   conformance only; no eval can show that the triad or the 4-lens verifier
   earns its 4× spawn cost.
10. **What Claude 5 actually changes**, per Anthropic's published guidance:
    literal instruction following (state scope explicitly; stop shouting),
    self-verification without prompting (remove "re-verify" instructions or
    it over-verifies), eager delegation (add explicit spawn guardrails),
    strong `medium`/`low` effort tiers, and a 1M context. Plus Claude Code
    now offers `SubagentStop`/`Stop` hooks, LLM-evaluated hooks, agent-level
    `effort`/`hooks`/`maxTurns`, `context: fork` for skills, and a Workflow
    scripting tool. None of these existed when acs was designed.

Recommendation in one sentence: keep the deterministic kernel (gates, locks,
workspace state, clarify ledger, convention CI) and the verifier-independence
principle; collapse the prompt layer to a shared coordinator protocol plus
per-skill charters; scale the topology by lane instead of applying the triad
everywhere; replace XML-in-chat with JSON-on-disk captured by a `SubagentStop`
hook (the input `<task>` envelope keeps its XML tags; it is the return ritual
that goes); and make `Stop` enforce the post-hook so the pipeline stops
depending on coordinator goodwill. The work is tracked as acs tickets
(epics E0-E8 with their children); this document is their rationale.

## 1. Method and scope

Read in full: `docs/INTERNALS.md`, `docs/AUTHORING.md`, `skills/code/SKILL.md`,
`agents/code-*.md`, `hooks.json`, model resolution in `acs_lib.py` and
`skill-start.py`, `.acs/settings.json`, `settings.schema.json` models block.
Five parallel audits covered: hooks/scripts (57 files, 10,854 lines); the
eleven doc-bootstrap skills and their 30 agents; schemas, XSD, templates,
ADRs 0001–0086, evals, CI; the pipeline/utility skills (ship, create-ticket,
create-pr, merge-pr, docs-sync, test, setup, handoff, release, update,
install-hooks, metrics, usage); and current Claude Code / Claude 5
documentation. Every bug listed in §3.6 was re-verified against source after
the audits reported it.

## 2. The plugin today

| Layer | Size | Notes |
|---|---|---|
| Skills | 25 `SKILL.md`, 529 KB, ≈11,900 lines | 15 hooked, 10 unhooked; largest: setup 1003, code 922, create-ticket 564, create-pr 533 |
| Agents | 45 files, 423 KB | 15 skills × 3 roles; 6 orphaned (create-ticket/create-pr/merge-pr planner+verifier) since the MAR-60 inlining; `code-verifier` alone is 395 lines / 16 dimensions |
| Hooks/scripts | 57 Python files, 462 KB | `acs_lib.py` 2,702 lines; 30 pre/post forwarders of 10–16 lines each; only 2 hook events registered |
| Schemas | 10 JSON schemas + 184-line XSD | four hand-synced copies of the skill-name enum |
| Tests | 145 modules, 52,842 lines | 78 modules read `SKILL.md`/agent text; free-tier evals run in pre-commit and CI; paid tier is local-only |
| ADRs | 86 | the architectural ones are near-uniformly model-weakness mitigations (§9) |

Prompt-text emphasis inventory across skills + agents: `ONLY` ×166, `NEVER`
×105, `EVERY` ×64, `STOP` ×45, `MANDATORY` ×31, `MUST` ×24, `EXACTLY` ×16.

Growth since the repo import (2026-08-06, 50 commits): `code/SKILL.md` 718 →
922, `ship` 363 → 424, `code-verifier` 350 → 395, `setup` 0 → 1003. Every
`code/SKILL.md` commit in that window adds a numbered "slice" of prose.

## 3. Findings

### 3.1 Model and effort plumbing (P0)

- `docs/AUTHORING.md` (skill and agent frontmatter tables) forbids `model`
  and `effort` in frontmatter; `INTERNALS.md` §Subagents says agents carry
  `model: inherit` and the coordinator applies `context.models.<role>` at
  spawn. No agent file has any `model:` line (grep: 0 of 45).
- `skill-start.py:248-249` resolves `{model, effort}` per role into the
  context JSON. From there the only carrier is prose: "apply
  `context.models.<role>.model` / `.effort` at spawn when not `inherit`; if
  the runtime rejects the model or effort, FAIL the run"
  (`skills/code/SKILL.md:325-328` and twelve siblings).
- Per the Claude Code sub-agents reference (Supported frontmatter fields):
  `effort` is a subagent **frontmatter** field ("Effort level when this
  subagent is active. Overrides the session effort level. Default: inherits
  from session. Options: `low`, `medium`, `high`, `xhigh`, `max`"). The
  per-invocation Agent parameter is `model` only, resolved in the order
  per-invocation `model` → frontmatter `model` (`inherit` = main model) →
  `CLAUDE_CODE_SUBAGENT_MODEL` → main conversation model. There is no
  per-invocation effort channel. In this session's Agent tool schema the
  `model` parameter enumerates aliases only (`sonnet|opus|haiku|fable`); the
  docs say full ids such as `claude-opus-5` are accepted, so a runtime
  check on the consumer's CLI build is still worth doing.
- Consequence: `.acs/settings.json` `effort: high` ×3, and every consumer's
  effort setting, is dead configuration. `validate_models`
  (`acs_lib.py:1027-1050`) also never checks the effort enum, so a typo
  would pass silently; the PRD (`docs/product/prd.md:395`) already admits
  the runtime has no model-id or effort validation.
- `settings.schema.json:159` `models.overrides` enumerates 9 skills: it
  includes `ship` (no subagents; the `coordinator` role was retired in
  MAR-154) and omits 8 hooked skills that do spawn triads (create-quality/
  operations/principles/standards/requirements, docs-sync,
  standardize-project) plus `test`.
- Model ids are pinned in two tests (`tests/acs/test_settings_models_pinned.py:37-39`,
  `tests/acs/test_setup_offers.py:55,167`) byte-for-byte, so the next model
  generation forces a test edit rather than a settings edit.
- Also relevant from the docs: the built-in Explore agent's inherited model
  is capped at Opus on the Claude API; custom agents inherit the main
  model directly. Subagents inherit the main conversation's extended
  thinking setting; there is no per-subagent thinking control.
  `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` overrides every definition and
  invocation, so a consumer can pin all acs subagents to one model without
  touching settings.
- **Plugin subagents ignore `hooks`, `mcpServers`, and `permissionMode`
  frontmatter** (security rule; the fields are silently dropped). Any acs
  design that wants agent-scoped hooks must either register them in the
  plugin's `hooks.json` with a `SubagentStart`/`SubagentStop`/`PreToolUse`
  matcher, or have `/acs:setup` render project-level agents into
  `.claude/agents/`, which support every field and take precedence over
  plugin agents of the same name (scope priority: managed → `--agents` →
  project → user → plugin).
- Subagents can now spawn their own subagents by default (three layers).
  acs's "never spawn subagents" invariant is enforced today only by
  executors' `disallowedTools: Agent, Skill` and by the planner/verifier
  `tools` allowlists omitting `Agent`; keep those, drop the prose repeats.

### 3.2 Prompts as runtime: size, accretion, and weak-model idioms

- **Budget violations.** AUTHORING's own limits are 180–330 lines per skill
  and 60–140 per agent. 19 of 25 skills exceed 330; 20 agents exceed 140.
- **Design-history leakage.** Runtime prompts carry ticket lineage no reader
  can resolve: `MAR-72`, `D-1..D-4`, `AC-3/AC-4`, `ADR 0069`, `NFR-S4`,
  `profile #1` ×7 in `release`, `Child 3 / MAR-15` in `metrics`, "this ticket
  introduces none" in five skills, "This is the deliberate inversion of
  `create-principles/SKILL.md`'s Start guard" (`create-standards/SKILL.md:45-57`).
  `create-pr/SKILL.md:343-400` is a 58-line webhook troubleshooting essay.
- **Verbatim-clause tests disguised as rubric.** `plan_approval_eligible`
  (`acs_lib.py:509-515, 626-631`) requires two sentences to appear
  character-for-character in `plan.md` ("no separate /acs:create-spec
  invocation and no separate create-spec planner subagent"; "every
  ticket.acceptance_criteria entry maps to at least one test the folded
  plan will write"), plus a numeric token within 200 chars of the word
  "coverage" (`:533-547`). This tests whether the planner copied text, not
  whether it planned.
- **The coordinator is asked to call Python by name.** `code/SKILL.md`
  instructs the coordinator to invoke `derive_lane`, `guard_axes`,
  `escalate_lane`, `save_ticket`, `update_pipeline`, `update_index`,
  `record_escalation_event`, `recommend_stakes`, `confirm_deescalation` in a
  specified order with a 13-field event dict. There is no CLI for these; the
  model must write ad-hoc heredoc Python. `ship/SKILL.md:35-57,184-191` and
  `setup/SKILL.md:21-55` do the same. This directly violates ADR 0001's own
  rule ("'carefully update the JSON' in a SKILL.md is a bug, fixed by adding
  a helper script").
- **Quadruple restatement.** "Plan once / what an iteration counts / no
  lane" appears four times in `create-quality/SKILL.md` (`:100-103, 105-109,
  157-163, 186-189`) and again in its planner and executor. The BEHIND
  carve-out is specified three times in `merge-pr/SKILL.md` and twice more in
  its executor. "Your FINAL message is ONLY the `<result>`… NOTHING after
  it" appears in 30 agents, often twice per file.
- **Hand-holding trivial operations.** `setup/SKILL.md:344-415` spends four
  bash blocks adding one line to `.gitignore` and one to `info/exclude`;
  `update/SKILL.md:49-50` explains how to compare semver tuples;
  `handoff/SKILL.md:59` re-derives the checkout id that `acs_lib` already
  computes; `create-quality-verifier.md:40-68` spends 30 lines on invoking
  `citation_check.py`, cloned four times.
- **Context-window prose everywhere.** Every hooked skill has a `## Context
  pressure` section instructing the model to detect a low window and hand
  off; `create-docs/SKILL.md:329-337` reasons about context size for five
  small doc files; handoff summaries are capped at 1 KB; "reference by path,
  never inline" is restated per agent. All of this is 200K-window design.
- **Stale examples.** Verifier `stop-reason` examples say "across 5
  dimensions" where 8 exist (`create-quality-verifier.md:134`), "6" where 8
  (`create-principles-verifier.md:132`), "4 of 5" where 13
  (`create-requirements-verifier.md:160`). Every `result.json` example still
  shows `tokens`/`cost_usd` that INTERNALS marks as ignored since ADR 0082.
  `mmdc` is a permitted tool in `create-architecture-verifier.md:154` though
  `mermaid_lint.py` is the gate.

### 3.3 Duplication

| What | Where | Size |
|---|---|---|
| Four template-consumer skills are one skill instantiated four times | quality / principles / standards / operations SKILL.md + 12 agents | ≈3,185 lines, ≈300 distinct; `create-quality-planner` vs `create-operations-planner` differ in 36 of 157 lines |
| Coordinator protocol blocks (Start, Resume, loop mechanics, Delivery, Clarification ledger, Context pressure, Finish, Completion report) | every hooked SKILL.md | ≈120 lines × 15 skills |
| Grounding (anti-hallucination) block | 45 agents | 17 lines × 45 ≈ 765 lines |
| Input/Output contract + Hard rules boilerplate | 45 agents | ≈40 lines × 45 |
| ADR-0012 design-time doc-consistency block with the same JSON example | 8 planners | 40 lines × 8 |
| Mermaid pitfalls prose | architecture-executor, design-executor | duplicates `mermaid_lint.py` |
| Six identical `hld/tech-stack.md` existence gates | `acs_lib.py:2201-2209, 2340-2387` | one table entry each would do |
| Three heading scanners + one re-implementation | `_plan_headings`, `structure_lint._headings`, `citation_check._headings`, `plan_approval_eligible._scan` | |
| Three token-share apportioners | `cost_sampler.py:285-367` | |
| Two cost/duration folders | `compute_ticket_totals`, `_update_metrics_body` | |
| 30 pre/post forwarders | `hooks/scripts/pre-*.py`, `post-*.py` | each calls one `acs_lib` function |

### 3.4 Where the triad earns its cost, and where it does not

| Skill group | Current | Value of each role for a Claude 5 model |
|---|---|---|
| `code` STANDARD/COMPLEX | planner ×1, executors ×N, verifier ×1 (light) or ×4 lenses (full), ≤3 iterations | Planner: real (file map, parallelism decision, test strategy). Verifier independence: real. 4 parallel lenses + coordinator merge pass: unmeasured; ADR 0067 states the 4× cost, no eval measures the gain. |
| `code` TRIVIAL/SMALL | coordinator-authored plan, executor, verifier, cap 1 | Already single-pass; but the coordinator must still author a six-heading `plan.md` with two verbatim clauses for a one-line change. |
| prd / architecture / requirements / design | full triad | Reviewer earns its keep (traceability, HLD↔LLD consistency, strawman detection). Planner is foldable into the author. |
| quality / principles / standards / operations | full triad | None of the three roles makes a judgment a script cannot: planner = file-exists test + citation list; executor = fill template; verifier = `structure_lint` + `citation_check` + docs-only diff. `architecture-conformance` and `audience-style` are the only judgment dimensions. |
| docs-sync | full triad, cap 3 regardless of lane | The value is fresh-context re-derivation from the diff. The planner is a third full read of the same six inputs before an executor that must re-read them. Ignores `verify_depth`. |
| create-project / standardize-project | full triad | The verifier that actually runs build/lint/tests is the value. Planner foldable. |
| create-ticket / create-pr / merge-pr / release | inline + optional single executor | The optional executor shares no memory and must re-read every input; pure overhead. merge-pr readiness is a pure function of `gh pr view --json`. |

Loop mechanics: no convergence detection (the same finding three times still
burns three iterations), no partial credit, and "reflection" is a misnomer:
findings are forwarded verbatim to the executor.

### 3.5 Deterministic layer: what it actually enforces

- **Hook surface.** `hooks.json` registers `PreToolUse` (matcher `Skill`) and
  `SessionEnd` only. `dispatch.py pre` spawns `pre-<skill>.py` as a
  subprocess, which calls `acs_lib.run_pre`. No `PostToolUse`,
  `SubagentStop`, `Stop`, `SubagentStart`, or `UserPromptSubmit`.
- **Post-hooks are goodwill.** `post-<skill>.py` is a Bash command the
  coordinator is told to run as its "MANDATORY final step". The safety net
  is indirect (the next gate reads `runs[-1].status`). Nothing forces the
  post-hook at the moment the coordinator stops.
- **The pipeline gates on self-report.** `run_post` (`acs_lib.py:2597-2661`)
  trusts `states.verifier_passed`, `states.tests.coverage_percent`,
  `states.pr`, `review.iterations` verbatim from the coordinator-written
  `result.json`. Only tokens/cost are measured independently (ADR 0082). The
  create-pr gate therefore checks "did the model write `true`", not "did a
  verifier pass". `_read_result_from_argv` defaults `status` to `completed`
  when absent (`acs_lib.py:2544`).
- **Fail-open dispatcher.** `dispatch.py:64-71` sets `timeout=25` but never
  catches `subprocess.TimeoutExpired`; a hung gate raises, exits 1, and
  Claude Code treats exit 1 as non-blocking, so the skill proceeds.
- **Locks and writes.** `lock_is_stale` uses `os.kill(pid, 0)` + hostname,
  meaningless across containers; `_guarded_repo_write` and
  `allocate_ticket_id` fail open after 10 s of spinning.
- **Dead code.** `codex_adapter.py` (design refuted in
  `docs/architecture/lld/runtime-coupling-inventory.md`, kept alive only by
  5 trivial tests); `consistency_findings.py` (test-only); `PIPELINE_STEP_ORDER`;
  `backfill_distinct_pr_count`; `validate_batch`/`batch_overall_ok`;
  `create-spec` residue in `statusline.py:40`, `subagent-statusline.py:39`,
  `validate_xml.py:81`; the `<metrics>` branch in `validate_xml.py:212-224`;
  six orphaned agent files; six executor "Delivery" steps that the SKILL.md
  never assigns.
- **Attribution drift.** `subagent-statusline.py:37-40` recognizes 9 of 15
  skills; usage attribution depends on `-planner/-executor/-verifier` name
  suffixes; cost sampling depends on five undocumented Claude Code
  internals (hook envelope fields, transcript JSONL shape with a
  fractional-second-intolerant timestamp parser, `attributionSkill`/
  `attributionAgent` fields, subagent transcript directory layout,
  statusLine payload keys) and on the user opting into a statusLine.

### 3.6 Logic bugs (verified against source)

| # | Bug | Evidence |
|---|---|---|
| 1 | `/acs:ship` resume of an incomplete `create-ticket` mints a new ticket: ship passes the ticket id as args, but create-ticket's Start always passes `--allocate`, and `skill-start.py` allocates unconditionally when the flag is set | `skills/ship/SKILL.md:285`; `skills/create-ticket/SKILL.md:30`; `hooks/scripts/skill-start.py:158-163` |
| 2 | `steps.test.fix_loops` has no writer: ship says `update_pipeline` "already writes an arbitrary-shape step dict"; its signature is `(tdir, ticket_id, skill, status, summary=None, flow=None, lane=None)` | `skills/ship/SKILL.md:125-129`; `acs_lib.py:1706` |
| 3 | `gate_docs_sync`'s remedy "run `/acs:test --for-ticket X` first" cannot open the gate: `/acs:test` never writes `pipeline-state.json`; only ship does. Once ship records `steps.test = failed` at cap, `fix_loops` is never reset, so resume dead-ends | `acs_lib.py:2264-2269`; `skills/test/SKILL.md` (no ledger write); `skills/ship/SKILL.md:150-153, 240-242` |
| 4 | `templates/CLAUDE.acs.md:24` (injected into every consumer's `CLAUDE.md`, and this repo's) describes the pipeline as `create-ticket → create-spec → code → create-pr`; `create-spec` was deleted in 0.4.6 and `docs-sync`/`test` are omitted | `templates/CLAUDE.acs.md:24`; root `CLAUDE.md` |
| 5 | merge-pr requires `reviewDecision == APPROVED` on every invocation while setup configures branch protection with `required_approving_review_count: 0`; a solo maintainer can never merge through the skill | `skills/merge-pr/SKILL.md:241-246`; `skills/setup/SKILL.md:714` |
| 6 | Dispatcher fails open on gate timeout | `hooks/scripts/dispatch.py:64-71` |
| 7 | Running `post-<skill>.py` with an empty result marks the run `completed` | `acs_lib.py:2544` |
| 8 | Effort setting unreachable (§3.1); `models.overrides` enum stale | `settings.schema.json:159`; `AUTHORING.md` frontmatter rules |

Smaller inconsistencies worth fixing in the same pass: create-pr maps a
`needs_input` handoff to `result.json` status `failed` while ship treats it as
`needs_input`; `states.<set>.files` has three shapes across the doc family;
the execute-report JSON has four schemas; `dimension` tokens mix kebab and
Title case; constraint names split between `coverage-target` and
`coverage-threshold`; branch creation has three recipes; completion-report
label substitutions (`Scope`/`Run`/`Ticket`) are inconsistent with
INTERNALS; README says merge-pr is "user-invoked only" while the skill is
agent-invocable (ADR 0028).

### 3.7 The XML message contract

The XSD is compact (three roots, ~10 fields). The protocol around it is
what costs: the coordinator validates every message it sends and receives via
a Bash pipe, re-requests once, persists every raw message to
`iter-<n>-<phase>.xml`, and each subagent self-checks via `echo … |
validate_xml.py -` before returning. The skill-name enum is hand-mirrored in
the XSD, two JSON schemas, and `validate_xml.SKILLS`; `ALLOWED_ATTRS`/
`TEXT_LEAVES`/`CHILD_ORDER` mirror the XSD again. `xmllint` is a CI and
optional consumer dependency.

Two observations:

- The XML is a second, lossy channel for data that already lives on disk:
  ADR 0005 itself says results "carry file references, never artifact
  bodies". The `<finding>` list summarizes `iter-<n>-verify.md`.
- From v0.4.0 to v0.4.7 the XSD `skillName` enum listed 9 skills while up to
  24 shipped (`CHANGELOG.md:77`). Had subagents actually run the mandated
  validation, every task for the other 15 skills would have failed. This is
  circumstantial evidence that the validation step is skipped in practice,
  which would mean the ceremony costs tokens without buying enforcement.

### 3.8 `/acs:ship`

Ship invokes each step with the Skill tool and then *is* the step's
coordinator in the same context. Consequences:

- "Never read step transcripts, phase XML files, specs, or diffs"
  (`ship/SKILL.md:21-29`) cannot hold; everything the step reads is in
  ship's context.
- The "Full-verify pipeline boundary" (`:167-217`) hard-stops the pipeline
  after `/code` on full-depth lanes because the window is presumed
  exhausted. With isolated step execution or a 1M window it is dead weight,
  and it contradicts "one command end-to-end".
- Epic flow requires the user to run `--fan-out` manually and pick children;
  children run sequentially (`:353-376`).
- Dead prose: a "model note" about a retired coordinator role (`:72-77`);
  instructions to validate `<task>` XML ship never composes (`:300-312`);
  "rendered only AFTER the post-hook succeeded" for a skill with no
  post-hook (`:407-412`); `iterations <n>/3` in a completion report for a
  non-iterating skill.

### 3.9 Tests and evals

- 78 of 145 test modules read `SKILL.md`/agent text and regex-pin wording
  ("topology", "reference sweep", "registry" tests; `test_skill_contracts.py`
  alone is 3,846 lines). They pin phrasing, not behavior, and will break on
  any rewrite before a single behavior changes.
- Evals (8 scenarios) assert conformance: state files, gate transitions,
  first-Skill routing, PR facts. Nothing measures code quality, verifier
  false-negative rate, iterations-to-pass, cost, or wall time. There is no
  `--model` knob in `Sandbox.run_skill`, so Opus 5 vs Sonnet 5, or triad vs
  single-agent, cannot be compared. s04 asserts the *first* Skill call, which
  a stronger model may reasonably choose differently.
- The dogfood `.acs/settings.json` sets `e2e.command` to the **paid** eval
  suite, so the Opus verifier launches paid `claude -p` sessions from inside
  a verify iteration.

### 3.10 Weak-model compensations, catalogued

These are the mechanisms whose justification was a 4.x-era failure mode.
Each is a candidate to remove, demote to advisory, or move into a script.

| Mechanism | Original failure mode | Claude 5 status |
|---|---|---|
| XML envelope + validate on every hop (ADR 0005) | malformed returns | Structured returns are reliable; JSON file on disk + script validation is strictly simpler |
| Grounding block ×45, "never assert what you did not observe" | hallucinated facts | Keep once, in the role base prompt; verifiers still police citations |
| Verbatim clauses in `plan_approval_eligible` | planner skipped the fold contract | Replace with section presence + AC↔test mapping check |
| 4-lens verifier + coordinator merge (ADR 0067) | single verifier missed blind spots | Unmeasured; make it COMPLEX-lane-only or measure first |
| Lane escalation state machine (`guard_axes`, `escalate_lane`, 13-field event, upward-only invariant) | model de-scoped itself | Keep `derive_lane`/`verify_depth`; make escalation a one-line CLI (`acs lane escalate --to high --trigger …`) or advisory |
| Iteration caps 1/3 (ADR 0034) | loop burned 12–20 windows on a one-liner | Keep, but add "same finding twice → stop and ask" |
| "Re-run every cheap check yourself, trust nothing recorded" | executor lied about green | Opus 5 self-verifies without prompting; the docs warn that extra verify instructions cause over-verification. Keep re-run of tests/coverage (cheap, deterministic); drop the surrounding exhortation |
| `## Context pressure` per skill; 1 KB handoff cap; "never inline bodies" | 200K window | Keep handoff as a mechanism in INTERNALS; delete per-skill sections |
| Full-verify boundary in ship | 200K window | Delete |
| Clarify ledger with mandatory rationale | silent assumptions | Keep; it is a product feature, not a crutch |
| Self-estimated tokens/cost in result.json | 500× under-reporting | Already ignored; delete from prompts |
| "NEVER spawn subagents" ×39 | runaway delegation | Still needed, once per role, phrased as scope: Claude 5 docs say Opus 5 delegates *more* readily |
| ALL-CAPS imperatives | instruction slippage | Docs: Claude 5 follows softer phrasing; aggressive language causes over-compliance and over-scoping |

## 4. What Claude 5 changes, and what it does not

From Anthropic's Opus 5 / Sonnet 5 / Fable 5.1 prompting pages and the
Claude Code docs (all referenced in §11):

- **More literal instruction following.** Say what to do and at what
  scope. "Deliver what was asked, at the scope intended" replaces walls of
  `NEVER`. Aggressive phrasing now over-steers.
- **Self-verification is default.** Opus 5 verifies its own work
  unprompted; explicit "re-verify everything" instructions produce
  over-verification. The verifier role's independence still matters (a
  different context judging fresh); its exhortations do not.
- **Eager delegation.** Opus 5 spawns subagents more readily; the guardrail
  "delegate only large, independent, parallelizable work" is now *more*
  important, but should be stated once as a scope rule.
- **Effort tiers.** `medium` on Sonnet 5 ≈ Sonnet 4.6 `high`; Opus 5
  `low`/`medium` are strong. Executors on `medium` and doc-template work on
  `low` are defensible defaults. Fable 5.1 adds `xhigh`/`max`.
- **1M context.** Instruction following stays consistent across the window.
  Context-pressure prose and the ship boundary lose their rationale;
  hand-off remains useful for *session* continuity, not window exhaustion.
- **Adaptive thinking on by default;** `budget_tokens` and sampling params
  are gone (400 errors). Nothing in acs sets them; nothing to do.

Claude Code platform features acs does not use yet:

- Subagent frontmatter: `effort`, `hooks` (PreToolUse/PostToolUse/Stop
  scoped to the agent), `maxTurns`, `skills` (preload), `memory`,
  `background`, `isolation: worktree`, `permissionMode`.
- Hook events: `SubagentStart`/`SubagentStop` (capture and validate a
  subagent's output deterministically), `Stop` (can block the coordinator
  from ending its turn with `decision: block`), `PostToolUse`,
  `PreCompact`/`PostCompact`, `TaskCompleted`, `UserPromptSubmit`.
- Hook types: `type: prompt` (single-turn LLM judgment, cheap) and
  `type: agent` (multi-turn) for rubric checks that need judgment but not a
  full verifier context.
- Skills: `context: fork` (run a skill in a forked context), `references/`
  progressive disclosure, plugin-level `settings.json`.
- Orchestration: the Workflow tool (`agent()`, `parallel()`, `pipeline()`)
  for scripted fan-out; `TaskCreate`/`TaskList`; agent teams (experimental).
- Plugin evals (`claude plugin eval`, early access) with `llm` graders and
  baseline comparison; `/skill-doctor` context-cost reports.

What does **not** change: the model still cannot guarantee idempotent state
writes, ordering, or locking. ADR 0001's two-layer split is more right than
ever; the fix is to move *more* into the deterministic layer, not less.

## 5. Target architecture

### 5.1 Principles

1. **Scripts decide, models judge.** Anything with a correct answer (gating,
   ids, state writes, lane math, PR readiness, project-field fills, tracker
   sync, result derivation) is a CLI subcommand. No SKILL.md ever names a
   Python function.
2. **One protocol, many charters.** The coordinator protocol (start, resume,
   loop, finish) is written once. Each skill contributes inputs, outputs,
   and its judgment rubric.
3. **Topology scales with lane.** The triad is the COMPLEX-lane shape, not
   the default.
4. **Independence over exhortation.** A verifier's value is a fresh context
   with different inputs; it does not need to be told 16 times not to trust
   the executor.
5. **Enforce at the platform boundary.** Use `SubagentStop` and `Stop` hooks
   so the pipeline's integrity does not depend on the coordinator
   remembering a Bash command.
6. **Prompts describe current behavior only.** Design history lives in
   ADRs and the CHANGELOG; a ticket id in a prompt is a bug.

### 5.2 Topology by lane (for `/acs:code`; other skills map onto rows)

| Lane | Plan | Execute | Verify | Cap |
|---|---|---|---|---|
| TRIVIAL | coordinator, short `plan.md` (AC↔test map + file list; no fold clauses) | 1 executor (Sonnet 5, `medium`) | deterministic only: tests + coverage + lint + `structure_lint` run by the coordinator, plus one `type: prompt` hook rubric pass on the diff | 1 |
| SMALL | coordinator | 1 executor | 1 verifier (Opus 5, `medium`), all dimensions | 1 |
| STANDARD | 1 planner (Opus 5, `high`) | N executors, parallel when file maps are disjoint | 1 verifier (Opus 5, `high`) | 2 |
| COMPLEX / high stakes | 1 planner | N executors | 2 lenses (A: correctness+tests+AC; B: architecture+security+standards+docs) merged by the coordinator; git-history lens only when the diff touches previously reverted paths | 3 |

Add a convergence rule on every lane above TRIVIAL: if iteration *k*'s
findings are substantively the same as iteration *k-1*'s, stop and surface
them instead of spending the cap.

Doc skills: prd / architecture / requirements / design → **author +
reviewer** (no planner; the author writes `plan.md` inline as its first
artifact). quality / principles / standards / operations → **one
parametrized skill** (`create-docset <set>`), coordinator-authored, gated by
`structure_lint`, `citation_check`, and docs-only-diff, with one optional
reviewer pass for stack conformance. docs-sync → single fresh-context
executor; reviewer only on `full` depth. create-ticket / create-pr /
merge-pr / release → inline, no executor; deterministic parts in CLIs.

### 5.3 Kernel additions (Python)

- `acs.py` single entry point with subcommands replacing the 30 forwarders
  and the heredoc sites: `gate <skill>`, `start <skill> …`, `finish <skill>
  --result-file`, `lane derive|escalate|deescalate`, `stakes recommend`,
  `plan check` (section presence + AC↔test mapping, replacing verbatim
  clauses), `phase validate <file>`, `readiness <pr>` (merge-pr), `pr
  metadata fill` (create-pr 6a), `tracker sync` (create-ticket step 5),
  `setup wizard` (drive the questionnaire; model handles conversation
  only), `context` (what `handoff`/`ship` re-derive in prose today).
- `finish` **derives** `result.json` from artifacts instead of trusting the
  coordinator: `verifier_passed` from the verifier's own `verdict.json`
  (written by the verifier subagent and captured by the `SubagentStop`
  hook), coverage/tests from the recorded command output, `pr` from `gh pr
  view`. Refuse an empty result; never default `status` to `completed`.
- `dispatch.py`: catch `TimeoutExpired` → exit 2; call gates in-process.
- Split `acs_lib.py` into `settings`, `repo`, `state`, `gates`, `lanes`,
  `setup_helpers`, `metrics`; keep a facade for compatibility during
  migration.
- Table-drive the six architecture-doc gates; unify the heading scanners on
  `structure_lint`; collapse the three apportioners.
- Isolate the five undocumented Claude Code interfaces used by cost
  sampling into one adapter module with a single degradation switch; record
  `claude --version` with samples.

### 5.4 Hook plan

| Event | Matcher | Purpose |
|---|---|---|
| `PreToolUse` | `Skill` | gates, as today (in-process) |
| `SubagentStop` | `^acs:` (plugin-scoped names contain `:` and are matched as an unanchored regex, so anchor it) | run `acs phase validate` on the agent's `iter-<n>-<phase>.json`; write the snapshot the coordinator writes by hand today; for verifiers, capture `verdict.json`. Plugin `hooks.json` hooks fire inside subagents, so this needs no agent-level frontmatter |
| `Stop` | — | if `runs[-1].status == in_progress` for this checkout and no `result.json` exists → `decision: block` with "run the finish step"; this closes the post-hook goodwill gap |
| `SessionEnd` | — | as today |
| `PreCompact` | — | flush `handoff-context.md` automatically instead of asking the model to notice context pressure |
| `PreToolUse` | `Edit\|Write\|NotebookEdit` while an `acs:*-executor` is active | deny writes outside the task's file map (the executor's "STOP and return needs_input" rule, enforced). Registered in plugin `hooks.json`, since plugin agents cannot carry frontmatter hooks; the active agent is known from the `SubagentStart` payload's `agent_type` |
| optional `type: prompt` hook on `SubagentStop` for executors | | cheap rubric pass (simplicity, scope, comment policy) instead of a full verifier on TRIVIAL |

### 5.5 Agent definitions

Three viable shapes. The recommendation is A for the plugin's shipped
defaults, with C as the consumer-side override path that finally makes
`effort` configurable.

**A. Three role agents + charters by reference (recommended default).**
`agents/planner.md`, `executor.md`, `verifier.md` (invoked as
`acs:planner` etc.). Frontmatter carries `effort` defaults (planner/verifier
`high`, executor `medium`), `tools`/`disallowedTools`, and `maxTurns`. The
body is the role base (I/O contract, grounding, hard rules — once). The task
prompt names the skill charter file
(`skills/<skill>/references/charter-<role>.md`) the agent reads first. 45
files → 3 + ~30 short charters; the per-skill charter is preserved. `model`
is passed per call from `context.models`.

**B. Generated per-skill agents (conservative).** Keep 45 files but render
them from `agents/_roles/<role>.md` + `skills/<skill>/charters/<role>.md`
with a build script; CI asserts rendered == committed. Removes source
duplication, keeps the runtime shape identical.

**C. Setup-rendered project agents (the effort/hook escape hatch).**
`/acs:setup` renders `.claude/agents/acs-<role>.md` into the consumer repo
from the plugin's role templates, filling `model` and `effort` from
`settings.models` and adding the agent-scoped hooks plugin agents cannot
carry (`PreToolUse` file-map guard, `Stop` → `SubagentStop` capture). The
coordinator spawns `acs-<role>` when the project file exists, else the
plugin default. Project agents take precedence over plugin agents, support
every frontmatter field, and are re-rendered by `/acs:update`'s migration
step when the templates change. Frontmatter hooks in project agents require
the folder to be trusted; document that in setup.

Either way: delete the "fail the run if the runtime rejects effort" clause;
effort can no longer be rejected at spawn because it is never passed there.
Use `SendMessage` to resume a verifier for a follow-up question instead of
re-spawning it (resumed subagents keep their context and their per-call
`model`). Consider `experimental.cacheTtl: 1h` on the verifier for long
full-depth reviews.

### 5.6 Skill files

- `skills/_shared/coordinator-protocol.md` (Start, Resume & reconcile, loop
  mechanics, clarification ledger, finish, completion report) — loaded by
  reference from each skill's `references/`.
- Each hooked `SKILL.md` ≤ 150 lines: purpose, inputs, outputs (`states`
  keys), lane/topology table, skill-specific judgment rules, next step.
- Progressive disclosure for the big four: setup integrations (7b–7f) →
  `references/`; create-pr metadata fill + troubleshooting → CLI +
  `references/`; create-ticket fan-out/split modes → `references/`; merge-pr
  exempt path folded into the main path with a flag.
- Strip every ticket/ADR/AC/D-n identifier and every "this ticket
  introduces none" from prompts; move the rationale to ADRs.
- Prompt style for Claude 5: state scope positively ("Change only files in
  the task's file map; if another file is needed, return `needs_input`
  naming it"), one statement per rule, no caps, no restatements; add the
  delegation guardrail once per role; remove "re-verify everything"
  exhortations but keep the concrete re-run commands.

### 5.7 Messages

The cost is the ritual and the return channel, not the tag syntax. Three
separable pieces: (1) the `<task>` input envelope — keep it, XML tags are
the recommended way to delimit prompt sections, and render it from a script
so attributes come from context; (2) the model-side validation ritual and
the four enum mirrors — remove unconditionally, validation moves to a
`SubagentStop` hook; (3) the `<result>` return format — default to a JSON
pointer, but keeping the XML element as the return *format* is acceptable if
a structured verdict in the transcript is valued, provided (2) still goes.

Default shape: each phase writes
`iter-<n>-<phase>.json` (one JSON schema, stamped with skill/phase/ticket/
iteration by the `SubagentStop` hook from context, not by the model) and
returns a one-line pointer. Delete `validate_xml.py`, the XSD, the three enum
mirrors, the `.xml` snapshots, and `xmllint` from CI and settings. `<handoff>`
becomes `handoff.json` under the same schema. Supersede ADR 0005; amend
`docs/requirements/functional/reflection.md:239-252` and
`docs/architecture/lld/contracts.md:6-25`.

### 5.8 `/acs:ship`

Make ship a thin driver over a Python state machine (`acs pipeline next
<ticket>` returns the next step or the reason it is blocked) that spawns each
step as an isolated Agent (or, later, a Workflow script). Delete the
full-verify boundary and the post-code test `fix_loops` prose (fix bugs 1–3 in
the same change). Automate epic fan-out and child dispatch under ship;
children with disjoint file maps run in parallel. Keep the stop-before-merge
rule.

### 5.9 Settings

- `models`: keep per-role `{model, effort}` but document that `effort` is
  applied via agent frontmatter defaults / project override, not per spawn;
  validate the effort enum and override skill names in `validate_models`;
  derive `overrides.propertyNames` from `HOOKED_SKILLS`.
- New: `reflection.max_iterations` per lane (defaults 1/1/2/3),
  `reflection.lenses` (`1|2|4`, default 2 on COMPLEX), `autonomy`
  (`confirm|recommend|auto`) controlling whether create-ticket's seven
  confirmations and the due-date question are asked or defaulted.
- Unpin model ids from tests; read the recommended defaults from one
  constant.

## 6. Keep

These decisions are right and should survive intact:

- Two-layer split and the workspace-backed state machine (ADR 0001, 0008,
  0030): gates over recorded state, ticket-level flags, deterministic
  lanes, locks, resumability.
- Verifier independence as a *principle* (ADR 0004's core), and "the
  verifier is the review".
- The clarification ledger and assumptions-as-visible-debt (ADR 0009).
- Measured (not self-reported) tokens and cost (ADR 0082).
- Convention CI (`check-conventions.py`), `acs-exempt` path, and the
  managed `CLAUDE.md` block.
- Living architecture / living requirements induction; docs as part of the
  changeset.
- Ticket sizing rubric and split-as-a-question (ADR 0037–0039, 0069).
- Plan-once, execute→verify loops (ADR 0077–0084).
- `structure_lint`, `citation_check`, `mermaid_lint` as deterministic floors.

## 7. Consolidated remove / refactor / add list

**Remove**
- `codex_adapter.py` + test; `consistency_findings.py`; `PIPELINE_STEP_ORDER`;
  `backfill_distinct_pr_count`; `validate_batch`; `create-spec` residue;
  `<metrics>` branch in `validate_xml.py`.
- Six orphaned agent files; the optional executor in create-ticket /
  create-pr / merge-pr / release; six executor "Delivery" steps.
- `create-docs` (becomes `create-docset --all`).
- XML protocol, XSD, `validate_xml.py`, `xmllint` dependency (after §5.7).
- Full-verify pipeline boundary; per-skill `## Context pressure` sections;
  `tokens`/`cost_usd` in result examples; `iterations <n>/3` on
  non-iterating skills.
- Verbatim-clause and coverage-proximity checks in `plan_approval_eligible`.
- All ticket/ADR/AC/D-n identifiers and authoring meta-commentary from
  prompts.
- 30 pre/post forwarders (after `acs.py`).

**Refactor**
- quality/principles/standards/operations → one data-driven skill.
- standardize-project → `create-project --mode brownfield` with mode-gated
  verifier dimensions (or keep separate but share the machinery).
- docs-sync → executor + lane-gated reviewer.
- code verifier → dimensions grouped into two lenses; 16 → ~10 dimensions
  by merging `required-sections`+`structure`, `features`+`acceptance-criteria`,
  and demoting `audience-style` to `info`.
- Coordinator protocol → shared reference; skills ≤150 lines.
- Agents → 3 role agents + charters (or generated).
- `acs_lib.py` → package; gates table-driven.
- `merge-pr` approvals rule → defer to repo protection, require APPROVED only
  when protection requires reviews or when invoked by an agent (ship).
- create-ticket confirmations → one summary with defaults + `autonomy`.
- Unify `states.<set>.files`, execute-report schema, `dimension` casing,
  constraint names, branch recipe, completion-report substitutions, status
  vocabulary (add `needs_input` to `result.json`).
- Tests: convert prose-pinning modules to structural checks (section
  presence via `structure_lint`, JSON I/O contracts of `acs.py`).

**Add**
- `acs.py` CLI (§5.3); `SubagentStop`/`Stop`/`PreCompact` hooks (§5.4);
  verifier `verdict.json`; derived `result.json`.
- Convergence detection in the loop.
- `reflection.*` and `autonomy` settings.
- Eval knobs: `--model`/settings override in `Sandbox.run_skill`; a JSON
  baseline (iterations, findings, cost, wall time); a verifier-accuracy
  scenario (seeded defect must block; clean run must pass); relax s04 to a
  sanctioned first-skill set. Consider `claude plugin eval` with `llm`
  graders once available.
- Agent-level `PostToolUse` hook enforcing the executor file map.
- Automatic epic fan-out under ship.

## 8. Migration plan

Ordered so each phase ships alone and the pipeline stays green.

| Phase | Scope | Risk | Rough size |
|---|---|---|---|
| 0. Bug fixes | §3.6 items 1–7; stale template/README/schema enum; unpin model ids in tests | low | 1 PR |
| 1. Kernel | `acs.py` subcommands; in-process gates; timeout fail-closed; derived `result.json` + verifier `verdict.json`; `SubagentStop`/`Stop`/`PreCompact` hooks; split `acs_lib` | medium (state-file compatibility) | 3–4 PRs |
| 2. Messages | JSON phase results; delete XML stack; supersede ADR 0005 | medium (every skill touched, mechanically) | 2 PRs |
| 3. Prompt collapse | shared protocol; 3 role agents + charters; strip history; rewrite in Claude 5 register; convert prose tests | high in volume, low in behavior change | 4–6 PRs, one per skill group |
| 4. Topology | lane-scaled triad; convergence rule; 2-lens verifier; doc family → `create-docset`; docs-sync single executor; drop optional executors | medium; needs eval baseline first | 3 PRs |
| 5. Ship | Python pipeline driver; isolated step agents; automatic fan-out; delete boundary | medium | 2 PRs |
| 6. Measure | eval knobs + baseline + verifier-accuracy scenario; run Opus 5 / Sonnet 5 matrix; decide 4-lens fate on data | low | 1–2 PRs |

Phase 6's baseline should be captured *before* Phase 4 so the topology change
is measured, not asserted.

## 9. ADRs to supersede or amend

| Move | ADRs |
|---|---|
| JSON phase results | supersede 0005; amend 0069 ("no new XML element"), 0074 D-4, 0082 §5 |
| Lane-scaled topology, 2 lenses, author+reviewer for docs | supersede 0004 and its amendment chain (0073, 0077, 0078, 0079, 0083, 0084), 0067, 0074, 0076 |
| Iteration caps / convergence | amend 0034, 0042 |
| Models/effort | amend 0082 P4 note; requirements `configuration.md:122-150, 195-197`; `prd.md:187, 395`; `roadmap.md:268` |
| Evals with model knobs / LLM graders | amend 0022 |
| Keep and cite as the argument for the kernel move | 0001, 0008, 0009, 0030, 0086 |

## 10. Open decisions for the maintainer

1. Agent shape A (3 role agents + charters) vs B (generated per-skill
   agents), and whether to ship C (setup-rendered project agents) in the
   same release or later. A is smallest; B is zero-risk at runtime; C is
   the only path that honors a consumer's `effort` setting.
2. Whether `effort` should remain a consumer setting at all if C is not
   adopted, given plugin agents can only carry a fixed frontmatter default.
3. Keep the 4-lens verifier for COMPLEX until measured, or cut to 2 now.
4. Whether plan approval (`plan-approval.py`, dimensions 15/16) becomes a
   real gate or is deleted; today it is "recorded, not gated" yet drives
   two blocking verifier dimensions.
5. Whether the dogfood repo should keep running the paid eval suite as its
   `e2e.command` inside verifier iterations.
6. Merge-pr approvals: defer to branch protection, or keep the
   require-APPROVED-for-all rule and change setup to require one review.

## 11. Sources

Repository: `plugins/acs/docs/INTERNALS.md`, `docs/AUTHORING.md`,
`skills/*/SKILL.md`, `agents/*.md`, `hooks/hooks.json`,
`hooks/scripts/*.py`, `schemas/*`, `templates/*`, `docs/adr/*`,
`docs/requirements/functional/*`, `evals/acs/*`, `tests/acs/*`,
`.github/workflows/*`, `.acs/settings.json`.

Claude Code / Claude documentation consulted (2026-09-02):
sub-agents (`code.claude.com/docs/en/sub-agents`), skills
(`/skills`), hooks (`/hooks-guide`), plugins (`/plugins`), workflows
(`/workflows`), agent teams (`/agent-teams`); prompting guides for Claude
Opus 5, Claude Sonnet 5, Claude Fable 5.1 and the general Claude prompting
best practices (`platform.claude.com/docs/en/build-with-claude/prompt-engineering/…`);
structured outputs (`…/structured-outputs`). One item could not be verified
from docs and is flagged above: whether the Agent tool accepts full model
ids in this CLI build (this session's schema enumerates aliases; the docs
say full ids work). Project-over-plugin precedence, the plugin-agent
frontmatter restrictions, and the `effort` frontmatter contract were
confirmed from the sub-agents reference.
