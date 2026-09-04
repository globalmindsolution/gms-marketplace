# Changelog

All notable changes to the `acs` plugin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are automated: run **`/acs:release <version>`** to perform the five
steps below in one command — bump `version` in BOTH
`.claude-plugin/marketplace.json` and `plugins/acs/.claude-plugin/plugin.json`
to the same value, point the acs `source.ref` in `marketplace.json` at
`v<version>`, add a matching section here, and merge to `main` — the Release
workflow tags `v<version>` and publishes a GitHub release using that section as
the notes.

## [Unreleased]

- **The five undocumented Claude Code interfaces measurement rests on are isolated behind one adapter** (MAR-520, completing epic MAR-500/E0). Hook-envelope fields, the transcript JSONL record shape, `attributionSkill`/`attributionAgent`, the subagent transcript directory layout, and the statusLine payload keys were spelled out independently in `usage_reader.py`, `cost_sampler.py`, `acs_lib.py`, `statusline.py` and `subagent-statusline.py`; an upstream rename therefore broke measurement in five places, each degrading its own way. They now live once in `claude_code_adapter.py`, whose accessors are **total** — a malformed, absent, or wrong-typed value yields `None` or a documented default, never an exception, so callers measure instead of validating Claude Code's output. Degradation goes through a **single switch**, `unavailable(reason)`, which logs the reason (JSONL to `$ACS_DEGRADATION_LOG`, rotated at 256 KiB; stderr only under `$ACS_DEBUG`, so a status line stays quiet) and returns it — every `"unavailable"` in a metrics artifact now traces to one call site. Each cost sample additionally records **`claude_version`** (cached with a 24-hour TTL beside the sample log, probe bounded and failure-tolerant), so a future payload-shape change can be dated against the build that introduced it. `tests/acs/test_claude_code_adapter.py` pins the eight distinctive interface literals as adapter-exclusive by AST inspection, so the drift cannot silently return; ADR 0082 carries an append-only amendment. **Migration:** none — no settings key, schema, state-file shape, or artifact rename. One visible behavior change: a `statusLine` payload that is valid JSON but not an object now renders the ordinary fallback line (model + cwd basename) instead of `statusline.main`'s last-ditch `Claude` literal, which still stands for anything that genuinely raises.

- **`acs.py` is the single deterministic entry point** (MAR-521, first child of epic MAR-501/E1). ADR 0001's rule is that a skill reaches Python through a CLI; the SKILL.md files broke it in one direction — they named `acs_lib` functions (`derive_lane`, `guard_axes`, `escalate_lane`, `save_ticket`, `update_pipeline`, `update_index`, `record_escalation_event`, `recommend_stakes`, `confirm_deescalation`) with no command to reach them, so a coordinator improvised heredoc Python. Each is now a subcommand that takes flags and prints one JSON object: `context`, `gate`, `lane derive|rank|escalate|apply|deescalate`, `stakes recommend|guard`, `ticket show|save`, `phase validate`, `slug`, `fanout batches`, `doctor`. **The persistence sequence is one command, not four.** `lane apply` performs guard → escalate → `save_ticket` → `update_pipeline` → `update_index` → `record_escalation_event` in exactly that order, so a caller cannot half-perform it; when the audit write fails the axes are already durable and the command says so and exits 2, which is the detectable state the ordering exists to produce. `ticket save` refuses to move `size`, `stakes` or `lane` — those go through `lane apply` / `lane deescalate`, which carry the guard and the event. `start`, `finish` and `plan check` forward argv to `skill-start.py`, `pipeline-step.py` and `plan-approval.py`, which stay the implementation and stay callable directly, so no behaviour was reimplemented and none could drift. **Migration:** none — every existing script, flag and exit code is unchanged; `acs.py` is an addition.

- **`acs_lib` is a package, and its duplicated logic is table-driven** (MAR-522, second child of epic MAR-501/E1). The 2,989-line god-module carried settings, git, locking, the state ledger, gates, the post-hook, lane math, CLAUDE.md templating, PR classification, toolchain probing and fan-out; it is now eight domain modules behind a facade — `_common`, `settings`, `repo`, `lanes`, `state`, `metrics`, `setup_helpers`, `gates` — each under 600 lines. `import acs_lib as lib` still resolves **all 197** names it did before, verified by diffing the module surface against the pre-split original. The duplication went with it: six gates requiring `hld/tech-stack.md` (three copies of the body, four one-line functions) are one `_require_architecture_doc_set` plus an `ARCHITECTURE_DEPENDENT_SKILLS` table; three identical markdown heading scanners are one `markdown_headings.py`, which imports `re` and nothing else so the dependency-light CLIs and the pure plan-approval predicate can share it without taking on the kernel; the three token apportioners are one `_apportion_by_tokens` parameterised by field names and whether unattributed entries are excluded; and the cost and API-duration folds in `compute_ticket_totals` are one `_fold_measured` over a `_MEASURED_FOLDS` table. **Migration:** none for callers — no setting, schema, state shape or artifact changes. **One internal contract did change:** a name imported into a sibling module binds at import time, so `mock.patch.object(lib, "write_json")` no longer reaches a caller that already imported it. Patch the module that uses it — `lib.state.write_json` — or, for a stdlib module, patch the shared object as before (`lib.subprocess`). The facade docstring says so at the point of use.

