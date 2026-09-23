# C4 Level 3 — Components (hook & helper layer)

The container with the most internal structure is the deterministic layer.
(C4 level 4 — code — is deliberately out of scope; the `acs_lib/` package and
its tests serve that level.)

```mermaid
C4Component
    title Hook & helper layer — components

    Container_Boundary(hooks, "Hook & helper layer") {
        Component(dispatch, "dispatch.py", "hook entry", "PreToolUse(Skill): route to pre-<skill>.py, exit-2 blocks; SessionEnd: safety net")
        Component(cli, "acs.py / acs_cli.py / acs_commands.py", "deterministic CLI front door", "ADR 0001's single entry point for the verbs a SKILL.md names, so no coordinator improvises heredoc Python: context, gate, run (new|show|next|check|abandon), step (start|finish|show), result validate, ticket, pr, tracker, readiness, lock, filemap, guard, verdict, slug, fanout, doctor, workflow (show|validate) and artifacts are implemented in-process, while plan (check|path) and setup detect/apply forward argv to the scripts that already implement them and return their exit code unchanged; stdout is exactly one pretty-printed JSON object, a usage or precondition failure exits 2, and exit 0 means the command ran, not that the answer was yes; guard events is MAR-578's read side over invocations[-1].guard_events, emitting ok/run_id/skill/count/events/path")
        Component(pre, "pre-<skill>.py x19", "gates", "artifacts the skill READS exist, lock free, settings/formats valid, safety brakes; a step owing nothing per the plan's ## Contract block is completed here as an evidenced no-op; no gate refuses a skill for a predecessor's POSITION in the workflow, though /acs:merge-pr's subject brake does read whether the step that recorded the PR reference completed — an artifact, not a position (gates.SUBJECT_GATES); fail closed; acs_lib.run_pre also writes a session-correlation marker (session_id/transcript_path off the PreToolUse envelope) via record_session_marker, wrapped in its own fail-open try/except so a marker bug never blocks the gate (MAR-1)")
        Component(post, "post-<skill>.py x19", "persistence", "finalize the step invocation; update ledger, index, metrics; release lock; merge extras (archive, epic auto-done); finalize_run measures tokens via usage_reader instead of trusting a coordinator-supplied estimate (MAR-1); no dollar cost is recorded (ADR 0103)")
        Component(start, "acs.py step start", "step registration", "resolve the run (ticket id, prompt or document); allocate ids; acquire the lock; write sessions/<checkout>/pointer.json; record the step in_progress; reconcile/handoff detection; reads the session-correlation marker and threads session_id/transcript_path/checkout_id onto the new invocation (MAR-1)")
        Component(mint, "new-ticket.py", "ticket factory", "id allocation, partition + ticket.json, epic backlinks, mint-time create-ticket state")
        Component(clarify, "clarify.py", "Q&A ledger", "add/answer/list clarifications; assumption protocol")
        Component(handoff, "handoff.py", "session handoff", "finalize the in-flight step interrupted + stop_reason: context_pressure + summary; release lock; print continue_with")
        Component(planapproval, "plan-approval.py", "plan approval + contract read", "sole writer of steps/create-impl-plan/plan-approval.json; records acs_lib.plan_approval_eligible's deterministic verdict plus the approved plan's sha256 (over the WHOLE file, prose and ## Contract alike) once per digest; mirrors states.plan_approved into the plan step's state; standard/complex only. Its `path` verb is the read side: prints the plan's delivery_path, owes flags and contract_errors, writing nothing (ADR-0098)")
        Component(codeowners, "codeowners.py", "reviewer resolution", "stdlib-only CODEOWNERS parser — last-match-wins pattern matching against changed files, team+user owner extraction, no workspace/lock coupling")
        Component(prconventions, "pr-conventions.py", "PR title render + pre-open convention self-check", "stdlib-only, runtime-agnostic helper for /acs:create-pr and the three product-level skills: render-title renders settings.formats.pr_title via acs_lib.render_format (the deterministic path, not LLM prose) and prints it verbatim for `gh pr create/edit --title`; check self-checks a rendered title plus a filled PR body BEFORE a PR is opened by driving templates/ci/check-conventions.py's evaluate() as the single source of truth, never re-implementing the convention rules, with two producer-only hygiene scans (unrendered placeholder tokens, leftover template comments) run on top of evaluate(), never instead of it. Derives no branch name or commit history itself -- its own tests assert the executable source contains no subprocess, which is why the stacked-base pre-flight below lives in a separate module rather than here")
        Component(stackedbase, "stacked-base.py", "create-pr stacked-base pre-flight", "new (MAR-590), stdlib-only and network-free -- the caller does the `git fetch`: decides whether a branch is stacked on a squash-merged base BEFORE /acs:create-pr pushes anything, and when it is, names the non-conforming subjects the author cannot fix by renaming them and emits a replay target. Two controls, neither redundant: step A reverse-applies each non-conforming commit's own `git diff --binary` patch against the base tree with a merge-base control, and step B gates on the newest commit whose CUMULATIVE diff from the merge base reverse-applies, which is the only safe `rebase --onto` target. Read-only: every tree test runs against a throwaway GIT_INDEX_FILE under tempfile.mkdtemp(), so nothing in `.git` is written. Loads templates/ci/check-conventions.py by file path exactly as pr-conventions.py does and calls its format_to_regex / _is_ignorable_commit -- it re-implements neither. Exits 0 (no stacked base), 1 (verdict stacked_base, a verdict rather than a failure) or 2 (unevaluable), printing its JSON report on stdout on 0 and 1 only. Detection is deliberately incomplete -- a miss degrades to the ordinary red conventions gate, never to a false alarm -- and the emitted replay is proven lossless only in the bounded sense that everything at-or-before replay_onto is already present in the base")
        Component(release_notes, "release_notes.py", "changelog aggregation + version bump", "stdlib-only, settings-driven helper — reads the .acs/settings.json release block (Decision 5), drafts the changelog section from the merged-ticket archive plus a base_branch git-history fallback for tickets no /acs:merge-pr archive entry recorded (each enumerated ticket stamped source: archive|git-log), optionally anchored by --ticket-prefix, cross-checks [Unreleased] coverage, bumps the block's version_locations + extra_refs + changelog_path; has its own gh seam -- gh_pr_list reads open release PRs, per its own docstring (MAR-403 D-3) -- currently unclassified: any non-zero exit returns None indistinguishable from 'no open PR' (follow-up R11, not fixed by MAR-403)")
        Component(migrateworkspace, "migrate_workspace.py", "workspace migrator", "standalone, one-shot CLI copying an external workspace partition into the in-repo state root — preflight aborts (exit 2) on any live lock or in_progress last status found anywhere under the source, reading both the old flat <skill>-state.json and the new steps/<skill>/state.json layouts; classifies each top-level entry as a run directory (copied once, an already-present destination partition left as-is for idempotent resume), the archive/ tree (same rule per archived ticket), or a repo-level file (copied if absent, skipped if byte-identical, abort on any other conflict); verifies every source file exists at the destination before removing the source tree; --dry-run prints the planned actions without writing or removing anything")
        Component(mermaidlint, "mermaid_lint.py", "doc lint", "stdlib-only heuristic Mermaid linter — blocking 0-syntax-error gate for generated docs; read-only")
        Component(structurelint, "structure_lint.py", "doc lint", "stdlib-only structure/section-conformance linter — blocking presence/non-empty/declared-order gate for generated docs against a skill-declared required-section list; read-only")
        Component(citationcheck, "citation_check.py", "doc lint", "stdlib-only citation-corroboration linter — blocking mechanical-floor gate (path containment, whitespace-normalized quoted-excerpt match) over the Upstream inventory citations of create-quality/-standards/-operations/-principles plan artifacts; read-only")
        Component(prdconformancecheck, "prd_conformance_check.py", "doc lint", "stdlib-only three-family corroboration linter — blocking mechanical-floor gate (code-evidence via imported citation_check helpers, answer-fidelity via clarifications.json reflection anchors, roadmap-outline via verbatim milestone-heading match) over /acs:create-prd's plan artifacts; read-only")
        Component(ureader, "usage_reader.py", "usage measurement", "new (MAR-1), stdlib-only: reads the run's exact recorded transcript_path + subagents/ subtree, counts all four message.usage token classes, buckets per role (coordinator/planner/executor/verifier/other/unattributed) and per model into a parallel model_usage list (MAR-3); never raises, degrades with a reason on any read failure, cap breach, or zero-token result")
        Component(metrics, "metrics_aggregate.py", "observability", "read-only: aggregate all panels for /acs:metrics (PM view) and /acs:usage (usage view) from workspace artifacts; emits one superset JSON, never writes/gates/locks; panel 6 (_accumulate_burn) now reads each run entry's measured role_usage field instead of scraping <metrics> XML, including a first-class coordinator bucket (MAR-1); MAR-3 additionally folds each run entry's model_usage into the new usage_by_model panel, at both repo and per-ticket scope, in the same walk (zero extra file reads); MAR-4 additionally computes each panel-6 bucket's repo-scope token_share_pct (_apply_panel6_shares, once, post-loop) and finalizes ticket-scope role shares into the new usage_by_ticket panel (_usage_by_ticket_panel), both derived from data already summed — zero extra file reads; MAR-7 additionally widens _accumulate_burn's return to a 3-tuple (adds ticket_skills, a per-skill raw wall-clock accumulator keyed by HOOKED_SKILLS, folded from each run entry's elapsed time — zero extra file reads), _panel3_row gains an additive step_order sibling key (steps itself unchanged), and _usage_by_ticket_panel widens with a skills[] array (_finalize_skill_bucket); tokens and wall-clock time only — no cost or API-duration figure, even from an older run entry that still carries one (ADR 0103)")
        Component(mrender, "metrics_render.py", "observability", "read-only: deterministic cross-surface renderer of the aggregate JSON — serves two views via render_pm_terminal/html (/acs:metrics) and render_usage_terminal/html (/acs:usage), selected by --view {pm,usage}; bare default is PM view; self-contained HTML (--html → show_widget); pure, no clock, never writes; MAR-4 additionally renders panel 6's token % column and the new usage_by_ticket table (_term_render_usage_by_ticket/_html_render_usage_by_ticket); MAR-7 additionally renders panel 3's per-skill sub-rows (_term_panel3_sub_rows/_html_panel3_sub_rows, one line per step_order entry: its step span) and the widened usage_by_ticket panel's skills[] table with per-run detail (_term_skill_table/_html_skill_table); no dollar or API-duration column (ADR 0103)")
        Component(lib, "acs_lib/", "shared core", "settings resolution, repo/checkout identity, state files, ledger, index, counters, metrics, locks, gates; default_state_root() derives the in-repo, main-checkout-anchored .acs/state-machine root from git plumbing, with no override (ADR-0102); plan_contract.read()/delivery_path()/owes() — the read side of the judged delivery path and the always-run steps' owes flags, both taken from the PLAN's ## Contract block, which is their only home; there is no writer here at all, because /acs:create-impl-plan judges the path once and writes it into the plan (ADR-0098, superseding record_delivery_path()/recorded_delivery_path() and, before them, derive_lane()/recommend_stakes()/verify_depth() and the escalation writers); record_guard_event() the file-map guard's fail-soft audit writer, appending one denial to invocations[-1].guard_events and returning False instead of raising when the invocation is absent, because its sole caller is a deny path whose verdict must not depend on the recording (MAR-578); plan_approval_eligible() pure plan-conformance predicate; allocate_ticket_id()'s fail-closed reconciliation gate — inside its existing O_EXCL critical section, the first allocation from a fresh/unreconciled (repo_id, prefix) partition refuses with exit 2 (ReconciliationRequired, a GateError subclass) unless a confirmable local-evidence proposal is confirmed via --seed-next; an already-populated counters.json is treated as already reconciled, no prompt (MAR-402); scan_local_ticket_evidence() — the ranked, bounded, network-free local-evidence scan helper backing that gate (committed-files grep, then git subjects+bodies, then branch names, each shelled out via the existing _git seam; MAR-402); elapsed_seconds() single None-safe time primitive (run_seconds/metrics_aggregate._elapsed_seconds are adapters over it); record_session_marker()/session_marker_path(); finalize_run() invokes usage_reader instead of trusting a coordinator-supplied tokens estimate (MAR-1, ADR 0082); DOC_BOOTSTRAP_DEPENDENCIES declared-dependency table + DOC_SET_DEFAULT_DIR new-set default directory + DOC_BOOTSTRAP_FANOUT_V1 declared v1 fan-out pair + fanout_batches() pure eligibility helper, fed the sets the coordinator found present (ADR-0102), for /acs:create-docs's cross-skill fan-out + parse_fanout_for_arg() pure --for argument parser gated on the declared v1 set, and an O_EXCL-guarded critical section around update_index()/update_metrics() that serializes two concurrently-running legs' updates on the normal path (fail-closed since MAR-530: a bounded-spin timeout raises GuardTimeout and REFUSES the write rather than performing it unguarded; a guard left by a crashed writer is reclaimed only once it outlives twice the configured budget and its recorded holder is not a live local process) (MAR-1); GH_ACCESS_DENIED_MARKER/GH_ACCESS_HINT/GH_GENERIC_HINT constants + the pure gh_failure_hint(stderr_text) predicate -- the canonical gh-failure diagnostic (verbatim stderr substring match, wording-only, no I/O, no network, no subprocess), quoted verbatim by the three apply-work skills and their executor agents as the single source of truth for the critical-failure hint sentence (MAR-403, ADR-0088; no new component -- Option F, not Option E)")
    }
    ContainerDb_Ext(ws, "Workspace store")
    System_Ext(transcript, "Claude Code transcript store")

    Rel(dispatch, pre, "subprocess, same stdin")
    Rel(cli, lib, "imports acs_lib as lib for every in-process verb")
    Rel(pre, lib, "build_context + GATES + record_session_marker")
    Rel(post, lib, "finalize_run, update_*")
    Rel(start, lib, "")
    Rel(mint, lib, "")
    Rel(clarify, lib, "")
    Rel(handoff, lib, "")
    Rel(planapproval, lib, "build_context + plan_approval_eligible")
    Rel(planapproval, ws, "atomic JSON read/write")
    Rel(prconventions, lib, "render_format for the deterministic title render")
    Rel(lib, ureader, "finalize_run -> read_transcript_usage(transcript_path, started_at, ended_at, skill)")
    Rel(ureader, transcript, "reads message.usage + model + timestamp + attribution fields only, read-only")
    Rel(ureader, lib, "acs_lib.parse_iso, ATTRIBUTION_SKILL_MAP")
    Rel(metrics, lib, "build_context + read-only state reads")
    Rel(mrender, metrics, "consumes aggregate JSON (stdin or self-invoke)")
    Rel(mrender, lib, "build_context on the self-invoke path (read-only)")
    Rel(lib, ws, "atomic JSON read/write")
```