- **Four more hook events are bound, so four more coordinator instructions became enforcement** (MAR-528, fifth child of epic MAR-501/E1). acs registered exactly two events — `PreToolUse` on `Skill`, and `SessionEnd`. Everything else the pipeline needs at a lifecycle boundary was prose in a SKILL.md, and an instruction a model must remember is a request, not an enforcement point. **`SubagentStop`** (matcher `^acs:`) now validates the subagent's returned XML against `acs-messages.xsd` and writes the phase snapshot the coordinator wrote by hand, at a path taken entirely from the message's own `skill`/`phase`/`iteration` attributes — an invalid message sends the subagent back with the errors, at most `BLOCK_LIMIT` (2) times, after which the coordinator records the failure. **`Stop`** refuses to end a turn that left a run `in_progress` with no result document, naming the exact finish command and the handoff alternative. **`PreCompact`** writes `<partition>/handoff-context.md` from the ledger — the ticket, the pipeline, the in-flight run, open clarifications and the finish command — because compaction is the moment the conversation stops being the record. **`SubagentStart`** (matcher `^acs:`) records the running agent in `<partition>/active-agents.json`, keyed by `agent_id` so parallel executors stay distinct; MAR-529's file-map guard reads it. The matchers are anchored on the plugin scope deliberately: unanchored, the subagent events would fire for `Explore`, `Plan` and other plugins' agents and try to file their output as an acs phase artifact. **These four fail OPEN**, the opposite of the gate — `dispatch.py`'s `run_lifecycle` turns anything raised into exit 0 plus one stderr line, because a bookkeeping bug that ends a session costs more than the bookkeeping — and both blocking hooks give up after `BLOCK_LIMIT`, since a session that cannot stop is worse than a run SessionEnd will mark `interrupted`. **Migration:** none — no settings key, schema or artifact rename, and every SKILL.md's own persist step stays correct (it is still required for work a coordinator performs inline, where no subagent runs). One thing to know: a subagent that omits `iteration` is claiming iteration 1 (the schema's default), and the hook now says so on stderr when that would overwrite a different message.

- **The verifier writes a verdict the kernel reads** (MAR-527, seventh child of epic MAR-501/E1). `verifier_passed` — the single field the `/acs:create-pr` gate turns on — was asserted by the **coordinator**. The verifier is the only role that knows the verdict and already writes a full report, so the coordinator was transcribing a conclusion it did not reach, and the gate checked whether a model had written `true` rather than whether a verifier had passed. The verifier now writes `phases/code/iter-<n>-verdict.json` (lens-scoped on full depth) with a per-dimension result table — by the numbers in `agents/code-verifier.md`, where `n/a` is a real answer, not an omission — plus its findings and `passed`. **`passed` is derived, never asserted:** it is true exactly when no finding is `blocking`, and `acs_lib.verdict.validate_verdict` rejects a document that claims otherwise — in both directions, including a dimension marked `fail` with no blocking finding to match, so the table and the findings cannot disagree about what happened. **The SubagentStop hook runs that validator** (MAR-528), so a verifier that writes no verdict, or an unusable one, is sent back rather than believed — at most `BLOCK_LIMIT` times, after which the coordinator records the failure with the errors named. `acs.py verdict show` reads and validates one; `acs.py verdict merge` builds the iteration's verdict from the four full-depth lens verdicts as the conjunction of `passed`, the union of findings and the worst result per dimension — arithmetic over the lens files, not a second opinion — so the coordinator *invokes* the merge instead of authoring a verdict. `verdict.schema.json` ships the shape and says in its own description which rule it cannot express and which function carries it. `info` findings are reported and carried and never gate, unchanged. **Migration:** none yet — `states.verifier_passed` is still the create-pr gate and is still written by the coordinator, now *copied* from `acs.py verdict show`'s `passed` rather than concluded from a findings count. MAR-523 removes the copy by deriving the field in `acs finish`.

## [0.4.9] - 2026-09-03

> ### ⚠️ This patch release contains four BREAKING changes
>
> The version increment does not signal them, so read this before updating:
>
> 1. **`/acs:initialize` no longer resolves** — the skill is renamed to `/acs:setup` (MAR-1). Every invocation, alias and doc reference must be updated.
> 2. **Pipeline state moved into the repo** at `.acs/state-machine/` (ADR-0086). An existing external workspace is not read from its old location; `/acs:setup` offers a one-shot `migrate_workspace.py` migration.
> 3. **A post hook now refuses a result document with no `status`** (MAR-515). Any caller relying on the implicit `completed` default must state the status explicitly.
> 4. **`models.overrides.ship` is now a hard error** (MAR-516). `/ship` spawns no subagents of its own — move the override onto the skill that runs the phase.
>
> Upgrading from v0.4.8 is not a drop-in patch upgrade despite the version number.


### Added

- **`pipeline-step.py` — a CLI for skills with no post-hook to record a pipeline step** (MAR-511). `/acs:test` has no post-hook, so without it the skill would have to embed Python in its prose to reach `update_pipeline`, the pattern ADR 0001 exists to prevent. A ticket-scoped `/acs:test --for-ticket <id>` run now records its own `steps.test` outcome, which is what opens `/acs:docs-sync`'s gate — the remedy that gate's own error message names, and which nothing could previously satisfy. `--only-if-present` keeps a direct, user-initiated run from newly creating the gate it was run to open. `--ticket` and `--skill` are validated against `pipeline-state.schema.json`'s own id pattern and step enum before the partition is resolved, since `--ticket` becomes a path segment. **Migration:** none — new script, additive step field.

- **`update_pipeline` gains an `extra` channel for step fields it does not own** (MAR-510). `extra={"<key>": <value>}` merges a caller field onto the step entry and `extra={"<key>": None}` removes it, while the fields the entry owns (`status`, `started_at`, `ended_at`, `summary`) stay unwritable through it. `/acs:ship` uses it for the `fix_loops` counter on the post-code test gate — previously the skill claimed no library change was needed because `update_pipeline` "already writes an arbitrary-shape step dict", which it did not. `/acs:ship` also now RESETS the counter when the step is re-entered after a failed cap; without that a resumed run re-read the capped value and stopped on its first failure, so it could never make progress. **Migration:** none — additive parameter, additive step field already allowed by `pipeline-state.schema.json`.

- **BREAKING: the `models` settings block is validated fail-closed at config time** (MAR-516). `validate_models` (`acs_lib.py`) now rejects an unknown `effort` value (the closed set is `low`, `medium`, `high`, `xhigh`, `max`, `inherit`), a non-object `models.overrides`, an unknown override role, and an unknown override skill. The allowed override-skill set is DERIVED from `HOOKED_SKILLS` (`MODEL_OVERRIDE_SKILLS`) rather than hand-listed, and the `models.overrides.propertyNames.enum` in `settings.schema.json` is pinned to that same list by a drift test. Validation runs from `build_context`, so it fires on every hooked skill run instead of failing late at subagent-spawn time. **Migration:** `models.overrides.ship` was schema-valid before this change and is now a hard error — `/ship` spawns no subagents of its own, so move any such override onto the skill that actually runs the phase (`code`, for example). Eight skills that were missing from the schema enum are now accepted.

- **API-duration sampling, apportionment, and dashboard surfacing for `/acs:usage`** (MAR-6 + MAR-7, epic MAR-2 Seam B1/B2). MAR-6 widens the existing cost-sampling/allocation mechanism (ADR 0082 §4) to a second, independently-tracked quantity, `total_api_duration_ms`: `record_cost_sample` now probes `total_api_duration_ms` via the new `_extract_api_duration` (a structural mirror of `_extract_total_cost`) and writes it alongside `total_cost_usd` in the same sample record — a sample is now written when EITHER quantity is found; the shared `<ckid>-cost-cursor.json` widens to `{ts, total_cost_usd, total_api_duration_ms}` and `allocate_cost` advances it once, in one write, for both quantities; `_apportion_duration` (`cost_sampler.py`) apportions duration across `role_usage` by the identical token-share mechanism as cost, with a coupled-degradation rule — a missing/non-numeric duration on either cursor edge degrades only duration to `"unavailable"` (`api_duration_scope = "duration_unavailable_on_cursor"`), cost unaffected; a cost-reset delta marks BOTH quantities unavailable. Documented as an append-only "Amendment — MAR-6" section on ADR 0082 (Context/Decision/Consequences unedited). MAR-7 makes the now-measured figures observable: `metrics_aggregate._accumulate_burn` widens to a 3-tuple (adds a per-skill raw duration accumulator, `ticket_skills`, zero extra file reads), feeding two additive widenings — panel 3 gains `step_api_duration`/`step_order` per-ticket sibling keys (`steps` itself unchanged), and `usage_by_ticket` gains ticket-scope `api_duration_ms`/`api_duration_basis` plus a `skills[]` array (`_finalize_skill_bucket`) with independent per-run detail; `usage_summary` gains `total_api_duration_ms` and its two per-ticket/per-PR averages. `metrics_render` renders panel 3's new per-skill sub-rows (step span + API duration + basis, one line per `step_order` entry) and `usage_by_ticket`'s new ticket-scope header line plus `skills[]` table (`_term_skill_table`/`_html_skill_table`), via a new `_humanize_ms` wrapper that delegates to `_humanize_seconds`; a `step_api_duration` cell renders the literal `UNAVAILABLE` marker uniformly whether that skill's entry is structurally absent (e.g. the unhooked `test` pipeline step) or present with its own `basis == "unavailable"` (D6), and a `usage_by_ticket.skills[]` row is emitted for any skill with run entries at all — never suppressed to an empty list just because duration was never measured, only a skill with zero run entries anywhere is genuinely absent. **Migration:** none — every new field is additive on already-open state files and freshly computed at aggregation/render time; no settings key, schema, state-file shape, or artifact rename.
- **Percentage (token-share/cost-share) breakdown for `/acs:usage`** (MAR-4, epic MAR-2 Seam C, #389). `metrics_aggregate._apply_panel6_shares` computes each panel-6 role bucket's repo-scope `token_share_pct`/`cost_share_pct` once, post-loop, from the totals panel 6 already sums; `metrics_render` gains matching "token %"/"cost %" columns on both terminal and HTML views, plus a new `UNAVAILABLE` render-layer constant shown on a cost-share cell with no measured cost (distinct from the pre-existing `cost_basis` `"unavailable"` enum value — a different, run-level fact). `/acs:usage` also renders a new "Usage by ticket" panel (`_usage_by_ticket_panel`/`_finalize_role_ticket_bucket`) — input/output/cache-write/cache-read tokens, cost, and token-share/cost-share percentage per role, scoped to that ticket's own totals (a different denominator than panel 6's repo-scope shares, not a conflicting figure). **Migration:** none — percentages are computed fresh at aggregation time and never persisted to any state file; no settings key, schema, state-file shape, or artifact rename.
- **`/acs:initialize`'s two-layer gitignore retrofit for the in-repo state root, plus a new one-shot `migrate_workspace.py` migrator** (ADR-0086). Alongside the existing `settings.local.json` retrofit, `/acs:initialize` now also ignores `.acs/state-machine/` two ways — a tracked `.gitignore` entry AND an idempotent append to `<git-common-dir>/info/exclude` — then asserts the combined result with `git check-ignore -v` and warns (never silently proceeds) when the ignore is not actually in effect, or when a broad `.acs/` rule would also hide `.acs/settings.json`/`.acs/ci/*` from CI. A new `migrate_workspace.py --from <old-workspace-root> --to <new-state-root> --repo-root <main-checkout-root> [--dry-run]` script offers a user-confirmed, one-shot migration of an existing external workspace into the new in-repo state root — preflight-aborting on any live `.lock` or an `in_progress` last run anywhere under the old partition tree, copy-then-verify-then-remove semantics, safe to re-run if interrupted. **Migration:** none — opt-in, offered interactively by `/acs:initialize` only when an external workspace is detected for the repo; declining leaves the old workspace and `workspace_path` untouched.

### Changed

- **`gh` is now classified as acs's only GitHub transport; every in-scope `gh` call site across create-ticket/create-pr/merge-pr is disposed critical, critical-per-ticket/soft-per-batch, or non-critical, and merge-pr's post-merge tracker sync gains a failure rule for the first time** (MAR-403, epic MAR-401 Seam A). A **critical** operation — `gh pr create`/`gh pr edit`, `gh issue view` on import, `gh pr merge` at both the ticketed and exempt-mode sites, and every gate-input read whose failure leaves a readiness gate unevaluable (`gh pr list`, `gh repo view --json defaultBranchRef`, merge-pr's resume/readiness/BEHIND-carve-out reads) — now surfaces gh's stderr verbatim plus one canonical `acs_lib.gh_failure_hint()` hint and stops the run, with no silent fallback to any other transport. `create-ticket/SKILL.md`'s Step 5 `gh issue create` tracker-sync call is a distinct **critical (per ticket), soft (per batch)** disposition: a failed create for one ticket is an error-severity finding naming that ticket's id + error + the canonical hint, `replayable: false`, but the batch is never aborted — the loop continues to the next ticket, and only that one ticket's `external` stays null. A **non-critical** operation (labels, assignee, milestone, Projects v2 item-add/field-edit, CODEOWNERS reviewer request, the PR back-reference comment, the `gh run list` CI diagnostic read) degrades to one info finding plus a replayable `gh` command block and the run continues. **Behaviour change**: widening "critical" to gate-input reads means a failed `merge-pr` readiness read now stops a run that could previously have degraded — an unevaluable gate is never a passed gate. merge-pr's `### Step 2 — Cleanup` tracker sync gains a new **loud-but-non-reverting** rule: a post-merge `gh issue close`/Projects Status→Done failure is never grounds to revert or re-attempt the merge — it is reported loudly, names the outstanding sync, and the run still finishes `merged: true`. The now-superseded `### GitHub MCP fallback (no gh CLI)` section (`create-pr/SKILL.md`, MAR-307) is removed outright — no acs skill or agent offers or implies a second GitHub transport (clarification C-6). Recorded as ADR-0088. **Migration:** none — no settings key, schema, state-file shape, or artifact rename; the canonical hint constants (`GH_ACCESS_DENIED_MARKER`/`GH_ACCESS_HINT`/`GH_GENERIC_HINT`/`gh_failure_hint()`) are new, pure additions to `acs_lib.py`.
- **`allocate_ticket_id` gains a fail-closed reconciliation gate for fresh/unreconciled workspace partitions** (MAR-402, epic MAR-401 Seam B). Inside its existing O_EXCL critical section, the first allocation for a `(repo_id, prefix)` partition with neither a `next` counter nor `reconciled: true` now refuses with exit code 2 and a ranked, bounded, network-free local-evidence proposal — committed-files grep, then git commit subjects+bodies, then branch names, each capped at 400 commits/refs, 10s per subprocess, degrading to "no local evidence" on timeout — instead of silently restarting the sequence at 1. A new `--seed-next <n>` flag on both `new-ticket.py` and `skill-start.py --allocate` confirms the proposal or repairs a wrong/stuck reconciliation: it mints `<PREFIX>-n`, and writes `next=n+1`, `reconciled: true`, `seed_source: "explicit-user"`, and `seeded_at` to `counters.json`. `counters.schema.json` gains these three additive optional fields; `observed_max` is surfaced only in the refusal message for a human to read and is deliberately never persisted. Recorded as ADR-0087. **Migration:** none — an already-populated `counters.json` (every existing repo, and any workspace moved by `migrate_workspace.py`) is treated as already reconciled: no prompt, no scan, no new keys.
- **`/acs:setup` and `/acs:merge-pr` explain why their approval rules differ** (MAR-513). The branch protection `/acs:setup` offers (`required_approving_review_count: 0`) makes a PR mandatory without forcing a review, while `/acs:merge-pr` requires an APPROVED review for every merge it performs (**ADR-0028** mitigation m6, unconditional with no settings kill-switch). Both skills now say so, scope the requirement to today rather than asserting it as permanent, and name PRD **G26** — narrowing m6 to agent invocations — as the tracked resolution. They also name the solo-maintainer consequence instead of presenting the workaround as design: GitHub forbids self-approval, so the skill can never merge there, and an out-of-band UI merge strands the ticket at `in_review` (never archived, no tracker Status→Done transition, metrics never bumped). **Migration:** none — documentation only; no readiness dimension, gate, or default changed, and no unreviewed merge path added.
- **BREAKING: a post hook refuses a result document with no `status`** (MAR-515). `post-<skill>.py` previously defaulted an absent or status-less result to `completed`, finalizing the run and opening the next gate on nothing at all. It now exits 1, and `finalize_run` raises rather than defaulting at the point of persistence — so an in-process caller cannot bypass it either. An invocation passing `--result-file` at an empty file now names that path in the error instead of reporting a generic "no result document". **Migration:** any caller relying on the implicit `completed` default must state the status explicitly (`--status`, or a `status` field in the result document); every in-repo caller already does.
- **The per-role model recommendation moves to one constant** (MAR-517). `acs_lib.RECOMMENDED_MODELS` is the single source for the ids `/acs:setup` offers; `.acs/settings.json` and the setup prose are both asserted against it, so a new model generation is a change to the constant, those settings and that prose — never a test edit. Nothing in the runtime reads it: the recommendation is a product fact the tests enforce, not an input to gate or spawn behaviour. **Migration:** none — no settings key, schema, or state-file change.
- **`/acs:create-architecture`'s, `/acs:create-design`'s, and `/acs:create-requirements`'s reflection loops each drop the per-iteration re-plan and become execute → verify, completing the plan-once migration across all twelve triad-keeping skills** (ADR-0084). The planner now runs exactly once per run, before the loop, for each of these three skills — exactly one `<skill>-planner` subagent is spawned across the whole run, however many iterations it uses, with no intervening planner spawn on later iterations. On iteration 2+, verifier findings route straight to the executor's `<task>` `<context>`, and the executor authors the remediation (the create-design and create-requirements executors already accepted iteration 2+ findings via `<context>` — only their planners and coordinators changed; create-architecture's executor gains the same `<context>`-driven fix step). The cap is **unchanged at 3** in every lane but now counts execute+verify rounds rather than plan+execute+verify triads. The resume path for all three never spawns a second planner either. The three verifiers' independent-corroboration behavior (fresh re-derivation from the doc set / codebase / PRD, never trusting the planner's or executor's claims) is **unchanged** by this change. **Migration:** none — no settings key, schema, state-file shape, or artifact-path change.
- **`workspace_path` becomes optional; the acs plugin workspace root now defaults in-repo** (ADR-0086, supersedes ADR-0003). When unset, the state root resolves to `<main-checkout>/.acs/state-machine` — gitignored, anchored via `git rev-parse --git-common-dir` so every linked worktree of a repo resolves to the same physical tree — hard-failing with a `GateError` on bare-repo/submodule layouts that cannot resolve a normal main-checkout root, where an explicit `workspace_path` override remains the escape hatch. `validate_settings()`'s pre-existing outside-the-repo rejection is inverted: an explicit override may now point anywhere the user chooses. **Migration:** none forced — every consumer repo already running acs has an explicit `workspace_path` set from a prior required `/acs:setup` and is unaffected until it re-runs `/acs:setup` and either accepts the new default or invokes the migrator.
- **BREAKING: `/acs:initialize` no longer resolves — the skill is renamed to `/acs:setup`** (MAR-1). The skill directory (`plugins/acs/skills/{initialize => setup}/SKILL.md`), `acs_lib.UNHOOKED_SKILLS` (`acs_lib.py:45`), `acs_lib.ATTRIBUTION_SKILL_MAP` (`acs_lib.py:60`), and the `skillName` enum in `plugins/acs/schemas/acs-messages.xsd:37`, `plugins/acs/schemas/skill-state.schema.json:9`, `plugins/acs/schemas/clarifications.schema.json:17`, and `validate_xml.SKILLS` (`plugins/acs/hooks/scripts/validate_xml.py:79`) all move together. `ATTRIBUTION_SKILL_MAP` flattens to `{"init": "setup", "initialize": "setup"}` rather than chaining onto the existing `"init": "initialize"` entry — `usage_reader._normalize_skill`'s single, non-chained `.get()` (`usage_reader.py:74`) would otherwise resolve a historical `acs:init` attribution to `"initialize"`, a name no longer present in `HOOKED_SKILLS + UNHOOKED_SKILLS`, silently misattributing those historical usage samples; the flat form maps both historical names directly to the current skill. No alias, shim, or redirect ships — this is deliberate, exactly as `/acs:init` → `/acs:initialize` was below (MAR-184): `setup` (like its predecessor `initialize`) is unhooked and writes no per-ticket state file (`initialize-state.json`/`init-state.json` count across the workspace, freshly measured: **0**), so removing the old name outright is non-regressive. After `claude plugin update`, run `/acs:setup`; existing `.acs/settings.json` and workspace state are unaffected — nothing keys off the skill name.

### Fixed

- **The repo-wide skill-name sweep no longer scans git-ignored paths** (MAR-570). `tests/acs/test_setup_skill_reference_sweep.py` enumerated the tree with a raw `os.walk`, pruning only `.git`, `node_modules`, `__pycache__` and `.claude`. Everything else git ignores was swept as if it were repo source — including `.acs/state-machine/`, which ADR-0086 made the in-repo default workspace, so a consumer's own ticket partitions were scanned: a retired skill-name token written in an ordinary ticket note failed the suite with nothing wrong in the repository. Enumeration now comes from `git ls-files --cached --others --exclude-standard` (tracked plus untracked-but-not-ignored, so a brand-new unstaged source file is still covered), with the raw walk kept as a fallback for a checkout git cannot enumerate. The change is subtractive: on this repo it drops 5421 ignored files from a 5967-file sweep and adds none. **Migration:** none — test-only; the historical allowlist and the line-scoped 2026-08-13 ledger carve-out are unchanged.

- **Stale facts in the prose the model reads at runtime** (MAR-519). Eight verifier agents cited dimension counts their own dimension lists no longer matched, so a model copying the example reports a wrong number. Fifteen skills carried `tokens`/`cost_usd` in their `result.json` examples, which `finalize_run` has measured and silently ignored since ADR 0082. The completion report's iterations metric was wrong twice over: skills that run no reflection loop printed a fraction of a loop they never ran, and `<cap>` is a constant 3 for eleven of the twelve triad-keeping skills — only `/acs:code` derives it from the lane. Label substitutions in the skills now match INTERNALS, which states both rules by property rather than by an enumeration that drifts. **Migration:** none — prose only, no executable change.

- **Removed the dead Codex adapter** (MAR-518). `codex_adapter.py` was an 88-line argparse stub with no caller: the MAR-5 PR that would have wired it was rejected because Codex CLI has no `Skill` hook matcher and no `SessionEnd` event, so it shipped unreferenced for six releases, kept alive only by five tests of its own argument parsing. Its test module goes with it, and a new regression guard asserts the deletion — nothing in the suite failed while it sat unused, and nothing would have failed if it came back. The runtime-coupling inventory keeps the seam analysis as the basis for any future adapter, with its MAR-5 rows marked superseded. **Migration:** none — the module had no consumer, no CLI entry point in `hooks.json`, and no settings key.

- **The shipped pipeline step lists match the order the code actually runs** (MAR-512). `CLAUDE.md`, the `CLAUDE.acs.md` template, both READMEs and `/acs:setup`'s closing summary described a `create-ticket → create-spec → code → create-pr` walk: `create-spec` was deleted by ADR 0066, and both `docs-sync` and the conditional `test` step were missing. `test` is a real step — `PIPELINE_STEP_ORDER` places it between `code` and `docs-sync`, and `gate_docs_sync` reads `steps.test` — so a list omitting it misdescribes the gate a user will hit. The living requirements (`workflow.md`, `skills.md`) carried the same gap and are corrected with them. **Migration:** none — documentation only.

- **`--allocate` no longer mints a second ticket for work that already has one, nor adopts another run's** (MAR-509). `skill-start.py --allocate` reuses an existing partition when the run is RESUMING one, so `/acs:ship` re-invoking an interrupted `create-ticket` no longer creates a duplicate. Reuse is deliberately narrow, because the failure mode is data integrity: only `--ticket`, or an `--args` value that IS a ticket id, counts. Free text that merely CITES a live id ("follow-up to SHOP-1: ...") mints a new ticket as before — `create-ticket` is invoked with the user's prompt verbatim, and adopting a cited id would overwrite active work. Args-derived reuse is scoped to `/acs:create-ticket`; the six product-level skills route resume through `--ticket`, so it bought them nothing while letting a leg adopt a delivery ticket. The session pointer and branch name are never consulted here, preserving ADR 0085 fan-out isolation. **Migration:** none.

- **The gate dispatcher fails closed** (MAR-514). `dispatch.py` ran each gate in a subprocess with `timeout=25` but never caught `subprocess.TimeoutExpired`: a hung gate raised, the dispatcher exited 1, and Claude Code treats anything other than exit 2 as "not blocked" — so the skill ran. The gate now runs in-process under a bounded alarm. The bound is raised as a `BaseException` subclass, not `TimeoutError`: `TimeoutError` subclasses `OSError`, so a gate hanging inside a git call had its own alarm swallowed by `acs_lib._git`'s handler and ran on unbounded, returning 0. A second hard alarm exits the process if the first is absorbed anyway, and `SystemExit`/`KeyboardInterrupt` inside a gate now also exit 2. ADR 0002 is amended append-only: the dispatcher no longer routes to `pre-<skill>.py`. **Migration:** none — the 15 `pre-*.py` forwarders remain on disk (now unreachable; `hooks.json` registers only `dispatch.py`) and are removed with MAR-521.

- **`parse_iso` accepts the timestamp forms Claude Code actually writes, without varying by interpreter** (MAR-520). Fractional seconds of any precision and explicit `Z` / `±HH:MM` / `±HHMM` offsets now parse, so transcript records carrying them are counted instead of silently dropped from token and cost totals. Parsing goes through an explicit regex plus `strptime` rather than `datetime.fromisoformat`, whose acceptance set CPython 3.11 widened — delegating to it accepted records on 3.12 that it dropped on 3.9, the CI floor, which is the same silent-drop the fix exists to remove. A **bare date still returns `None`** per ADR 0020: the panel-7 lead/cycle callers read that as "no data" and degrade, where a midnight-anchored value would render as measured. The space-separated and basic (`20260620T090000Z`) forms are rejected rather than accepted as a side effect. **Migration:** none — no settings key, schema, or state-file change; previously-rejected records simply start counting.

- **Merged-ticket enumeration for `/acs:release` no longer reports zero when PRs were merged without `/acs:merge-pr`** (MAR-306). `enumerate_merged_tickets` reads `archive/` first, then the new `enumerate_git_log_tickets` recovers ids from `base_branch` commit subjects since the boundary tag; archive entries always win on a duplicate id, and a non-zero `git` exit degrades to `[]` rather than raising. Additive surface: a new optional `--ticket-prefix` on `draft`/`bump` (passed by `/acs:release` as `settings.ticket_prefix`), and a new `tickets[].source` (`"archive"`/`"git-log"`) on `draft`'s JSON. Known limits: tracker-ref-only subjects (`[#399] …`) and shallow clones still under-count, and git-log entries carry no `parent`/`docs_only` — see `docs/operations/release-runbook.md`'s "Accepted limitations of the git-log fallback". **Migration:** none — additive flag and additive output field; archive-only behaviour is byte-identical when no ticket-ref subjects exist (pinned by `test_archive_only_enumeration_is_byte_identical_when_history_has_no_ticket_refs`).
- **Panel 6's repo-scope `cost_share_pct` no longer fabricates `0.0%` for a role that was never charged** (MAR-400, #399). `metrics_aggregate._empty_panel6_bucket` gains a `cost_seen` flag, set only inside `_accumulate_burn`'s `if _is_number(cost)` branch — mirroring the `_empty_model_bucket`/`_finalize_model_bucket` pattern already used for `usage_by_model` — and `_apply_panel6_shares` now returns `cost_share_pct: None` for a bucket that never received a numeric `cost_usd`, so `/acs:usage` renders the `UNAVAILABLE` marker ("unavailable") rather than a real-looking `0.0%`. A role genuinely charged exactly $0 keeps `cost_seen: True` and still renders `0.0%`, so the two cases stay distinguishable. This closes the "unknown value rendered as a valid known value" gap on the MAR-4 percentage-breakdown feature above, per ADR 0082's "never fabricated, never zero-padded" rule, and makes the already-documented behaviour in `docs/operations/observability.md` ("A bucket with no measured cost renders **"unavailable"** for cost %") actually hold at repo scope. `token_share_pct` and the ticket-scope `usage_by_ticket` shares are unchanged. **Migration:** none — panel 6 is computed fresh at aggregation time and never persisted to any state file; `cost_seen` is an additive key on the emitted bucket, read by no renderer and constrained by no schema.

## [0.4.8] - 2026-08-26

### Added

- **Per-model token/cost breakdown for `/acs:usage`** (MAR-3, epic MAR-2 Seam A, #388). `usage_reader.read_transcript_usage` now buckets token usage by model into a new `model_usage` list, parallel to the existing `role_usage` list (D1.1 Option B — `role_usage`'s shape is completely unchanged). `cost_sampler.allocate_cost` apportions the same session-window cost delta across `model_usage` by token share with NO unattributed-token exclusion (D1.2 Option A) — its cost total can therefore exceed `role_usage`'s attributed-only total by `excluded_cost_usd`, a documented reconciliation identity, not a bug. `/acs:usage` renders a new "Usage by model" panel (input/output/cache-write/cache-read tokens and cost per model), at both repo and per-ticket scope. **Migration:** none — `model_usage` is additive on the run entry (`skill-state.schema.json`, outside the closed `tokens` object per F10); a legacy pre-MAR-3 run entry simply lacks it and renders "no data" on the new panel.
- **New optional `evals.forge_repo` settings key + `ACS_FORGE_REPO` override** (MAR-67), read only by `evals/<plugin>/` — never by the hook layer, so no consumer behavior changes and no migration is needed. Names the dedicated, `NEVER-PRODUCTION`, org-owned GitHub repo the forge-tier eval harness (`ForgeSandbox`, `evals/acs/harness.py`) runs the real delivery pipeline against, guarded by three independent, no-override-escape-hatch checks: the target's name must match `^acs-eval(-[a-z0-9][a-z0-9-]*)?$` (`plugins/acs/schemas/settings.schema.json`), it must not be this repo's own remote, and its checkout must contain a committed `.acs-eval-target` marker file.
- **`/acs:create-ticket <epic-id> --fan-out`** (MAR-78, #363): a second invocation mode of `/acs:create-ticket` that mints an already-created, already-designed epic's children only — Steps 1-3 are not re-run. Reuses Step 2's confirmation gate: the proposed breakdown is derived from the epic's `design.md` slice/seam content when an approved design exists, and is presented and user-confirmed before any child is minted. When no approved design exists yet, the mode surfaces that precondition and asks the user how to proceed — it neither proceeds silently nor hard-refuses.
- **Coordinator plan approval: `plan-approval.json` + `states.plan_approved`** (MAR-73, slice 3 of MAR-69, #358). A new deterministic `acs_lib.plan_approval_eligible` pure function computes plan-approval eligibility from the plan artifact's own content plus `settings.test_coverage_percent` (never an LLM self-assertion); the new `plan-approval.py` hook script is the sole writer of `<partition>/phases/code/plan-approval.json`, recording the predicate's inputs/checks/failures plus the approved plan's sha256, and mirrors the verdict into `code-state.json`'s `states.plan_approved`. STANDARD/COMPLEX only, written at most once per approved plan digest (idempotent on resume). Nothing gates on it yet — that's slice 4. Migration: none — no settings key, no schema change, no state-file shape change, no artifact rename.
- **`code-verifier` gains dimensions 15 and 16; the plan-revocation escape hatch lands; ADR 0073 amends ADR-0004** (MAR-74, slice 4 of MAR-69, #359). `code-verifier` gains dimension 15 **"Plan conformance"** (blocking when active / N/A otherwise; activation computed by the verifier from `plan-approval.json` — `eligible`, `plan_path == phases/code/plan.md`, digest match; judged against the approved `## Executor tasks & file map` + Approach; strictly subordinate to dimension 1, which stays the loop's fixed point) and dimension 16 **"Approval-audit"** (blocking, every lane; re-runs `recommend_stakes` over `git diff --name-only`); the lens table gains 16 → lens B and 15 → lens C; light verify now 15 base dimensions, full verify 16. The **plan-revocation escape hatch** (`plan-superseded-<k>.md`, copy-never-move, boundary-gated, `clarify.py`-confirmed) moves from reserved to real. **ADR 0073** amends ADR-0004's verifier-anchoring clause append-only (ADR-0004 itself unedited). Nothing new gates — `/create-pr` stays `verifier_passed`. Migration: none (no settings key, no schema change, no state-file shape change).

### Changed

- **The MAR-70 read-both resume-only compat fallback for `/acs:code`'s plan artifact is retired** (MAR-73, slice 3 of MAR-69, #358). `plan.md` is now unconditionally the only name `/acs:code` (and its downstream consumers, `/acs:test --for-ticket` and `plan-approval.py`) ever reads or writes for the plan artifact, on every lane, on every run, including resume — the fallback to the highest-numbered `<partition>/phases/code/iter-*-plan.md` when `plan.md` was absent is gone. **Migration:** none for tickets that already completed the MAR-70 rename. A ticket that never completed its MAR-70-era `iter-<n>-plan.md` → `plan.md` transition can no longer resume via the old fallback; this is the accepted, explicit consequence of retiring it.
- **Behaviour change: an epic's own `/acs:create-ticket` run no longer fans out children** (MAR-78, #363). It now completes with `children: []`; fan-out is deferred to the new `--fan-out` mode above, run after `/acs:create-design`. Also: the tracker-sync set (Step 5) now excludes any ticket whose `external` is already non-null, so a `--fan-out` (or split/restructure) run never re-creates the already-synced epic's remote issue as a duplicate; and the split/restructure mode's child minting is explicitly routed back through Step 4.
- **`derive_lane`'s `needs_design` floor (Rule 4) is removed; `needs_design` is now epic-only** (MAR-76). `derive_lane(size, stakes, needs_design, ticket_type)` no longer floors a `trivial`/`small` non-epic ticket to `STANDARD` just because `needs_design` is `true` — the lane now derives from `size` alone once the `stakes == "high"` floor and the epic → `COMPLEX` override (both unaffected) don't apply. `/acs:create-ticket` no longer offers or confirms `needs_design` for story/task; it stays an always-`true`, stated-not-asked flag for epics only. **Migration:** no data migration and no `ticket.json` rewrite is required — a legacy non-epic ticket carrying `needs_design: true` simply recomputes to a lower lane on its next `derive_lane` call (`plugins/acs/hooks/scripts/acs_lib.py:84-109`, a documented public contract, `docs/architecture/lld/contracts.md:52`).
- **BREAKING: `/acs:init` no longer resolves — the skill is renamed to `/acs:initialize`** (MAR-184). The skill directory (`plugins/acs/skills/{init => initialize}/SKILL.md`), `acs_lib.UNHOOKED_SKILLS` (`acs_lib.py:45`), and the `skillName` enum in `plugins/acs/schemas/acs-messages.xsd:33`, `plugins/acs/schemas/skill-state.schema.json:10`, `plugins/acs/schemas/clarifications.schema.json:18`, and `validate_xml.SKILLS` (`plugins/acs/hooks/scripts/validate_xml.py:79`) all move together. No alias, shim, or redirect ships — this is deliberate, unlike the `/acs:create-spec` deletion (0.4.6, below), whose `create-spec` anchors in `plugins/acs/hooks/**` and `plugins/acs/schemas/**` were retained for backward compatibility: that retention protected live per-ticket state, but `initialize` is unhooked and writes no state file (`init-state.json`/`initialize-state.json` count across the workspace: **0**, versus **78** for `create-spec-state.json`), so removing the old name outright is non-regressive. After `claude plugin update`, run `/acs:initialize`; existing `.acs/settings.json` and workspace state are unaffected — nothing keys off the skill name.
- `/acs:ship` now stops by design after `code` on a full-verify lane, ending `handed_off` with `/acs:ship <ticket-id>` as the resume command; light-verify (cheap-tail) pipelines are unchanged and still complete end-to-end; `ship/SKILL.md` "Full-verify pipeline boundary" (MAR-179, #333).
- `/acs:code <epic-id>` (direct invocation) no longer runs — the `pre-code.py` gate (`gate_code` in `acs_lib.py`) now refuses any ticket with `type == "epic"` and exits 2 with the remediation path `/acs:create-design <id>` (if the epic has no design yet) → `/acs:create-ticket <id> --fan-out` → `/acs:code` on a child. Non-epic tickets, including `size: large` (COMPLEX lane) ones, are unaffected — they proceed, and instead get a **surfaced, non-blocking** breakdown recommendation from `code/SKILL.md`'s Start and escalation steps. `create-design/SKILL.md`'s handoff next-step is now epic-conditional rather than an unconditional `/acs:code <id>` (MAR-75, #360).
- **`/acs:code`'s plan artifact is renamed from `iter-<n>-plan.md` to a single per-ticket `<partition>/phases/code/plan.md`** (MAR-70, slice 1a of MAR-69). The plan phase now runs exactly once per run, before the loop, and writes `plan.md` a single time (see the MAR-71, slice 1b of MAR-69 entry below — it is never renamed, numbered, or rewritten in place). `/acs:test --for-ticket` reads the same path. `phases/code/iter-<n>-plan.xml` message persistence and the `iter-<n>-execute.json` / `iter-<n>-verify.md` artifacts are unaffected. **Migration:** no backfill and no rename of existing files — an in-flight ticket that has only `iter-<n>-plan.md` still resolves via a resume-only fallback to the highest-numbered file, supported for one release (current version `0.4.7`).
- **`/acs:code`'s reflection loop drops the per-iteration re-plan and becomes execute → verify** (MAR-71, slice 1b of MAR-69). The planner now runs exactly once per run, before the loop — exactly one `acs:code-planner` subagent is spawned across the whole run, however many iterations it uses. On iteration 2+, verifier findings route straight to the executor's `<context>` with no intervening planner spawn, and the executor authors the remediation. The light=1 / full=3 verify-depth caps are **unchanged in value** but now count execute+verify rounds rather than plan+execute+verify triads. Mid-flight escalation (MAR-57)'s detection point and monotone ceiling are unaffected. **Migration:** none — no settings key, schema, state-file shape, or artifact path changes.
- **`/acs:code` no longer spawns a `code-planner` subagent on TRIVIAL/SMALL** (MAR-72, slice 2 of MAR-69, ADR 0074) — the coordinator authors `<partition>/phases/code/plan.md` itself against the identical artifact contract (same six headings, same five fold section literals, both mandatory verbatim clauses, explicit intake mode); STANDARD/COMPLEX still spawn exactly one planner per run. The lane read is the freshly recomputed `derive_lane(...)`, never cached `ticket.lane` (D-2); mid-flight escalation never retro-spawns a planner (D-3); no `<task phase="plan">` message and no `iter-<n>-plan.xml` snapshot exist on fast lanes (D-4). Verify depth/iteration caps (light 1 / full 3), the verifier-in-every-lane gate, the TDD/coverage gate, and the four plan-dependent verifier dimensions are unchanged (G16 preserved). **Migration: none** — no settings key, schema, state-file shape, or artifact path changes.
- **`/acs:docs-sync`'s reflection loop drops the per-iteration re-plan and becomes execute → verify** (MAR-300). The planner now runs exactly once per run, before the loop — exactly one `acs:docs-sync-planner` subagent is spawned across the whole run, however many iterations it uses (`SKILL.md:93-96`). On iteration 2+, verifier findings route straight to the executor's `<context>` with no intervening planner spawn (`SKILL.md:162-165`). The cap is **unchanged at 3** but now counts execute+verify rounds rather than plan+execute+verify triads (`SKILL.md:98-103`). The resume path never spawns a second planner either (`SKILL.md:60-62`). The verifier's independent re-derivation behaviour is unchanged (`docs-sync-verifier.md` byte-unmodified by this change). **Migration:** none — no settings key, schema, state-file shape, or artifact-path change.
- **`/acs:create-project`'s reflection loop drops the per-iteration re-plan and becomes execute → verify** (MAR-301). The planner now runs exactly once per run, before the loop — exactly one `acs:create-project-planner` subagent is spawned across the whole run, however many iterations it uses (`SKILL.md:95-96`). On iteration 2+, verifier findings route straight to the executor's `<context>` with no intervening planner spawn (`SKILL.md:226-229`). The cap is **unchanged at 3** but now counts execute+verify rounds rather than plan+execute+verify triads (`SKILL.md:98-103`). The resume path never spawns a second planner either (`SKILL.md:63-65`). The verifier's independent build/lint/test/coverage re-run behaviour is unchanged (`create-project-verifier.md` byte-unmodified by this change). **Migration:** none — no settings key, schema, state-file shape, or artifact-path change.
- **`/acs:standardize-project`'s reflection loop drops the per-iteration re-plan and becomes execute → verify, with a frozen iteration-1 allowlist approval gate** (MAR-302, ADR-0079). The planner now runs exactly once per run, before the loop — exactly one `acs:standardize-project-planner` subagent is spawned across the whole run, however many iterations it uses. On iteration 2+, verifier findings route straight to the executor's `<context>` with no intervening planner spawn. The cap is **unchanged at 3** but now counts execute+verify rounds rather than plan+execute+verify triads. The resume path never spawns a second planner either. Unlike MAR-300/MAR-301, `standardize-project-verifier.md` is not byte-unmodified: it gains the Verdict-split section — but the additive-only diff-status enforcement itself (`classify_additive_diff`, `acs_lib.py` unchanged) is untouched, and remains independently re-run every iteration. Two facts unique to this ticket: (1) the Additive-surface allowlist is authored exactly once, by the iteration-1 planner, and is frozen and authoritative for the whole run — the executor's writable surface is monotonically non-increasing across iterations, never widening; (2) a narrow, class-scoped `severity="info"` degradation routes an out-of-frozen-allowlist `plan-conformance` missing-scaffold finding to `recommended_follow_ups` instead of blocking, while `additive-only`/`doc-set-authorship` findings (and dimension 4's "no unplanned extra scaffold file" clause) always remain blocking, fail-closed on any undetermined case. **Migration:** none — no settings key, schema, state-file shape, or artifact-path change.
- **BEHAVIORAL CONTRACT CHANGE: the shared `plan-conformance` verifier dimension across `/acs:create-quality`/`-standards`/`-operations`/`-principles` gains independent citation corroboration** (MAR-303, ADR-0080). A new deterministic, stdlib-only helper, `citation_check.py`, re-opens every `Upstream inventory` citation the planner records and mechanically checks path containment plus a whitespace-normalized verbatim-excerpt match (`--plan <plan.md> --root <name>=<path> [--root …]`; exit 1 on any finding, exit 0 clean, exit 2 on usage error); the verifier's `plan-conformance` dimension runs this floor and then itself judges substantiation for every citation the script resolves. The 4 planners' `Upstream inventory` citation grammar now **mandates** a verbatim quoted excerpt per citation — a behavioral contract change to the planner charters, not merely additive. Every such finding — mechanical or semantic — and a script exit 2 are always `severity="blocking"`; there is **no** `severity="info"` carve-out. The mechanism folds into the existing dimension 4 (no 9th dimension); loop topology and `/acs:create-prd`'s own verifier are **unchanged**. `prd_path` is newly declared as a verify-task constraint on these 4 skills' verify tasks. **Migration:** none — no settings key, schema, state-file shape, or artifact-path change.
- **BEHAVIORAL CONTRACT CHANGE: `/acs:create-prd`'s dimension 7 "Plan conformance" gains independent, three-family corroboration** (MAR-304, ADR-0081, amends ADR-0004 append-only). A new deterministic, stdlib-only script, `prd_conformance_check.py`, imports `citation_check.py`'s `extract_citations`/`resolve_and_check` helpers unchanged (zero bytes of `citation_check.py` modified) to re-check brownfield `Code evidence` citations against the repo; independently re-derives every `answered`/`assumed` `clarifications.json` entry's population and asserts each has a dispositioned reflection anchor in `prd.md`/`roadmap.md` (or a ceiling-judged `N/A: <why>` escape, never silently accepted); and asserts every plan-declared roadmap milestone heading is bidirectionally consistent with the shipped `roadmap.md` — full bidirectional check in greenfield/brownfield, scoped to `--added-heading` values (from `git diff -- <prd_path>`) in amend mode. The verifier's semantic ceiling additionally judges "not contradicted," "substantiates," and "maps to the intended epic" for every finding the script resolves, including every `N/A`. Every such finding — mechanical or semantic — and a script exit 2 are always `severity="blocking"`, mode-conditional only for the code-evidence family (N/A, never a block, in greenfield). The mechanism folds into the existing dimension 7 (no new dimension; all 11 dimensions keep their names/numbers/order); `create-prd-planner.md`'s required-heading list gains three new sections (`## Code evidence`, `## Answer fidelity`, `## Roadmap milestones`) and their grammars; `clarifications.json` and the repo root are newly declared verify-task constraints. `citation_check.py`, its test harness, the 4 MAR-303 sibling skills' mechanism, and loop topology are all **unchanged**. **Migration:** none — no settings key, schema, state-file shape, or artifact-path change.
- **`/acs:create-prd`'s, `/acs:create-quality`'s, `/acs:create-standards`'s, `/acs:create-operations`'s, and `/acs:create-principles`'s reflection loops each drop the per-iteration re-plan and become execute → verify** (MAR-305). The planner now runs exactly once per run, before the loop, for all 5 bootstrap-doc skills — exactly one `<skill>-planner` subagent is spawned across the whole run, however many iterations it uses, with no intervening planner spawn on later iterations. On iteration 2+, verifier findings route straight to the executor's `<context>`, and the executor authors the remediation. The cap is **unchanged at 3** but now counts execute+verify rounds rather than plan+execute+verify triads. The resume path never spawns a second planner either. The 5 verifiers' independent-corroboration mechanism (`citation_check.py`, `prd_conformance_check.py`, and their test harnesses) is **unchanged** by this ticket. **Migration:** none — no settings key, schema, state-file shape, or artifact-path change.

## [0.4.7] - 2026-08-11

### Added

- **Epic: pay down hook-script coverage debt to the repo-wide 90% target (MAR-168, #318).** `plugins/acs/hooks/scripts` measured 62% at kickoff — well under the configured `test_coverage_percent` floor — because the suite drives most hook-script CLIs through `subprocess.run`, which `coverage.py` does not instrument by default. Six children close the gap and then flip this repo's own `Tests & coverage` CI check from diff-scoped to repo-wide enforcement:
  - **MAR-175 (#325 → 886f735)** — the measurement prerequisite: a committed `.coveragerc` (`parallel = true`, absolute `source`/`data_file`, an omit list for the 29 true argument-forwarder shims) plus `COVERAGE_PROCESS_START` wiring and `coverage combine` in `tests.command`. No test or production change — TOTAL jumps from 62% to ~88% purely because measurement becomes correct. Also lands the shared `tests/acs/acs_case.py` fixture every later child builds on.
  - **MAR-169 (#319 → 85bc2ef)**, **MAR-172 (#322 → afb4d48)**, **MAR-177 (#330 → 3ad8026)** — close the genuinely zero-coverage hook-script CLIs (`skill-start.py`, `new-ticket.py`, `codeowners.py`, `clarify.py`, `handoff.py`) to 100%.
  - **MAR-173 (#323 → 8ff6a42)** — closes the largest single residual gap, `acs_lib.py` (54% → 99%), with 91 new tests across settings resolution/validation, partition and lock handling, and the `run_pre`/`run_post` gate paths (lane derivation was already fully covered and needed none). Hook entry points that read `os.getcwd()` are driven exclusively as subprocesses, never in-process, to avoid corrupting the operator's real workspace during the test run itself.
  - **MAR-178 (#331 → 06979c3)** — the epic's last child: raises `statusline.py` and `subagent-statusline.py` (Claude Code's optional status-line renderers) from 84% each to 100%, covering the failure/fallback branches PRD G7's "never crash" contract requires. Also removes 3 lines of proven dead code in `statusline.py`'s `render()` (a `needs_design` branch that could never change its own output), found while writing the tests.
  - **MAR-174 (#324 → 927027e)** — flips `.acs/settings.json`'s `tests.command` from the diff-scoped `diff-cover` gate to the repo-wide `coverage report --fail-under=$ACS_COVERAGE` form now that every sibling child has closed its residual gap. Landed last, by design: the flipped command grades MAR-174's own PR, so the repo-wide ≥90% bar had to already hold on its base. Repo-wide TOTAL after the full epic: **96%** (up from 62% at kickoff).

### Fixed

- **`plugins/acs/schemas/acs-messages.xsd`'s `skillName` enumeration reconciled from 9 stale values to the 24 shipped skills plus a deliberately retained `create-spec` — 25 total (MAR-176, #327 → a00b2c7).** The same set is applied to `skill-state.schema.json` and `clarifications.schema.json`, which carried identical stale copies, and to `validate_xml.py`'s hardcoded `SKILLS` mirror. Concretely, skills such as `docs-sync` could not validate their own `<task>`/`<result>` messages even though their SKILL.md instructs the coordinator to do exactly that. A new bidirectional drift guard (`tests/acs/test_message_schema_skill_enum.py`) now fails on a shipped skill directory with no matching enum value, or an enum value with no matching directory, across all three schemas and the validator mirror.

## [0.4.6] - 2026-08-05

### Removed

- **`/acs:create-spec` is deleted outright** (MAR-156, ADR 0066, #300). Spec authoring folds into `/acs:code`'s plan phase on **every** lane, not just the fast lanes — the skill file, its three agent files, both hook scripts, and its `GATES`/`WORKFLOW_SKILLS` registry entries are gone. The review loop's fixed point moves from the spec set to `ticket.json`'s `acceptance_criteria`/DoD. Legacy partitions minted before the deletion still resolve: the `create-spec` anchors in `plugins/acs/hooks/**` and `plugins/acs/schemas/**` are retained deliberately for backward compatibility.

### Added

- **`/acs:docs-sync`, a new hooked skill** running after `/acs:code` (and `/acs:test` when the gate is active) and before `/acs:create-pr` (MAR-160, #305). It takes over the documentation work `/acs:code`'s execute step previously carried inline: the requirements-classification rubric, `.evidence.md` sidecar routing, and HLD / `lld/flows/` / ADR production.
- **`/acs:test` gains a ticket-scoped `--for-ticket` mode** plus a `/acs:ship` post-code fix-and-re-test loop, gated by e2e presence (MAR-159, ADR 0068, #303).
- **`create-ticket` now validates that acceptance criteria and DoD are substantive** rather than placeholder text (MAR-157, #301).
- **Oversized-ticket split detection has an owner again** (MAR-164, ADR 0069, #311). Two levers: `create-ticket`'s existing upfront PR-size rubric, plus a new **non-blocking** plan-time oversize signal in `code-planner.md` that surfaces through the clarification ledger and never halts a run. On a user "split" answer the `/acs:code` run ends `status="failed"` with a `/acs:create-ticket split <id>` next step.
- **`code-planner.md` gains a bounded ADR-0012 doc-graph-gap check** over the touched area only (edges E1–E4: component, data-model, flow, PRD/roadmap docs), carried on the existing `problems` channel to `/acs:docs-sync` (MAR-164, ADR 0012 third amendment). Explicitly *not* full design-time participation, and explicitly *not* a claim that docs-sync supersedes the design-time step.

### Changed

- **Default models updated to Opus 5; the `coordinator` model role is dropped** (MAR-154, #292).
- **`code-verifier` multi-lens adversarial rigor upgrade** for `verify_depth == "full"` only: four parallel lenses plus a coordinator adversarial merge pass (MAR-158, ADR 0067, #302). Light depth keeps today's single-subagent 13-dimension pass unchanged.
- **`/acs:code` no longer performs in-loop doc-sync**; its execute step's doc-authoring instructions are retired in favour of the new skill, and `code-verifier`'s documentation sub-checks are demoted to advisory — except the MAR-65 product-doc-consistency block, which stays blocking (MAR-162, ADR 0007 second amendment, #307).

### Fixed

- **Stale `/acs:create-spec` references swept repo-wide** across the doc set (MAR-161, #306), `docs/product/prd.md` (MAR-163, #310), and `plugins/acs/{skills,agents}/**` (MAR-164, #311) — the last down to five permanent past-tense provenance lines across three files. `handoff/SKILL.md`'s in-flight scan-order bullet, which named the deleted skill and omitted seven others, now references `acs_lib.HOOKED_SKILLS` instead of restating the list.
- **The stale `create-spec` routing row is out of the eval suite** and its 23→22 case-count cascade reconciled across two test modules and both product docs (MAR-165, #315). The brittle hardcoded count assertion now derives its expected values from the scenario source.
- **Roadmap reconciled for v0.4.5** (G38/G39 marked shipped) (MAR-153, #291).

## [0.4.5] - 2026-07-23

### Added

- **Relocate code-evidence citations into per-doc `.evidence.md` sidecars (MAR-152, ADR 0064).** Every code-cited `docs/requirements`/`docs/architecture` doc's inline repo-source `path:line` citations now relocate into a companion `<doc-basename-without-.md>.evidence.md` sidecar (clause-anchor -> `[path:line, ...]`, human-auditable markdown) instead of living inline in the human body — the body keeps a stable clause anchor with no raw source citation. Wired into `create-requirements-executor`/`-verifier`, `create-architecture-executor`/`-verifier`, and `/acs:code`'s requirements-merge step + `code-verifier`'s Documentation dimension: each producer writes body + sidecar, and each verifier actively checks grounding (body-grep-to-0, sidecar-exists, anchor-join, amend-mode count-not-reduced) rather than passively trusting the sidecar. The doc-enumerating `test_mermaid_diagrams.py` walk now excludes `*.evidence.md` sidecars via a shared `tests/acs/evidence_sidecar.py` predicate. This repo's own docs are dogfood-migrated — 3 files / 18 in-scope citations (`docs/architecture/lld/runtime-coupling-inventory.md` 16, `docs/architecture/lld/flows/tabp-usage-read.md` 1, `docs/requirements/functional/tabp.md` 1) — a ground-truth correction of the design's "~26+~7" estimate. A new `tests/acs/test_evidence_sidecar_topology.py` coverage/topology gate proves G37's 100%-code-cited coverage was relocated, never reduced, and that C-22 DRAFT/human-confirm-required markers are unaffected. This is an **intentional, non-byte-identical migration** — it rewrites the 3 committed docs above, distinct from ADR 0065's byte-identical template-default guarantee. Counts stay 24/45/49; no new skill/agent/hook/schema/settings key.
- **Configurable create-design/create-spec section templates with byte-identical built-in defaults (MAR-151, ADR 0065).** Two new `formats.design_template` (default `design-default`) and `formats.spec_template` (default `spec-default`) settings keys, plus their `enforcement.design_sections` / `enforcement.spec_sections` section companions, let a consumer repo tailor the design/spec section shape and the structure gate — resolved identically to the shipped `formats.pr_description_template` (built-in name → `.acs/templates/<name>.md` → absolute path). Two built-in template files (`plugins/acs/templates/design-default.md`, `spec-default.md`) carry the default headings. The built-in defaults encode today's exact required-section lists verbatim, so with no key set create-design/create-spec output and the structure gate are byte-identical to before (a guard test locks `default == today's literal`). This child adds the settings + template + doc/ADR foundation; the skill/verifier wiring and the net-new create-spec blocking `structure` gate follow in the same PR.

### Changed

- **Delete `/acs:create-spec`; generalize its fold into `/code`'s plan phase for every lane; relocate the review-loop fixed point to `ticket.json` (MAR-156, ADR 0066, supersedes ADR 0006).** `/acs:create-spec` (skill, 3 agent files, both hook scripts, its `GATES`/`WORKFLOW_SKILLS` entries) no longer exists; `gate_code` is now an unconditional pass-through gated only on `create-ticket` completed, on every lane. `code/SKILL.md`'s fast-lane fold generalizes from TRIVIAL/SMALL-only to every lane: the code-planner self-authors the five-section spec content whenever `<partition>/specs/` is absent or empty, and still reads pre-existing specs unchanged otherwise (backward-compat for in-flight tickets). The mid-code "Stage re-introduction" escalation step that re-spawned the create-spec triad is removed entirely, no stub. code-verifier's "Spec conformance" dimension is replaced by "Acceptance-criteria conformance" — `ticket.json`'s `acceptance_criteria`/DoD re-read fresh every iteration, never the current plan artifact's restatement (the new review-loop fixed point); design-conformance folds into the existing Architecture/System-design dimensions; completeness and structure become dimension-1 sub-checks; consistency is retired (a folded artifact has no cross-file surface left to be inconsistent with); a new standalone blocking dimension 13 "Audience-style" judges the folded plan artifact's prose. `ship/SKILL.md`'s pipeline-order table and "Picking the next step" collapse to one lane-uniform walk order (`create-ticket → [create-design] → code → create-pr`), with zero remaining create-spec references. `pipeline-state.schema.json`'s `steps` enum and `settings.schema.json`'s `formats.spec_template`/`enforcement.spec_sections` keys are dropped; the append-only schema enums that still enumerate skill names elsewhere (`acs-messages.xsd`, `clarifications.schema.json`, `skill-state.schema.json`) and the statusline cosmetic maps are deliberately left untouched, for backward-compat with tickets minted before this change. The spec-time simplicity-evaluation gate (ADR 0037-0039) migrates into `code-planner.md`'s own decompose step rather than being retired.
- **Promoted the `audience-style` verifier dimension from advisory to BLOCKING and extended it to create-spec, with a clarify-ledger waiver path (MAR-150, ADR 0063).** The `audience-style` register check is now a blocking gate across the 8 producer verifiers that declare an `audience_style_profile` (create-design, create-prd, create-architecture, create-requirements, create-standards, create-quality, create-operations, create-principles) — reversing ADR 0057's advisory carve-out (`severity="info"`, "except the advisory"/"except the sanctioned") in each charter. `create-spec` gains the gate net-new: `create-spec/SKILL.md` declares an `audience_style_profile` (`engineers (implementation-contract prose)`) forwarded into its verify task, and `create-spec-verifier.md` adds a blocking `audience-style` dimension. A waiver safety valve reuses the existing clarification ledger — a register the coordinator records via `clarify.py --source assumption` is waived (emitted `severity="info"`) and does not block, so the pass bar is 0 **unwaived** audience-mismatch findings per run. The anchored per-skill profile mechanism (ADR 0057's hybrid) is retained — no deterministic style helper is added. create-project stays N/A; counts stay 24/45/49. The `tests/acs/test_structure_audience_verifiers.py` guard is rewritten from the advisory contract to the blocking contract.
- **Codified the "test filenames name the behavior, never a ticket id" convention and swept the existing suite to match (MAR-147).** The standing "never a ticket id in source" rule now explicitly extends to test module filenames: a test file is named by the component/behavior under test, never by a ticket id — the originating `MAR-<NNN>` reference lives in the module docstring instead. The rule is stated across the five pipeline guidance surfaces (the `code` and `create-spec` skills plus the `code-executor`, `code-planner`, and `create-spec-planner` agents) and in a new first-class `docs/standards/standards.md`, and is enforced by a new `tests/acs/test_test_naming_convention.py` guard. The 49 pre-existing `test_mar<NNN>_*.py` modules were renamed to component/behavior names as content-preserving `git` renames (class names, methods, assertions, and each module's own docstring ticket ref unchanged), with their inter-test docstring cross-references updated to the new names.

### Documentation

- Amended the PRD to add goals **G38** (readable, audience-aware, evidence-clean docs) and **G39** (configurable design/spec templates) ahead of building them (MAR-148, #279), and reconciled the roadmap's release-versions mapping after the v0.4.4 cut (MAR-146, #276).

## [0.4.4] - 2026-07-16

### Added

- **New `/acs:create-requirements` skill + functional/non-functional requirements model (G37 epic, MAR-142).** A new product-level producer skill bootstraps, elicits, or amends the living-requirements doc set, and `settings.requirements_path` now resolves a functional/non-functional split shared with `/acs:code`. Delivered as three children:
  - **Functional/non-functional settings-aware requirements model foundation (MAR-145, #272).** A new additive `requirements_layout` settings key (`functional_subdir`/`non_functional_subdir`, default `"functional"`/`"non-functional"`) lets `settings.requirements_path` resolve a functional and a non-functional subfolder. `/acs:code`'s requirements-merge step now classifies each merged requirement against a written functional-vs-NFR rubric (behavior vs. quality, default-to-functional tie-break) and routes it into the matching subfolder — the additive, per-area, no-overwrite merge semantics are unchanged, only the target subfolder is new. Documented in `docs/architecture/lld/contracts.md` and ADR 0060; requirements stays a living contract alongside the conformance chain, not a new verified level.
  - **Skill core + brownfield reverse-engineer mode (MAR-143, #273).** The skill reverse-engineers the `requirements/` doc set from an existing codebase — architecture-aware feature-area enumeration (`c4-container.md`/`c4-component.md`/`project-structure.md` when present, a codebase-inventory fallback otherwise), each extracted requirement DRAFT / human-confirm-required and code-cited, classified functional-vs-non-functional against the same rubric `/acs:code` uses and written into the settings-resolved `functional/`/`non-functional/` subfolders (augment-only-absent — never overwrites an existing area file). An interactive-confirm step presents the DRAFT baseline and any `[OPEN]` (ungroundable) points via the clarify ledger before the executor writes; the verifier gates on ≥90% coverage, 100% code-citation, and 0 silent omissions. See ADR 0061.
  - **Greenfield elicitation + uniform DRAFT discipline (MAR-144, #274).** The greenfield mode is now a real elicitation branch (mirroring `/acs:create-prd`'s greenfield mode) — when there is no meaningful codebase and the requirements set is absent, the skill elicits behavior/quality from the user, writes one `functional/<feature>.md` per behavioral feature and one `non-functional/<item>.md` per NFR item DRAFT-marked and cited to the user's answer (no code-citation expected), completing the brownfield/greenfield/amend three-mode set. The DRAFT / human-confirm-required, interactive-confirm discipline is now stated uniformly across all three modes (C-22), and the per-file functional/non-functional format is finalized (DRAFT marker + `MUST`/`SHOULD`/`MAY`/`[OPEN]`/`[ASSUMPTION]` prose, no new template). `docs/architecture/lld/contracts.md` now documents requirements as a living contract alongside the (unchanged) verified conformance chain, not a new chain level (Decision D1). See ADR 0062.

### Documentation

- Amended the PRD to add goal **G37** (brownfield requirements extraction / `/acs:create-requirements`) ahead of building it (MAR-140, #266), reconciled the roadmap's release-versions mapping after the v0.4.3 cut (MAR-139, #265), and deferred team-shared delivery state (G23) to post-GA behind a new M8 milestone (MAR-141, #267).

## [0.4.3] - 2026-07-14

### Added

- **Verifier-enforced generated-doc quality: readable, audience-aware structure + syntactically-valid Mermaid diagrams (G36 epic, MAR-136).** The doc-producing skills now enforce documentation quality on their own generated output — in any consumer repo, driven by each skill's own definition. Delivered as two children:
  - **Diagram-lint gate: 0 Mermaid syntax errors, verifier-enforced (child A, MAR-137, #262).** The heuristic Mermaid linter now ships inside the plugin at `plugins/acs/hooks/scripts/mermaid_lint.py` (promoted from `tests/acs/mermaid_lint.py`, same rule set and `lint_text`/`lint_file`/`Finding`/`main(argv)` API), so it travels to any consumer repo with acs installed. The `create-architecture` and `create-design` verifiers both invoke it via `${CLAUDE_PLUGIN_ROOT}/hooks/scripts/mermaid_lint.py` and treat any finding as a **blocking** failure — replacing the prior soft structural/grep check (architecture, dimension `mermaid-diagrams`) and "syntactically plausible" LLM judgment (design, dimension `completeness`) with a deterministic 0-syntax-error gate. The marketplace's own pre-commit hook and CI keep linting every committed doc via the repointed plugin path (ADR 0055).
  - **Structure/section-conformance floor (blocking) + audience-style gate (advisory), verifier-enforced (child B, MAR-138, #263).** Every one of the 7 prose-doc skills (`create-prd`, `create-architecture`, `create-design`, `create-principles`, `create-standards`, `create-quality`, `create-operations`) now declares its `required_sections` and an `audience_style_profile` in its own SKILL.md and passes both into its verify task. Each verifier gains two appended dimensions: a deterministic `structure` dimension invoking the new `plugins/acs/hooks/scripts/structure_lint.py` (stdlib-only; presence, non-empty, and declared-order checks) as a **blocking** gate, and an `audience-style` dimension that judges register/style against the declared profile as an **advisory** (`severity="info"`, never blocking) gate. `create-project` is explicitly N/A (its scaffold/manifest completeness check is its structure-conformance analog) — locked by a negative contract test (ADR 0056, ADR 0057).

### Documentation

- Amended the PRD to add goal **G36** (generated-doc readability + valid diagrams) ahead of building it (MAR-135, #258), and reconciled the roadmap's release-versions mapping after the v0.4.2 cut (MAR-134, #257).

## [0.4.2] - 2026-07-13

Delivers the **G17 epic** (first-class release versions + one-command release
cut) and the **consumer-general skills** program (every acs skill is
settings-driven and repo-agnostic — no skill hardcodes this marketplace's own
layout). This is the first release cut by the new `/acs:release` skill itself.

### Added

- **First-class release versions + one-command release cut (G17, epic MAR-128).**
  - **Settings-driven `/acs:release` cut skill (MAR-129, #251).** A new unhooked
    utility skill plus a stdlib-only `release_notes.py` helper that
    authoritatively drafts the `## [<version>]` CHANGELOG section from the
    merged-ticket archive since the last tag — cross-checked against
    `[Unreleased]` with a coverage report (N merged / M covered / K missing),
    never a silently empty section when >=1 ticket merged (defeats the v0.4.1
    empty-notes bug). The cut is **settings-driven / consumer-general**: a new
    `.acs/settings.json` `release` block declares which files hold the version
    (JSON pointers), the `source.ref`/extra-ref locations, the changelog path,
    tag format, base branch, and publish driver — this marketplace is
    configured as **profile #1**, and any JSON-manifest consumer repo can
    configure its own release. It bumps the version in both manifests +
    `source.ref` and opens an exempt `release/*` PR that **stops for a
    mandatory human merge**; the skill never tags or publishes itself, and the
    existing `release.yml` workflow (the profile's publish driver) is reused
    unchanged. Skill count 22->23; `UNHOOKED_SKILLS` 8->9 (`HOOKED_SKILLS` 14,
    `GATES` 14, agent files 42 unchanged). ADRs 0050-0054.
  - **First-class release versions in the create-prd roadmap (MAR-130, #255).**
    `/acs:create-prd` now authors and verifies a "Release versions" mapping
    table in `roadmap.md` (each release version -> the milestone(s)/epic(s) it
    delivers), with a verifier coverage sub-check that every committed
    milestone resolves to exactly one release version (0 orphan milestones).
    Additive and non-breaking (C-8); decoupled from the cut skill (ADR 0053).
- **Consumer-general skills (PRD amendment + engineering principle).**
  - **PRD constraint C-20 (MAR-132, #252).** Generalizes C-16 to all skills:
    every acs skill is consumer-repo-general and settings-driven, operating on
    the invoking repo via `.acs/settings.json` and never hardcoding this
    marketplace's own artifacts.
  - **Engineering-principles doc set (MAR-133, #254).** Stands up the repo's
    first `docs/principles/` doc set (activates `principles_path`) with the
    **Consumer-repo generality** principle — the verifier-enforceable form of
    C-20.

## [0.4.1] - 2026-07-12

### Added

- **Enforceable e2e integrity (G13) — epic MAR-124 (E2E-1 → E2E-3).** acs gains an
  opt-in, fail-closed e2e merge gate plus brownfield onboarding for it, and validates
  the G13 metric — everything guarded on `settings.e2e`/`suites.e2e` being configured
  (unset ⇒ zero new behavior). Delivered as three reviewed children:
  - **E2E-1 — required e2e merge gate (MAR-125).** New committed CI-workflow pair
    `plugins/acs/templates/ci/acs-e2e.yml` + `run-e2e.py` (stdlib runner resolving
    `suites["e2e"]` or the raw top-level `e2e` alias; fail-closed conclusion),
    mirroring the existing tests gate. `/acs:init` gains **Step 7f**, which auto-wires
    the `acs-e2e` required status check into branch protection via `gh api` when e2e
    is configured and the authenticated user is a repo admin, with a **report-once**
    manual-step safeguard otherwise. No new settings key. Makes `/acs:merge-pr`'s
    report-only CI read enforceable (documentation-only merge-pr change).
    ADRs 0045/0046/0047.
  - **E2E-2 — brownfield e2e scaffolding (MAR-126).** `/acs:standardize-project`
    additively scaffolds the `acs-e2e.yml` + `run-e2e.py` templates into an existing
    repo (`A`-status file adds only, opt-in, never overwrites an existing workflow,
    never wires branch protection), surfacing the wire-via-`/acs:init` step as a
    recommended follow-up. ADR 0048.
  - **E2E-3 — measured G13 metric (MAR-127).** Read-only validation of the G13 metric
    from existing artifacts (no new mechanism, no metrics panel) with an honest
    dogfood recording, plus product-doc reconciliation. ADR 0049.

## [0.4.0] - 2026-07-11

### Added

- **`/acs:create-principles` skill + `principles_path` settings key
  (MAR-117).** A new product-level, triad-keeping skill that bootstraps and
  maintains the consumer `principles/` doc set — `principles.md`
  (engineering principles + rationale) — reading the PRD and the
  `architecture_path` set as upstream (principles is itself upstream of
  `standards/`), delivered as a docs-only PR on its own delivery ticket
  (`create-principles-planner`/`-executor`/`-verifier`,
  `create-principles-state.json`). `principles_path` is added to
  `settings.schema.json` (optional `string | null`, default
  `docs/principles`, mirroring `quality_path`/`operations_path`) and
  defaulted by `/acs:init`'s Step-4 batch; one new coarse template ships
  under `plugins/acs/templates/principles/`.

- **`/acs:create-standards` skill + `standards_path` settings key
  (MAR-118).** A new product-level, triad-keeping skill that bootstraps and
  maintains the consumer `standards/` doc set — `coding-standards.md`,
  `conventions.md` (naming/layout/formatting), and `review-checklist.md` —
  reading the PRD, the `architecture_path` set, and the `principles_path`
  doc set (when set and present) as upstream, gracefully degrading when
  `principles_path` is unset or absent (`create-standards-planner`/
  `-executor`/`-verifier`, `create-standards-state.json`), delivered as a
  docs-only PR on its own delivery ticket. `standards_path` is added to
  `settings.schema.json` (optional `string | null`, default
  `docs/standards`, mirroring `principles_path`/`operations_path`) and
  defaulted by `/acs:init`'s Step-4 batch; three new coarse templates ship
  under `plugins/acs/templates/standards/`.

- **Conformance-chain extension: standards conformance checked by design +
  code verifiers (MAR-119).** `code-verifier`'s dimension 7 "Technical
  standards" is re-anchored to read the `standards/` doc set at
  `standards_path` as the source of truth (falls back to documented
  architecture when unset); `create-design-verifier`'s `consistency` and
  `nfr` dimensions gain a matching `standards` sub-check against the design
  decisions a `design.md` introduces (`dimension="standards"` findings).
  Both verdicts BLOCK only on changeset-introduced standards violations
  (`severity="blocking"`) and SURFACE pre-existing violations as flagged
  notes, never a silent waiver. `standards_path` is wired into both
  verifiers' `<constraints>` (present only when set), mirroring
  `architecture_path`/`adr_path`. The conformance chain extends to `PRD →
  architecture → principles → standards → design → specs → code` across
  `contracts.md`, `hld/overview.md`, `requirements/overview.md`,
  `requirements/workflow.md`, and `docs/README.md`. Traces **G10**
  (standards conformance & repo standardization).

- **`/acs:create-architecture` gains a `hld/project-structure.md` output
  (MAR-120).** The Output-contract table gains a standing row: the intended
  repo layout derived from the C4 container/component views, rendered as a
  Mermaid `flowchart` in directory-tree style — the canonical target
  `/acs:standardize-project` will audit an existing repo against. The
  addition ripples across `create-architecture-planner`/`-executor`/
  `-verifier` (Target doc set, doc-set list, and doc-set-completeness +
  C4-traceability checks) and is purely additive — every pre-existing
  Output-contract row and the Re-run mode's additive semantics are
  unchanged. Traces **G10**.

- **`/acs:standardize-project` skill — brownfield audit-and-scaffold
  (MAR-121).** A new triad-keeping workflow skill (not a `<set>_path`
  doc-set producer) that audits an EXISTING repo's `principles_path`,
  `standards_path`, `hld/project-structure.md`, and acs-readiness tooling,
  then additively scaffolds ONLY the missing docs/config/tooling as one
  reviewed PR — it never moves, renames, deletes, or rewrites existing
  source (`standardize-project-planner`/`-executor`/`-verifier`,
  `standardize-project-state.json`). The verifier re-runs
  `git diff --name-status` independently every iteration via a new
  `classify_additive_diff` helper and blocks on any `R`/`D` status or `M`
  outside the additive-surface allowlist (D6). Structural gaps outside the
  allowlist surface as `recommended_follow_ups` entries in the completion
  report and PR body — never auto-minted as tickets (D7). Each run creates
  its own delivery ticket (type `task`, "Brownfield project
  standardization"); no new settings key. Traces **G10**.

- **Epic complete — repo standardization & conformance (G10): MAR-117 →
  MAR-121.** `/acs:create-principles`, `/acs:create-standards`, and
  `/acs:standardize-project` together complete the standards-conformance
  epic (the `architecture → principles → standards → design → specs →
  code` conformance chain wired by MAR-119). Epic-final totals: 22 skills,
  42 agent files, 36 reachable agents, eleven triad-keeping skills.

### Fixed

- **Docs: refreshed stale reflection-topology counts across the acs docs
  (MAR-123).** INTERNALS, overview, roadmap, reflection, and prd now state
  the live-derived topology (22 skills, 42 agent files, 14 hooked skills, 11
  triad-keeping skills → 36 reachable agents, 6 orphaned apply-work
  planner/verifier files) after the producer-skill additions; a new
  `tests/acs/test_mar123_docs_topology.py` derives the counts live and pins
  the docs so the figures cannot silently drift again. Docs-only; no plugin
  behavior change.

- **`/acs:create-quality`, `/acs:create-operations`, `/acs:create-principles`,
  and `/acs:create-standards` no longer fail closed on every run (MAR-122).**
  The four doc-set producer skills were registered in `HOOKED_SKILLS` but had
  no entry in the `GATES` dict, so `run_pre`'s bare `GATES[skill]` subscript
  raised `KeyError`, caught by the fail-closed handler as exit 2 "unexpected
  error in gate" — blocking all four skills end-to-end in any hooked repo.
  Each now has its own registered gate requiring the architecture doc set
  (`hld/tech-stack.md`, mirroring `gate_create_project`), so a ready repo
  passes (exit 0) and a repo missing the architecture set gets the same
  actionable `GateError` message the other doc-set producers already give.

## [0.3.8] - 2026-07-07

### Added

- **`/acs:create-quality` skill + `quality_path` settings key (MAR-112).** A
  new product-level, triad-keeping skill that bootstraps and maintains the
  consumer `quality/` doc set — `test-strategy.md` and `coverage-policy.md`
  — reading the PRD's non-functional requirements and the `architecture_path`
  set as upstream, delivered as a docs-only PR on its own delivery ticket
  (`create-quality-planner`/`-executor`/`-verifier`, `create-quality-state.json`).
  `quality_path` is added to `settings.schema.json` (optional `string | null`,
  default `docs/quality`, mirroring `adr_path`) and defaulted by `/acs:init`'s
  Step-4 batch; two new templates ship under `plugins/acs/templates/quality/`.
- **`/acs:create-operations` skill + `operations_path` settings key (MAR-113).**
  A new product-level, triad-keeping skill that bootstraps and maintains the
  consumer `operations/` doc set — `release-process.md`, `runbooks.md`,
  `observability.md`, `incident-response.md`, and `test-scheduling.md` —
  reading the PRD's non-functional requirements and the `architecture_path`
  set as upstream, delivered as a docs-only PR on its own delivery ticket
  (`create-operations-planner`/`-executor`/`-verifier`,
  `create-operations-state.json`). `operations_path` is added to
  `settings.schema.json` (optional `string | null`, default
  `docs/operations`, mirroring `quality_path`) and defaulted by
  `/acs:init`'s Step-4 batch; five new templates ship under
  `plugins/acs/templates/operations/`.
- **`/acs:test` skill + `suites` settings key generalization (MAR-114).** A
  new unhooked, model-invocable utility skill that runs the product's
  configured test suites (all, or a `--suite`-selected subset), writes an
  auditable results artifact, and closes the loop on failures by minting,
  comment-bumping, or linking a regression ticket via direct `new-ticket.py`
  reuse. The `suites` settings key generalizes the existing `e2e` setting
  into a named-command map — `e2e` is retained as a soft-deprecated,
  load-time-normalized compatibility alias into `suites["e2e"]`, and
  `/acs:init` offers a one-time `e2e` to `suites.e2e` migration on re-run.
- **Shared ADR-0012 design-time doc-consistency step (MAR-115).** A single
  canonical analysis step, transcribed byte-identically into the planner
  phase of all six design-producing skills' planners
  (`create-prd`/`create-architecture`/`create-design`/`create-spec`/
  `create-quality`/`create-operations`): read the upstream and downstream
  doc-graph slice, detect gaps and staleness, and surface findings — the
  fixed shape `{kind: "gap"|"staleness", upstream, downstream, description,
  recommendation}` — through the existing clarification ledger; the user
  decides, the executor updates the affected docs as part of the same
  change, and the verifier confirms consistency. `create-quality-verifier`
  and `create-operations-verifier` each gain a matching sixth `consistency`
  check dimension. Internally, `plugins/acs/hooks/scripts/consistency_findings.py`
  is a new stdlib-only helper that validates a finding against this shape.
  ADR 0012 is flipped from `Proposed` to `Accepted`.

## [0.3.7] - 2026-07-06

### Added

- **`/acs:metrics` surfaces the G25 escalation metric on the delivery
  summary (MAR-109).** An additive `escalations` sub-object on the existing
  `delivery_summary` panel — no new panel key — reporting four tallies:
  total escalation events, count of fast-lane (TRIVIAL/SMALL-origin) tickets
  that escalated to ≥STANDARD (per-ticket, not per-event), de-escalation
  count, and silent-reversal count (down-direction events lacking a
  `confirmation_ref`; 0 on well-formed state). Computed from the
  `escalations` arrays already visited in the existing bounded single-pass
  workspace walk — no new state surface, no extra file read. Renders on both
  `/acs:metrics` surfaces (terminal and HTML); an absent/empty escalations
  array renders every tally as `0`, not "no data".

- **`/acs:code` gains a user-confirmed mid-flight de-escalation path, never
  automatic (MAR-108).** A new `acs_lib.py` writer, `confirm_deescalation`,
  is the only function capable of lowering a ticket's `size`/`stakes`/`lane`
  below its current confirmed value; it hard-requires a resolved, *answered*
  `clarify.py` ledger entry (an `"open"` or agent-authored `"assumed"` entry
  is refused, same as a missing one — `ValueError`, no write), recomputes
  `lane` via `derive_lane`, persists exactly like the upward path, and then
  records a `direction:"down"` audit event with a non-null `confirmation_ref`.
  It is reachable only from a boundary-only, explicitly user-confirmed
  subsection of the `/code` coordinator — never from the in-loop
  trigger-evaluation path or any subagent — so the upward-only negative
  guarantee holds for every automatic/unattended path.

- **`/acs:code`'s iteration-start escalation detection point and
  fold-boundary stage re-entry are now a formalized, contract-tested
  guarantee (MAR-107).** The shipped detection point (start of each
  iteration, after the prior verifier, before the current execute) is now
  named and tested so an escalation always lands before the next verifier
  pass; the monotone never-lowered ceiling raise, the no-restart guarantee,
  and the fast-lane-to-full-lane `create-spec` re-introduction are all
  contract-tested. Zero behavior change — no `acs_lib` function is modified.

- **`/acs:code`'s in-loop escalation now writes a durable audit-event trail
  and freezes its signal set (MAR-106).** A new `acs_lib.py` helper
  `record_escalation_event(tdir, skill, event)` appends a fixed 13-field event
  (from/to lane, from/to axes, trigger, source, ceiling before/after,
  direction, confirmation ref) to `runs[-1].escalations` on `code-state.json`,
  called from step (f) of the on-trigger escalation sequence after the
  axis/lane persistence — replacing the prior free-text coordinator note. The
  three shipped escalation triggers are normatively frozen, with the
  `high_stakes_paths` glob match as the sole deterministic, unit-tested
  signal; no new deterministic scope heuristic is introduced.

### Fixed

- **`/acs:init`'s CLAUDE.md managed-block writer (`upsert_managed_block`) now
  ends the file with exactly one trailing newline on every path, so a
  consumer `CLAUDE.md` no longer trips pre-commit's `end-of-file-fixer`
  (MAR-104).**

## [0.3.6] - 2026-07-05

### Added

- **`/acs:create-pr` requests CODEOWNERS-derived reviewers and syncs the
  remaining Project fields (MAR-103).** A new stdlib-only `codeowners.py`
  helper resolves PR reviewers from the repo's CODEOWNERS file
  (last-match-wins, team-slug-aware); the PR author is always dropped, and
  an empty or author-only result skips gracefully with an info finding
  instead of a hard failure. `/acs:create-pr` and `/acs:create-ticket` also
  sync Priority, Story Points, and Parent to the board's matching named
  Project field (fixed case-insensitive table, type-driven value mapping);
  a schema-undefined field is surfaced as an info finding, same as the
  existing Type/Status fallback.
- **`/acs:create-pr` moves the ticket's Project Status to In Review (MAR-102).**
  The tracker-metadata-fill Status-set call resolves the in-review option by
  case-insensitive name (`In Review`, then `Review`) on both the create and
  edit paths. When the board defines no such option, an info finding names
  it and how to add it; Status is left unchanged and the PR is unaffected.

## [0.3.5] - 2026-07-04

### Changed

- **`/acs:create-spec` gains a spec-time simplicity gate (MAR-88).** The
  planner evaluates each decomposition for a **materially** simpler
  alternative meeting the **same acceptance criteria**; the coordinator
  **surfaces** (never blocks) a finding for the user's **decision** —
  deconflicted from `code-verifier` dim. 12, planner-charter-only.

### Added

- **`/acs:create-pr` now sets PR assignee, ticket-type label, and GitHub
  Project membership (MAR-101).** For github-tracker-synced tickets, on both
  the create and edit paths, the PR carries assignee = PR author (via `gh`'s
  `@me`), the ticket-type label alongside `ACS` (idempotent creation), and is
  added to the configured GitHub Project with Status set; a schema-undefined
  Project field is surfaced as an info finding, not silently skipped.
  `local`/unsynced tickets are unaffected; a failed `gh` metadata call is
  surfaced as a finding and never aborts the PR.

## [0.3.4] - 2026-07-03

### Added

- **`/acs:init` offers version-pinned per-role models, per-role effort, and an
  explicit e2e choice (MAR-89).** A fresh `/acs:init` now actively offers, as
  first-class setup prompts: version-pinned model ids (`claude-opus-4-8` /
  `claude-sonnet-5`) for all four roles (planner/executor/verifier/coordinator)
  instead of only the coarse `opus`/`sonnet` tiers; per-role reasoning effort
  (`low|medium|high|xhigh|max|inherit`) as an explicit choice, including the
  coordinator-scope caveat; and the e2e suite as an explicit, candidate-detected
  offer rather than a silently-defaultable Step 4 key — so no user-settable
  configuration is reachable only by hand-editing `.acs/settings.json` (goal
  G21). Prose-only change to `init/SKILL.md` guarded by a new prose-contract
  test; no settings-schema, model-id/effort-validation, or broader guided-flow
  changes (those remain v0.4.0).

### Changed

- **`/acs:code` enforces Simplicity First + Surgical Changes restraint layer
  (MAR-2).** The code-executor's Charter gains two named authoring rules:
  **Simplicity First** (minimum code that solves the spec — no speculative
  features, no single-use abstractions, no unrequested configurability, no
  impossible-case error handling; if 200 lines can be 50, rewrite; apply the
  "would a senior engineer call this overcomplicated?" check) and **Surgical
  Changes** (every changed line traces to the spec; do not refactor or reformat
  adjacent code; only remove orphans your own change created; mention but never
  delete pre-existing dead code). The code-planner's file-map step now directs
  the minimal change surface and prohibits speculative scope. The
  code-verifier gains a new blocking **Simplicity & scope** dimension (dimension
  12) that flags overcomplication and out-of-scope edits as blocking findings
  looped back to the executor. Mirrored in the `/acs:code` SKILL doc and the
  shared requirements docs (skills.md, reflection.md). Generalizes the v0.3.1
  minimal-comment policy from comments-only to a full authoring-discipline
  contract.
- **`/acs:code`, `/acs:create-ticket`, `/acs:create-pr`, `/acs:merge-pr`
  reconcile the acs ticket id with the GitHub issue/PR (MAR-75).** Tracker
  sync now cross-references the acs ticket id and its GitHub records
  bidirectionally and GitHub-natively. `/acs:create-ticket` Step 5 stamps the
  acs ticket id on the synced issue body (`acs-ticket: {ticket_id}`, via the
  task/story/epic description templates) and fills the issue's GitHub fields —
  `ACS` + type labels, assignee when known, milestone when the repo uses one,
  and applicable Project fields (Status, Type) — surfacing, never silently
  skipping, a field the Project schema does not define. `/acs:create-pr` adds a
  native `Closes #<external.key>` bullet to the PR body's `## Ticket` section
  (so GitHub auto-links and auto-closes the issue on merge) and passes
  `--milestone` when one is used. `/acs:merge-pr`'s issue-close comment now
  carries the acs ticket id and a PR back-reference
  (`Merged {ticket_id} via PR #{pr.number} — {pr.url}`). `local`/unsynced
  tickets are unaffected; no enforced `pr_title`/`branch_name`/`commit_message`
  format string and no placeholder vocabulary changed.
- **`/acs:create-pr` renders the PR title from the tracker's native reference
  when the ticket is synced (MAR-80).** A new `{ticket_ref}` token for
  `formats.pr_title` renders `[#<issue-number>]` for a GitHub-synced ticket
  (`[<JIRA-KEY>]` for Jira) and falls back to the local acs ticket id
  (`[<ticket_id>]`) when unsynced — via a new `compute_ticket_ref` helper and a
  `--provider` flag threaded through the render-title call sites in the four
  tracker-aware skills; `branch_name` and `commit_message` stay id-based. The CI
  convention checker (`check-conventions.py`) and `acs_lib.validate_formats`
  both learn the `{ticket_ref}` token so the rendered title still passes the
  enforced conventions, and the default `pr_title` becomes
  `[{ticket_ref}] {title}`. Decisions recorded as ADRs.

### Fixed

- **`/acs:create-ticket` now syncs every fanned-out epic child to the tracker,
  not just the root ticket (MAR-84).** Epic children minted during Step 4 fan-out
  were never pushed to GitHub/Jira — Step 5's sync sequence only ever ran once,
  for the root, leaving every child's `external` `null`. Step 5 (both
  `create-ticket/SKILL.md` and `create-ticket-executor.md`) now defines a
  "tickets to sync" set (`root, unless imported` + `every child minted in Step
  4`, excluding product-flow delivery titles) and wraps the existing
  `gh`/`acli` sequence in a per-ticket loop, reusing the field-fill checklist
  verbatim for each ticket. A new stdlib-only helper,
  `plugins/acs/hooks/scripts/record-external.py`, is the deterministic write
  seam that stamps `external = {provider, key}` into one ticket's own
  `ticket.json` (and refuses, as defense in depth, to write onto a
  product-flow ticket). A per-ticket `gh`/`acli` failure is surfaced as a
  finding naming the ticket id and error and no longer aborts the rest of the
  batch — the loop continues, and the failed ticket's `external` stays `null`
  for a later retry. Product-flow delivery tickets ("Product definition
  (PRD)", "Product architecture doc set") remain unsynced by design.

## [0.3.3] - 2026-07-01

### Fixed

- **`/acs:init` now detects and auto-repairs a consumer `CLAUDE.md` that an
  earlier buggy run corrupted, and reports the repair.** v0.3.2 stopped the writer
  from *producing* a doubled block, but a repo already carrying a doubled or
  orphaned block (e.g. `2 BEGIN / 3 END` from the old `find`-based non-idempotency)
  still needed a human to hand-edit it. Step 7e now reads `CLAUDE.md` before
  writing, and when the new pure detector `acs_lib.managed_block_is_malformed`
  reports marker counts other than one `<!-- BEGIN acs-managed … -->` / one
  `<!-- END acs-managed -->`, the same `upsert_managed_block` collapses the entire
  span (first `BEGIN` → last `END`, `rfind`) to a single clean pair and
  `_strip_stray_markers` scrubs any orphan marker left in the surrounding text, so
  no doubled block or orphan `END` survives the next run. The step prints
  `repaired malformed acs-managed block in CLAUDE.md (was N BEGIN / M END -> 1/1)`
  and surfaces the repair in the completion report's Results/Findings, so a repair
  is never mistaken for a routine refresh. A first-time insert into a block-less
  `CLAUDE.md` is correctly reported as a normal write, not a repair. The heal
  preserves the user-owned content before and after the block byte-for-byte and is
  itself idempotent. Re-run `/acs:init` once to collapse any lingering corruption.

## [0.3.2] - 2026-07-01

### Fixed

- **`/acs:init` no longer writes a doubled, non-idempotent acs-managed block into
  the consumer `CLAUDE.md`.** Step 7e used to read the whole `CLAUDE.acs.md`
  template — which already ships a complete block (maintainer header + its own
  `BEGIN`/`END` markers) — and wrap it in a *second* marker pair, producing two
  `<!-- BEGIN acs-managed … -->` and two `<!-- END acs-managed -->` with the
  header sandwiched between them. Re-running degraded the file further because the
  writer located the closing marker with `find` (the inner `END`), orphaning the
  outer one. The writer now injects only the guidance **body** (new
  `acs_lib.managed_body_from_template`, which drops the header and the template's
  own markers) wrapped in exactly one pair, and `upsert_managed_block` locates the
  span with `rfind` and defensively strips any stray markers from the body. Result:
  a fresh write yields a single clean pair, re-runs are byte-identical, and a
  pre-existing doubled/legacy block self-heals to one clean pair — all while
  preserving the surrounding user-owned content byte-for-byte. Step 7e also gains a
  post-write self-check asserting a single marker pair. Re-run `/acs:init` to
  collapse an already-doubled block in an existing repo.

## [0.3.1] - 2026-06-29

### Changed

- **CLAUDE.md managed block now steers ticket work to `/acs:code` / `/acs:ship`
  and explains why hand-made PRs fail the gate.** The `/acs:init`-installed
  guidance (`CLAUDE.acs.md`) tells the assistant to implement/code a ticket via
  `/acs:code <ticket-id>` (or `/acs:ship`) and let `/acs:create-pr` open the PR,
  never a raw `gh pr create`. It makes the mechanism explicit: the pipeline
  renders the branch/title/body/label from **the project's own**
  `.acs/settings.json` formats, and the CI convention gate validates against the
  same file — so a pipeline-produced PR passes by construction while a hand-made
  one bypasses the rendering and fails. Re-run `/acs:init` to refresh the block
  in an existing repo.

- **`/acs:code` writes minimal, idea-only code comments (token discipline).**
  The code-executor now writes at most one short single-responsibility line per
  new function/class (SOLID — one unit, one job), never puts a ticket id in
  source comments or docstrings, and on edits only touches a comment the change
  actually invalidates (e.g. a changed parameter) — no re-comment passes over
  unchanged logic. Mirrored in the code-planner's documentation map and the
  `/acs:code` SKILL doc step. The `commit_message` format (which carries the
  ticket id) is unchanged.

- **Corrected stale agent-topology references to the post-MAR-60 shape.**
  `docs/requirements/overview.md` and `plugins/acs/docs/INTERNALS.md` no longer
  describe the old "27 subagents / 9 planner-executor-verifier triples" topology
  that predates apply-tier inlining (MAR-60); the counts now reflect the current
  triad-vs-inline split.

- **`/acs:code` doc-sync now reconciles factual prd.md/roadmap.md claims and
  flags intent divergence (MAR-65).** Execute step 4 is extended so the
  executor reconciles FACTUAL claims in `docs/product/prd.md` and
  `docs/product/roadmap.md` as part of the same changeset diff (agent/subagent
  counts, feature/epic shipped-vs-planned status, component topology, version
  numbers, file path references). Intent content (goals, NFR targets, scope,
  vision, requirements rationale) remains `/acs:create-prd`-owned: when a
  changeset contradicts stated intent, the executor flags the divergence in its
  execute-report `problems` field (surfaced in the coordinator result document
  and PR body) and NEVER rewrites intent content. The code-planner's
  documentation map now assesses prd/roadmap factual impact; the
  code-verifier's Documentation-consistency dimension (dimension 11) makes a
  stale factual claim a blocking finding and an intent contradiction an explicit
  flagged divergence (not a block). ADR-0007 is amended inline to record the
  extended scope, the factual-vs-intent boundary, the divergence rationale, and
  the enforcement note (status remains Accepted).

## [0.3.0] - 2026-06-28

### Added

- **Complexity-adaptive delivery — four-lane routing from size × stakes
  (MAR-56).** `/acs:create-ticket` now classifies each ticket on two
  user-confirmed axes (`size`, `stakes`) and derives a deterministic `lane`
  (`TRIVIAL` / `SMALL` / `STANDARD` / `COMPLEX`) via `derive_lane()`, persisted
  to `ticket.json`, `pipeline-state.json`, and `tickets-index.json`. The lane
  drives how much process the pipeline applies; the default is full/standard
  rigor and lighter lanes are opt-in (rigor is never silently dropped).

- **Verifier-as-gate with lane-driven verify depth (MAR-58).** acs is
  autonomous-first: the verifier subagent is the in-loop quality gate on
  *every* lane (it always runs). `verify_depth(size, stakes)` scales only the
  iteration ceiling — `light` (single pass, `VERIFY_ITERATION_CAP["light"]=1`)
  for TRIVIAL/SMALL low/normal-stakes tickets, `full` (up to 3 iterations + the
  11-dimension review + e2e when configured) for STANDARD/COMPLEX and all
  high-stakes tickets — with a high-stakes floor to `full`. The TDD/coverage
  gate runs in full in every lane and is never trimmed by depth selection.

- **Trivial/small fast-lane: spec authoring folded into `/code` (MAR-59).** On
  the TRIVIAL/SMALL lanes, `gate_code` no longer requires a standalone
  `/acs:create-spec` run or a populated `specs/` directory; spec authoring
  (with acceptance criteria mapped to tests) is folded into `/acs:code`'s plan
  phase by the code-planner, and `/acs:ship` skips the standalone create-spec
  step for those lanes. STANDARD/COMPLEX/absent/unknown lanes stay fail-closed
  on the full create-spec path. The TDD/coverage hard-fail and verifier-as-gate
  (light cap 1, no inline human gate) are preserved on the fast lane.

- **Apply-tier inlining: create-pr / merge-pr / create-ticket run inline
  (MAR-60).** The three apply-work skills run deterministic-inline (coordinator
  + at most one executor), never a planner/executor/verifier triad, in every
  lane — generalizing the proven merge-pr exempt-PR inline shape. Every
  load-bearing apply step, post-hook, and canonical `states` key is preserved;
  the six triad-keeping skills (create-spec, code, create-prd, create-design,
  create-architecture, create-project) are unchanged. ~$0.10 inline vs ~$0.70
  triad per apply step (G14/G15).

- **Mid-flight lane escalation, upward-only (MAR-57).** A ticket whose true
  size/stakes turn out higher than its classification is automatically
  escalated to a higher-rigor lane mid-run (on the first higher-stakes signal:
  a verifier finding, a touched `high_stakes_paths` glob, or an explicit
  request) — recomputing lane + verify depth via `escalate_lane()` and
  re-persisting, without restarting, and re-introducing any skipped stage.
  De-escalation is guaranteed never automatic or silent: no unattended path
  lowers a ticket's lane or authoritative size/stakes below a user-confirmed
  value (an interactive downgrade command is deferred to a later ticket).

- **`/acs:init` prompts for per-role models on a fresh init.** Model selection
  is now a first-class setup step: a Recommended preset
  (planner/verifier/coordinator = opus, executor = sonnet), Inherit-session-
  model, or Custom per role. Re-runs only ask whether to change current values.

- **Behavioral-eval coverage for all 16 skills.** The `skill_triggers` routing
  eval now covers every skill: the 14 model-invocable ones by description, and
  the 2 user-only ones (`install-hooks`, `update`) by an explicit-invocation
  probe plus a negative-routing probe that asserts `disable-model-invocation`
  is honored. A new free, deterministic `update_migration` scenario certifies
  `/acs:update`'s local logic offline — numeric semver comparison
  (installed vs latest) and the Step-6 migration checks (settings validate
  against the schema; workspace requirement enforced).

### Changed

- **PRD/roadmap reconciled to the shipped verifier-as-gate model.** The
  complexity-adaptive PRD/roadmap previously described a three-tier model that
  dropped the verifier on trivial tickets behind a human-approval gate; the
  docs now describe the autonomous-first model that actually shipped (verifier
  gates on every lane; lane-driven verify depth; no inline human-approval gate;
  PR review is the human checkpoint).

- **In-process stdlib XML validation is now the default fast path (MAR-61).**
  `validate_xml.py` now validates every message via the in-process
  `validate_structurally()` engine (pure stdlib, zero subprocess) instead of
  spawning `xmllint` per message.  `xmllint` is retained as an opt-in
  authoritative check via `ACS_XML_AUTHORITATIVE=1` (PATH-guarded; absent
  xmllint never blocks a verdict).  The in-process engine matches xmllint for
  the following covered violation classes: bad root element, missing/invalid
  attribute, bad ticket-id pattern, out-of-order children, wrong list-item tag,
  bad status/severity enum, duplicate maxOccurs=1 sequence children
  (cardinality), xs:decimal grammar for cost-usd (no exponent, no inf/nan, no
  underscores), and the closed content model — undeclared attributes (the XSD
  has no anyAttribute/wildcard) and element children inside text-only
  (xs:string) leaves are both rejected, matching xmllint.  A parity corpus
  (`TestValidators` in `tests/acs/test_acs_plugin.py`) asserts identical
  pass/fail verdicts for each of these classes across both paths.

- **`validate_batch()` / `batch_overall_ok()` — new Python-callable batch
  validation API (MAR-61 AC-4).** `validate_batch(messages)` accepts a list
  of XML message strings and returns a per-message `(ok, errors)` tuple list
  in a single call with zero subprocess spawns; `batch_overall_ok(results)`
  returns `False` when any member is invalid.  The batch API calls the
  in-process `validate_structurally()` engine and is importable directly from
  `validate_xml.py`; `main()` and the CLI are unchanged (AC-6 back-compat).

- **Clarify-batching coordinator contract (MAR-61 AC-7).** All 9 hooked
  coordinator skill bodies and `docs/requirements/skills.md` now document the
  grouped-ask rule: when ≥2 clarifications are open, the coordinator presents
  all of them in ONE grouped interaction instead of serial round-trips.  Each
  answer is recorded as its own `clarify.py add` entry (one `C-<n>` per
  question, `--source` preserved); no question may be skipped, merged, or
  auto-answered outside the existing `--source assumption --rationale "..."`
  rule.  A `TestClarifyBatchingContract` suite in `test_skill_contracts.py`
  asserts grouped-ask presence, per-question ledger-entry documentation, and
  zero-auto-answer documentation across all 9 skills.

- **`/acs:merge-pr` is now agent/model-invocable (MAR-42).** Removed
  `disable-model-invocation` from the skill; the readiness gate (CI, approvals,
  conflicts, protections) and the repo's branch protection are the merge brakes,
  by whoever invokes. Because invocation source (agent vs user) is not reliably
  detectable, an **approving review is now required for every merge** (mitigation
  m6, the require-APPROVED-for-all fallback; see
  [ADR 0028](../../docs/adr/0028-merge-pr-agent-invocable.md)) — including on
  repos that require no review. `/acs:ship` still stops at create-pr. Authorised
  by the PRD Vision amendment in MAR-45.

### Fixed

- **`acs-conventions` workflow no longer cancels its own required check (MAR-43).**
  The concurrency block previously used `cancel-in-progress: true`. When a PR is
  created with `gh pr create --label ACS`, the `pull_request` trigger fires for
  both `opened` and `labeled` near-simultaneously, producing two runs in the same
  concurrency group. The cancelled run left a non-SUCCESS conclusion on the
  required "Branch / PR / commit conventions" check, which branch protection
  treated as unmet and blocked the PR (observed as PR #96). Setting
  `cancel-in-progress: false` in both `plugins/acs/templates/ci/acs-conventions.yml`
  and `.github/workflows/acs-conventions.yml` lets all concurrent runs complete;
  GitHub records the latest run's conclusion. The per-PR concurrency group is
  retained for cross-PR isolation.

### Added

- **Two-skill metrics split: `/acs:metrics` (PM view) + `/acs:usage` (usage view) (MAR-14).**
  The former single-view `/acs:metrics` skill is split into two narrowly-scoped
  utility skills over one shared stdlib aggregator:

  - **`/acs:usage`** is a new model-invocable utility skill (skill count 15 → 16,
    unhooked) that renders the **usage view**: usage summary (total cost, total
    working time, total runs, plus four averages — avg working time per ticket and
    per merged PR, avg cost per ticket and per merged PR), cost + time per ticket
    by pipeline step with the four averages (Panel 3), and token burn by role
    (Panel 6). Backed by `metrics_aggregate.py` (shared superset) then
    `metrics_render.py --view usage`. Read-only; no network call; no config key.

  - **`/acs:metrics`** is re-scoped to the **PM view**: delivery summary (headline
    KPIs — tickets done/total, PRs merged, avg lead/cycle, coverage pass rate),
    throughput by status/type (Panel 1), pipeline funnel + distinct PRs (Panel 2),
    ISSUES (id/title/status/type/GitHub key), PROGRESS (per-epic done/total +
    burn-up visual), DEADLINE ("not set" degraded frame — deadline tracking requires
    a `due_date` ticket field, wired in Child 3 / MAR-15), coverage achieved vs
    target (Panel 4), review iterations before the verifier passed (Panel 5), and
    lead + cycle time per ticket (Panel 7). Invokes `metrics_render.py --view pm`.

  **Shared mechanism.** `metrics_aggregate.py` emits one superset JSON carrying all
  panel keys for both views (the PM union usage full set; no panel appears in both
  views). `metrics_render.py` gains four new view entrypoints —
  `render_pm_terminal`, `render_pm_html`, `render_usage_terminal`,
  `render_usage_html` — selected by the new `--view {pm,usage}` CLI flag (bare
  `metrics_render.py` with no `--view` defaults to the PM view; both skills invoke
  the renderer with the flag explicitly). The existing `render_terminal` /
  `render_html` entrypoints and `--view all` remain for back-compat.

  **DEADLINE panel** ships as a "not set" B1-compliant degraded frame in this
  release (the panel key is always present; it renders "not set" without error).
  Child 3 / MAR-15 wires real due-date data via a `due_date` field on the ticket.

- **Ticket `due_date` field + live DEADLINE panel (MAR-15).** The DEADLINE panel
  in `/acs:metrics` (PM view) now derives and displays real on-track/overdue
  status from each ticket's `due_date`:

  - **`due_date` on `ticket.json`** is a new optional ISO-8601 date field
    (`YYYY-MM-DD` or null; additive, back-compatible — existing tickets with no
    `due_date` are valid and the panel degrades gracefully to "not set").
    `/acs:create-ticket` elicits and sets `due_date`; the `--due-date` option on
    `new-ticket.py` accepts and validates the value (malformed input is rejected
    with a non-zero exit).
  - **DEADLINE panel — live derivation.** `metrics_aggregate.py` reads each
    ticket's `due_date` (from the `ticket.json` already opened per ticket) and
    derives: *overdue* when `due_date < now` and the ticket is not done;
    *on-track* otherwise.  The panel shows one row per ticket with a `due_date`,
    plus a roll-up summary.  A workspace with no parseable `due_date` on any
    ticket degrades to the "not set" state (B1 — the panel key is always
    present; no crash).  An empty workspace keeps `deadline == "no data"`.
  - **Read-only.** Aggregator and renderer write nothing; the only new write is
    `due_date` at create-ticket.  No network call; no new config key.
    Deterministic: the reference "now" is the same instant stamped into
    `meta.generated_at` (pinnable in tests); the renderer reads no clock.

  This supersedes the MAR-14 interim "not set" degraded frame.

- **Distinct-PR counting via `created_pr_numbers` + idempotent backfill (MAR-13 spec 01).**
  `prs.created` in `metrics.json` now counts **distinct PRs** rather than completed
  `create-pr` run invocations — a single PR re-triggered multiple times no longer
  inflates the metric.  `update_metrics` gains an optional `pr_number` parameter;
  when `pr_created` is truthy and `pr_number` is a positive integer not already
  recorded, it is appended to a sorted de-duped `prs.created_pr_numbers` list and
  `prs.created` is set to `len(created_pr_numbers)` (idempotent: re-runs with the
  same number are a no-op).  A one-time idempotent `backfill_distinct_pr_count`
  helper heals already-inflated history by recomputing `created_pr_numbers` from
  the distinct positive `states.pr.number` values across all active and `archive/`
  partitions; re-running it is safe and produces the same result.  The
  `created_pr_numbers` field is additive on the `prs` object (no schema break); all
  other metric paths (`tokens`, `cost_usd`, `prs.merged`, ticket counts) are
  unchanged.  No new runtime dependency; no network call.
- **Lead/cycle re-cycle hardening + per-ticket re-work count (MAR-13 spec 02).**
  Panel 7 (`metrics_aggregate.py`) now carries an explicit overlap-safe guarantee:
  `aggregate()` never raises when a ticket's `code.started_at` falls after its
  `merge-pr.ended_at` (a re-cycled or overlapping step span) — the affected
  `cycle_seconds` value renders as `"no data"` and a `meta.degraded` entry (panel 7)
  is appended; one row per ticket is always returned; nothing is written.  This
  guarantee is documented in the `_elapsed_seconds` and `_panel7_row` docstrings and
  is now covered by a dedicated cycle-inversion test
  (`test_cycle_inversion_yields_no_data`).  In addition, each Panel-7 per-ticket row
  gains a new additive `rework_count` integer field (>= 0) equal to the count of
  distinct positive PR numbers recoverable from that ticket's `create-pr-state.json`
  in the resolved partition; 0 when the file is absent, malformed, or carries no
  positive PR number.  `rework_count` is read-only (zero writes), stdlib-only, and
  is not averaged at the panel level — it is per-ticket metadata next to
  `lead_seconds` / `cycle_seconds`.  No schema break; no new config key; no network
  call.
- **Pipeline-default `CLAUDE.md` guidance + exempt non-ticket merge path (MAR-9).**
  Two changes that make the acs pipeline the *automatic* path in an installed
  repo and close the non-ticket dead end. (1) `/acs:init` gains an opt-in
  (default-on) step that writes an idempotent, marker-delimited **acs-managed
  block** into the repo's `CLAUDE.md` (from the new `templates/CLAUDE.acs.md`),
  steering every Claude session to ship via `/acs:ship` instead of a raw
  `gh pr create` — re-runs replace only the block, never the surrounding
  content. (2) `/acs:merge-pr --pr <n>` (also `#n` or a PR URL) lands a
  legitimate one-off **exempt** PR: it runs the same four readiness checks and
  branch/worktree cleanup as the ticket path but resolves no ticket, writes no
  partition/state, and skips tracker sync and archiving (bumping only the repo
  `pr_merged` metric). `skill-start.py --pr` validates the PR carries the
  configured `exempt_label` (or an `exempt_branches` head) and refuses +
  redirects to `/acs:merge-pr <ticket-id>` when the PR looks ticket-backed. The
  existing ticket-backed merge flow and every other gate are unchanged.
- **`/acs:metrics` — read-only delivery dashboard (MAR-5).** A new
  model-invocable utility skill that renders dashboard panels for the current repo —
  throughput by status/type, pipeline funnel, cost and time per ticket by step,
  coverage achieved vs target, review iterations before the verifier passed, and
  token burn by role (planner/executor/verifier). Backed by the stdlib-only
  `metrics_aggregate.py` helper, which aggregates the panels from existing
  workspace artifacts and emits one JSON object (every panel key always present;
  degradation is an in-band "no data" marker, never a missing key). The skill is
  read-only: it writes no file, makes no network call, and adds no config key.
- **Deterministic cross-surface metrics renderer (MAR-5).** Rendering is now a
  deterministic stdlib helper `metrics_render.py` that consumes the aggregate
  JSON and emits the dashboard panels on two surfaces: a Unicode block-bar
  **terminal** dashboard for the Claude Code CLI (default) and a self-contained
  **HTML** component (`--html`, inline CSS, no external fetch) handed to
  `show_widget` verbatim on Claude Desktop / claude.ai. The skill now **routes**
  (aggregate → render) instead of model-composing the layout, and the
  deterministic terminal renderer **supersedes** the former model-improvised
  Markdown-table fallback. `metrics_render.py` is stdlib-only, never imports
  `show_widget`, is read-only, and is deterministic (identical JSON in →
  byte-identical output; no clock read in render) — unit-tested to the same 90%
  coverage bar as the aggregator.
- **`/acs:metrics` delivery-flow metrics (MAR-7).** The dashboard now surfaces
  delivery-flow timing on both render surfaces: **Panel 3** gains four **averages**
  summary rows — avg working time and avg cost, each per ticket and per merged PR
  (a zero denominator renders "no data") — and a **new Panel 7 — Lead + cycle time
  per ticket** shows per-ticket **lead** (`ticket.json.created_at` → `merge-pr`
  end) and **cycle** (`code` start → `merge-pr` end) wall-clock times plus their
  averages, with humanized `d`/`h`/`m`/`s` durations. Aggregated additively in
  `metrics_aggregate.py` and rendered in `metrics_render.py` (terminal + HTML),
  read-only and deterministic, with every "no data" value rendering a present "no
  data" cell — no schema, config, or network change.

## [0.2.0] - 2026-06-14

### Added

- **`/acs:init` toolchain preflight (Step 0b).** Init now checks every external
  tool the full workflow needs up front and offers to install the missing ones
  (consent-gated, platform-aware) instead of failing mid-pipeline on a missing
  `gh` or `pre-commit`. Backed by `acs_lib.check_toolchain()` — the single
  source of truth listing `git`, `python3`, `gh`, `pre-commit`, `xmllint`,
  `acli` with kind (required | recommended | optional, bumped by tracker
  provider) and per-platform install commands — plus `acs_lib.missing_tools()`.
  The Step 8 summary now also confirms the full skill set is ready.

- **CI enforcement of acs conventions (opt-in via `/acs:init`).** A new Step 7c
  offers to scaffold repo-side enforcement so a PR that never went through
  `/acs:create-pr` is still held to the same conventions before it can merge.
  It installs:
  - `.github/workflows/acs-conventions.yml` — a `pull_request` check (re-runs on
    title/body edits and label changes) that validates **branch name**, **PR
    title**, **PR description sections**, the **`ACS` label**, and (opt-in)
    **commit-message** format.
  - `.acs/ci/check-conventions.py` — a self-contained, stdlib-only checker that
    compiles the committed `formats.*` strings into regexes (the same vocabulary
    the pipeline renders from) and reads `ticket_prefix` + `formats` from the
    committed `.acs/settings.json`; **no acs install is needed on the runner**.
    It is FAIL-CLOSED (no committed conventions → error + "run /acs:init") and
    runs in `--mode pr` (CI), `--mode pre-push`, or `--mode commit-msg` (local
    hooks) — the same checker and the same configured formats everywhere.
  - Optional **local git hooks** that enforce conventions *before* push, against
    the SAME configured `formats.*`/`enforcement.*`: `commit-msg` validates the
    commit subject against `formats.commit_message` as it is written, and
    `pre-push` validates `formats.branch_name` + the push range's commit
    subjects. Installed via the pre-commit framework (tracked, shared across the
    team) or as raw `.git/hooks/*` (per-clone). PR title/description stay CI-only
    (they don't exist until a PR is open).
  - New **`enforcement`** settings block (`schemas/settings.schema.json`):
    `checks.*` toggles, `exempt_branches` globs, `exempt_label`, `require_label`,
    and `pr_description_sections`.
- **New skill `/acs:install-hooks`** — the `pre-commit install` equivalent for
  acs: installs this clone's local `commit-msg` + `pre-push` hooks (per-clone,
  user-invoked). It ensures the `.acs/ci/` files exist (copying them from the
  plugin if needed), then installs via the pre-commit framework when the repo
  uses it or via raw git hooks otherwise. A committed `.acs/ci/install-hooks.sh`
  lets a teammate who only cloned the repo run it (`sh .acs/ci/install-hooks.sh`)
  without the acs plugin. `/acs:init` Step 7c now copies the hook scripts +
  installer into `.acs/ci/` and points at this command.
- **No-bypass gate guidance.** Because branch/title are cosmetic and the proof
  of pipeline use lives in the workspace outside the repo, the check is *mandatory
  to merge* but the real gate is a **required status check on a protected default
  branch**. Step 7c detects repo-admin (`gh api .permissions.admin`) and either
  configures branch protection via `gh api` or prints the one-time admin command,
  with a configurable **`acs-exempt` label + branch allowlist** escape hatch for
  releases and bot PRs.

## [0.1.6] - 2026-06-14

### Fixed

- `/acs:init` now reliably gitignores `<repo>/.acs/settings.local.json`. The
  Step 5 ignore step is rewritten to run on **every** init (fresh and re-run,
  even when no keys changed), so a repo first initialized by an older acs that
  has the file but no ignore rule gets retro-fixed. It uses `git check-ignore`
  instead of an exact-line `grep` (a broader existing rule like `.acs/` now
  counts as ignored, so no duplicate line is appended) and guarantees a
  trailing newline before appending so the entry can't glue onto the last line
  of an existing `.gitignore`.

## [0.1.5] - 2026-06-14

### Changed

- Unified release versioning: the marketplace catalog and the `acs` plugin now
  share **one version** and a single `v<version>` release tag. The separate
  `marketplace-v<version>` tag scheme and its workflow are retired. Cutting a
  release now bumps `version` in both `.claude-plugin/marketplace.json` and
  `plugins/acs/.claude-plugin/plugin.json` to the same value and points the acs
  `git-subdir` `source.ref` at the new `v<version>` tag; CI enforces that the
  two versions match. Existing `marketplace-v*` tags remain valid in history.

## [0.1.3] - 2026-06-13

### Changed

- **Breaking**: marketplace `name` renamed from `gms-plugins` to `gms-marketplace`.
  Existing consumers must migrate:
  1. Rename the key in `extraKnownMarketplaces` (managed settings or
     `~/.claude/settings.json`) from `"gms-plugins"` to `"gms-marketplace"`.
  2. Re-run `claude plugin install acs@gms-marketplace` (the old
     `acs@gms-plugins` reference no longer resolves).

## [0.1.2] - 2026-06-13

### Fixed

- Plugin failed to install on current Claude Code (manifest validation:
  `Unrecognized key: "displayName"`), leaving `acs@gms-marketplace` uninstallable
  even after the v0.1.1 hooks fix. Removed the unsupported `displayName` key
  from `plugin.json`; the marketplace lists the plugin by `name` +
  `description`. Caught by the M2-0 validation spike
  ([docs/product/m2-0-validation-spike.md](../../docs/product/spikes/m2-0-validation-spike.md)).

## [0.1.1] - 2026-06-13

### Fixed

- Plugin failed to load on install with "Duplicate hooks file detected"
  because `plugin.json` declared `"hooks": "./hooks/hooks.json"` — a file
  Claude Code already auto-loads by convention. Removed the redundant
  manifest key so the plugin loads cleanly on a fresh install (GMS-5).

## [0.1.0] - 2026-06-12

Initial release.

### Added

- Claude Code plugin marketplace manifest (`.claude-plugin/marketplace.json`)
  listing the `acs` plugin; install with
  `claude plugin marketplace add <github-url>`.
- 12 skills: `/acs:init`, `/acs:ship`, `/acs:handoff`, `/acs:create-prd`,
  `/acs:create-architecture`, `/acs:create-project`, `/acs:create-ticket`,
  `/acs:create-design`, `/acs:create-spec`, `/acs:code`, `/acs:create-pr`,
  `/acs:merge-pr`.
- 27 subagents: planner/executor/verifier triples for each of the 9 workflow
  and product-level skills, driving the plan -> execute -> verify reflection
  cycle (max 3 iterations).
- Hook-gated pipeline: a `PreToolUse` dispatcher plus pre/post hooks per
  hooked skill — each skill refuses to run (exit 2) until its predecessor's
  run completed, post-hooks finalize run state and release locks, and a
  `SessionEnd` safety net marks interrupted runs.
- Workspace state outside the consumer repo: per-ticket partitions
  (`ticket.json`, `pipeline-state.json`, `design.md`, `specs/`, phase
  artifacts, result documents) plus repo-level `tickets-index.json`,
  `counters.json`, `metrics.json`, per-checkout session pointers, and
  `archive/` for merged tickets.
- Helper CLIs: `skill-start.py`, `new-ticket.py`, `handoff.py`,
  `validate_xml.py` (under `hooks/scripts/`).
- JSON Schemas for every workspace document
  (`plugins/acs/schemas/*.schema.json`).
- XSD-defined XML messaging (`plugins/acs/schemas/acs-messages.xsd`):
  `task`, `result`, and `handoff` messages between coordinator and subagents.
- Description templates (`plugins/acs/templates/`): `epic-default.md`,
  `story-default.md`, `task-default.md`, `pr-default.md`.
- Unit test suite (`tests/`) and CI: tests on Python 3.9 and 3.12, JSON and
  JSON Schema validation, XSD validation, hook-script byte-compilation, and
  skill/agent frontmatter checks.
- Automated release workflow: tags `v<version>` and publishes a GitHub
  release from the matching changelog section when the plugin manifest
  version changes on `main`.

[Unreleased]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.3.4...HEAD
[0.3.4]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.3.3...v0.3.4
[0.3.1]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.6...v0.2.0
[0.1.6]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.3...v0.1.5
[0.1.3]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/globalmindsolution/gms-marketplace/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/globalmindsolution/gms-marketplace/releases/tag/v0.1.0