## Skill-side anatomy (per hooked skill)

Every coordinator follows the same protocol components (defined once in
`plugins/acs/docs/INTERNALS.md`): Start (skill-start) → Resume/reconcile →
work loop (XML tasks → phase artifacts → validation → persistence) →
User interaction (clarification ledger) → Context pressure (handoff) →
Finish (result document → post-hook → completion report).

The work loop has two shapes. The **twelve authoring skills** (create-prd,
create-architecture, create-project, create-design, docs-sync,
standardize-project, create-requirements, analyze-requirements, create-impl-plan,
create-api-contract, create-test-docs, create-e2e-tests), `code` and
`create-docs` run the execute→verify reflection loop, spawning a separate
executor and verifier subagent per phase —
**12 authoring pairs (24 agents in pairs)** plus the 2 + 2 of `code` and
`create-docs`. No skill has a plan
phase: every one of the fourteen runs execute→verify with no planner (ADR
0092; `code` against the plan `/acs:create-impl-plan` approved, ADR 0089;
`create-docs` first, ADR 0094; the other twelve in ADR 0092's stage 2) —
iteration 1's executor surveys and records `iter-<n>-authoring.md` before it
writes, and the verifier judges the deliverable against those notes. The
**three apply-work skills** (create-ticket, create-pr, merge-pr) run
**inline** (MAR-60): the coordinator does the work directly, or delegates to
**at most one** executor — never a verifier, any lane; correctness is gated
instead (create-ticket by schema + Step-2 confirmation; create-pr/merge-pr by
`/code`'s verifier). 24 agents in the authoring pairs, the 4 of `code`'s and
`create-docs`'s executor + verifier pairs, and the 3 apply-work executors
give **31 agent files, all reachable**; the apply-work skills' plan/verify
files and the twelve authoring planners were deleted under ADR 0092, so no
agent file is orphaned. Within the fourteen, `/create-impl-plan`'s execute
leg is lane-conditional since MAR-72: its executor (whose survey is the
former `code-planner` charter) is spawned on STANDARD/COMPLEX; on
TRIVIAL/SMALL the coordinator authors the plan artifact itself, with zero
executor spawns (ADR 0074). The verify leg stays unconditional in every lane,
for every skill that runs the loop — so the counts above are unaffected.

`/acs:project` is an unhooked coordinator: like `/acs:ship` it has no
executor/verifier pair, no gate and no hook scripts of its own. It is the
**entry point** of the design-phase fold (ADR 0091; a leg is marked by
`disable-model-invocation: true` in its own front matter, not by a registry
entry — `workflows/phases.yaml` is gone, ADR-0096), and it spawns the *existing* pairs above as
ordinary execute→verify runs on their own delivery tickets — over exactly
one of its two legs (`create-project` or `standardize-project`), chosen by
`acs_lib.project_mode` from declared on-disk evidence. `/acs:create-docs`,
once an unhooked umbrella over four such legs, is since ADR 0094 a hooked
product skill of its own: one executor + verifier pair authors and judges any
of the four doc sets (the set rides in the task constraints), one delivery
ticket per set, the eligible sets run in slices of at most 2 — a limit
`/acs:create-docs` sets for itself, since `ship.yaml` v3 carries no
`max_parallel`. Because the fold moved no pair, no gate and no agent file, the
authoring-skill list and the 12/24/31 counts above are unaffected by it
(MAR-1; fold per ADR 0091).

`/code` adapts to the recorded DELIVERY PATH, and it does so by DISPATCH
rather than by branching inside one body: `skills/code/SKILL.md` reads the
path with `acs.py plan path` — from the PLAN's `## Contract` block, its only
home (ADR-0098) — and calls the matching leg: `code-trivial`, `code-small`,
`code-standard` or `code-complex`. Each states its own executor shape and
shares the protocol and execute references under `skills/code/references/`.
The two axes the legs used to differ by are gone, and both left for the same
reason — they were review properties, not implementation properties: the
verifier's shape is `/acs:review-code`'s business on every run, and the
iteration ceiling is the workflow's `loops[].max_iterations` (ADR-0099). The
legs own no agents and no hook scripts: each runs
`acs.py step start --step code`, so the run directory, the step state, the
ledger key and the post-hook are `code`'s throughout, and each spawns
`code-executor`. There is no `code-verifier`.

The REVIEW runs on **every** path, as `/acs:review-code`: five read-only
lenses in parallel, one fresh-context adjudicator per candidate finding, and
a final gate running build, lint, the full unit suite and coverage — the only
place the suite runs. The ceiling counts `code` → `review-code` rounds, with
the plan authored once before the loop (MAR-71, slice 1b of MAR-69).
Exactly one plan-authoring `create-impl-plan-executor` is spawned per
`/create-impl-plan` run, on every run — MAR-72/ADR-0074's coordinator-authored
fast path went with the lanes, because that skill runs before any path exists.
Spec authoring folds into `/create-impl-plan`'s plan whenever
`<partition>/specs/` is absent or empty (MAR-59, universalized by ADR 0066).

A path never moves mid-run. MAR-57's upward escalation, MAR-106's
`record_escalation_event` audit trail and MAR-108/ADR 0042 D3's
`confirm_deescalation` all existed to make a mid-run rigor change safe, and
all three are retired with the axes they moved: the judgement is made once,
by `/acs:create-impl-plan`, and written into the plan — there is no second
writer to move it, and re-judging means editing the plan, which invalidates
its approval and shows up in the diff. After the plan is authored, on the `standard` and `complex` paths a
deterministic plan-approval record is written
(`plan-approval.py`, `states.plan_approved`) and gates nothing this release
(MAR-73, slice 3 of MAR-69). The record is now **read** by
`/acs:review-code`'s plan-conformance lens as its activation condition
(`eligible`, `plan_path == steps/create-impl-plan/plan.md`, `plan_sha256`
matching the current `plan.md` bytes) — never a coordinator-relayed value;
`plan-approval.py` stays its sole writer; it **still gates nothing** (it is a
review dimension, not a `/create-pr` gate change), and the revocation path
re-runs the script for a fresh record (MAR-74, slice 4 of MAR-69, ADR 0073).
