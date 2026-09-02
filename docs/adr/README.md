# Architecture Decision Records

Decision records for the **GMS Marketplace** (including acs and its plugins, dogfooding `adr_path`). On
consumer repos this folder is maintained by `/acs:code`, which commits each
ticket design's accepted decisions; these first ten are retrofitted from the
[decision log](../README.md#decision-log) — the log remains the complete,
dated history, while ADRs carry the load-bearing architecture choices with
context and consequences.

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-two-layer-architecture.md) | Deterministic scripts vs. judgment prose | Accepted |
| [0002](0002-hook-event-binding.md) | Hook event binding on PreToolUse(Skill) | Accepted |
| [0003](0003-file-based-state-outside-repo.md) | File-based state in a workspace outside the repo | Superseded |
| [0004](0004-reflection-with-independent-verifier.md) | Reflection trio; verifier anchors on gated contracts | Accepted |
| [0005](0005-xml-messaging-with-xsd.md) | XML subagent messaging validated by XSD | Accepted |
| [0006](0006-spec-plan-altitude-split.md) | Standing spec/plan altitude split (keep /create-spec) | Superseded |
| [0007](0007-living-docs-by-induction.md) | Living architecture, requirements & factual product docs by induction | Accepted |
| [0008](0008-conditional-steps-as-ticket-data.md) | Conditional steps are ticket data, never invocation options | Accepted |
| [0009](0009-clarification-ledger-and-grounding.md) | Clarification ledger + grounding rules | Accepted |
| [0010](0010-explicit-semver-distribution.md) | Explicit-semver distribution with an update assistant | Accepted |
| [0011](0011-sdlc-doc-sets-quality-and-operations.md) | Full-SDLC doc sets (quality, operations) + standing test runs | Proposed |
| [0012](0012-design-time-doc-consistency.md) | Design-time doc-consistency gap & staleness analysis | Proposed |
| [0013](0013-metrics-derives-panels-from-artifacts.md) | acs:metrics derives panels 4-6 from phase artifacts, not a schema extension | Accepted |
| [0014](0014-metrics-helper-emits-json-skill-renders.md) | metrics helper emits aggregate JSON; the skill renders show_widget | Accepted |
| [0015](0015-metrics-single-show-widget-call.md) | acs:metrics renders all six panels in a single show_widget call | Accepted |
| [0016](0016-metrics-bounded-single-pass-walk.md) | metrics aggregation uses a bounded single-pass walk with regex extraction | Accepted |
| [0017](0017-metrics-deterministic-cross-surface-rendering.md) | acs:metrics renders deterministically across surfaces via metrics_render.py | Accepted |
| [0018](0018-distinct-pr-counting-via-created-pr-numbers.md) | Distinct-PR counting via a recorded `created_pr_numbers` set | Accepted |
| [0019](0019-split-acs-metrics-into-pm-and-usage-skills.md) | Split `/acs:metrics` into two narrowly-scoped skills: PM delivery and tool usage | Accepted |
| [0020](0020-ticket-due-date-and-deadline-panel.md) | Deadlines sourced from a `due_date` ticket field (not the GitHub tracker, not deferred) | Accepted |
| [0021](0021-heterogeneous-plugin-contract-via-directory-convention-shapes.md) | Heterogeneous plugin contract via directory-convention shapes | Accepted |
| [0022](0022-behavioral-evals-local-only-ci-runs-no-llm-calls.md) | Behavioral evals are local-only; CI runs no LLM calls | Accepted |
| [0023](0023-tabp-hybrid-quality-mechanism-instruction-driven-plus-stdlib-helper.md) | tabp quality-mechanism: hybrid instruction-driven orchestration plus tabp-namespaced stdlib-Python helper (deliberate divergence from ADR 0001 hook-gated model) | Accepted |
| [0024](0024-tabp-state-in-cowork-project-folder.md) | tabp state in the Cowork project folder (deliberate divergence from ADR 0003 outside-repo rule) | Accepted |
| [0025](0025-tabp-independent-verifier-subagent.md) | tabp independent verifier: inline-artifact input contract and bounded (N=3) remediate-and-re-verify loop | Accepted |
| [0026](0026-tabp-hybrid-cost-sourcing.md) | tabp hybrid cost sourcing: transcript-actuals plus settings-configurable dated-snapshot pricing | Accepted |
| [0027](0027-tabp-dual-runtime-detection.md) | tabp dual-runtime detection: explicit `--runtime` flag with auto-detect fallback (cwd-as-project-dir on Claude Code) | Accepted |
| [0028](0028-merge-pr-agent-invocable.md) | merge-pr is agent/model-invocable; readiness gate + m6 require-APPROVED-for-all | Accepted |
| [0029](0029-merge-pr-auto-update-behind-branch.md) | merge-pr auto-updates a BEHIND branch then merges in the same run | Accepted |
| [0030](0030-four-lane-hybrid-routing-from-size-stakes-axes.md) | Adopt four-lane hybrid routing (TRIVIAL/SMALL/STANDARD/COMPLEX) from size x stakes axes | Accepted |
| [0031](0031-axes-authoritative-lane-derived-cache.md) | Store size + stakes as authoritative axes; lane is a derived cache, recomputable by the routing function | Accepted |
| [0032](0032-lane-field-in-pipeline-state-and-index-writers.md) | Measure G14/G15/G16 by adding one lane field to the existing pipeline-state.json and tickets-index.json writers | Accepted |
| [0033](0033-stakes-first-class-with-path-glob-detection.md) | Treat stakes as a first-class independent axis with configurable path-glob detection | Accepted |
| [0034](0034-light-verify-one-iteration-cap.md) | Light verify = single verifier pass with one-iteration cap; full verify unchanged; TDD/coverage gate immutable in every lane | Accepted |
| [0035](0035-pr-title-ticket-ref-token.md) | Introduce a `pr_title`-only `{ticket_ref}` alternation token instead of overloading `{ticket_id}` | Accepted |
| [0036](0036-compute-ticket-ref-in-build-title.md) | Compute `ticket_ref` inside `build_title` via a `provider` parameter and a `--provider` CLI flag, one uniform template for every caller | Accepted |
| [0037](0037-spec-time-simplicity-evaluation-in-create-spec-planner.md) | Add a spec-time simplicity-evaluation step to the `create-spec-planner` charter, surfaced by the coordinator | Accepted |
| [0038](0038-spec-simplicity-gate-surfaces-never-blocks.md) | The spec-simplicity gate surfaces found alternatives; it never blocks or auto-loops back to re-plan | Accepted |
| [0039](0039-spec-simplicity-gate-planner-only-scope.md) | The spec-simplicity gate is scoped to `create-spec-planner` only; no `create-spec-verifier` dimension or meta-check is added | Accepted |
| [0040](0040-codeowners-derived-pr-reviewers.md) | CODEOWNERS-derived PR reviewers (not a settings key) | Accepted |
| [0041](0041-fixed-field-name-table-group-b-sync.md) | Fixed case-insensitive field-name table for Priority/Story Points/Parent, with type-driven value mapping and tracker-key-valued Parent field | Accepted |
| [0042](0042-dynamic-mid-flight-lane-correctness.md) | Dynamic mid-flight lane correctness | Accepted |
| [0043](0043-suites-map-generalization.md) | `suites` map generalization with soft-deprecated `e2e` alias | Accepted |
| [0044](0044-acs-test-closed-loop-ticketing.md) | `/acs:test` closed-loop ticketing semantics | Accepted |
| [0045](0045-dedicated-acs-e2e-workflow-runner-pair.md) | Dedicated `acs-e2e.yml` + `run-e2e.py` CI workflow pair, independent of the tests gate | Accepted |
| [0046](0046-no-new-settings-key-for-e2e-ci-enforcement.md) | No new settings key for e2e CI enforcement — `settings.e2e`/`suites.e2e` remains the single opt-in signal | Accepted |
| [0047](0047-init-auto-wires-e2e-required-check-report-once.md) | `/acs:init` auto-wires the e2e required check when admin, with a report-once manual-step fallback | Accepted |
| [0048](0048-standardize-project-scaffolds-e2e-no-branch-protection.md) | `/acs:standardize-project` additively scaffolds the e2e workflow + runner for brownfield repos but never wires branch protection itself | Accepted |
| [0049](0049-e2e-3-read-only-g13-metric-validation.md) | Read-only G13 e2e-integrity metric validation from existing merge-pr/spec artifacts, no metrics_aggregate.py panel | Accepted |
| [0050](0050-release-unhooked-utility-skill.md) | `/acs:release` ships as an unhooked utility skill, not a 15th hooked apply-work skill | Accepted |
| [0051](0051-changelog-archive-primary-coverage-check.md) | Changelog aggregation is authoritative, archive-primary with an `[Unreleased]`-coverage cross-check | Accepted |
| [0052](0052-release-exempt-pr-human-merge.md) | Release cuts land via an exempt `release/*` PR that stops for a mandatory human merge | Accepted |
| [0053](0053-release-versions-roadmap-mapping-table.md) | Release versions are modeled as an additive `roadmap.md` mapping table, decoupled from the cut skill | Accepted |
| [0054](0054-settings-driven-release-block.md) | Settings-driven `release` block (JSON-manifest-focused schema, Option A); marketplace = profile #1 | Accepted |
| [0055](0055-promote-mermaid-lint-shared-plugin-helper-blocking-diagram-gate.md) | Promote `mermaid_lint.py` to a shared plugin helper + blocking diagram-lint gate | Accepted |
| [0056](0056-skill-md-required-sections-source-of-truth-structure-helper.md) | SKILL.md-declared `required_sections` as the single source of truth + deterministic structure-conformance helper | Accepted |
| [0057](0057-audience-aware-style-hybrid-advisory-severity.md) | Audience-aware-style HYBRID mechanism, ADVISORY severity | Accepted |
| [0060](0060-functional-non-functional-requirements-model.md) | Functional/non-functional settings-aware requirements MODEL | Accepted |
| [0061](0061-create-requirements-brownfield-reverse-engineer-producer.md) | `/acs:create-requirements` brownfield reverse-engineer producer | Accepted |
| [0062](0062-create-requirements-greenfield-elicitation-draft-discipline.md) | `/acs:create-requirements` greenfield elicitation + uniform DRAFT discipline | Accepted |
| [0063](0063-audience-style-verifier-dimension-advisory-to-blocking-create-spec.md) | Audience-style verifier dimension: ADVISORY → BLOCKING, extended to create-spec | Accepted |
| [0064](0064-evidence-sidecar-code-citation-relocation.md) | Relocate code-evidence citations into per-doc `.evidence.md` sidecars | Accepted |
| [0065](0065-configurable-design-spec-templates-byte-identical-defaults.md) | Configurable design/spec templates with byte-identical built-in defaults | Accepted |
| [0066](0066-fold-spec-authoring-into-code-ticket-json-fixed-point.md) | Supersedes ADR 0006: fold spec-authoring into `/code`'s plan phase for every lane; `ticket.json`'s `acceptance_criteria`/DoD becomes the review loop's fixed point | Accepted |
| [0067](0067-code-verifier-multi-lens-adversarial-rigor-upgrade.md) | code-verifier multi-lens adversarial rigor upgrade (`verify_depth=="full"` only): 4 parallel lenses plus a coordinator adversarial merge pass | Accepted |
| [0068](0068-acs-test-ticket-scoped-fix-and-retest-mode.md) | `/acs:test` ticket-scoped `--for-ticket` mode + `/acs:ship`'s post-code fix-and-re-test loop, gated by e2e presence | Accepted |
| [0069](0069-oversized-ticket-two-lever-split-control.md) | Oversized-ticket split detection is a two-lever control again: `/create-ticket`'s upfront PR-size rubric plus a non-blocking, plan-time oversize signal in `code-planner.md` | Accepted |
| [0070](0070-fix-subprocess-coverage-measurement.md) | Fix subprocess coverage measurement (parallel `.coveragerc` + `COVERAGE_PROCESS_START` + `coverage combine`) instead of duplicating subprocess scenarios as in-process tests | Accepted |
| [0071](0071-coverage-omit-true-forwarder-shims-only.md) | Coverage `omit` rule excludes true argument-forwarder shims only; `post-merge-pr.py`'s real `--pr` branch stays measured, never waived | Accepted |
| [0072](0072-shared-importable-test-fixture.md) | Shared importable test fixture (`tests/acs/acs_case.py`) for concurrent per-module test authoring across child tickets | Accepted |
| [0073](0073-verifier-anchors-on-an-approved-plan.md) | Verifier anchors on an approved plan for a bounded new plan-conformance dimension, amending ADR-0004's verifier-anchoring clause (append-only; ADR-0004 itself unedited) | Accepted |
| [0074](0074-lane-conditional-planning-no-planner-spawn-on-fast-lanes.md) | Lane-conditional planning: `/acs:code`'s coordinator spawns `code-planner` only on STANDARD/COMPLEX; TRIVIAL/SMALL get a coordinator-authored `plan.md` instead | Accepted |
| [0075](0075-planning-implementation-pipeline-split-epics-never-implemented.md) | Pipeline splits into a planning phase (`create-ticket(epic) → create-design → fan-out`) and an implementation phase (`create-ticket → code → … → merge-pr`); epics are never implemented | Accepted |
| [0076](0076-plan-approval-deterministic-predicate-hook-script-sole-writer.md) | Coordinator plan approval: a deterministic predicate, recorded by a hook script, never gated this release | Accepted |
| [0077](0077-docs-sync-remediation-loop-execute-verify-only.md) | Docs-sync remediation loop is execute → verify only, amending ADR-0004's `/acs:code` carve-out to also name `/acs:docs-sync` (append-only; ADR-0004 itself unedited) | Accepted |
| [0078](0078-create-project-remediation-loop-execute-verify-only.md) | Create-project remediation loop is execute → verify only, amending ADR-0004's `/acs:code` carve-out to also name `/acs:create-project` (append-only; ADR-0004 itself unedited) | Accepted |
| [0079](0079-standardize-project-remediation-loop-execute-verify-only.md) | Standardize-project remediation loop is execute → verify only with a frozen iteration-1 additive-surface allowlist, amending ADR-0004's `/acs:code` carve-out and its all-findings-block clause for a narrow, class-scoped plan-conformance degradation (append-only; ADR-0004 itself unedited) | Accepted |
| [0080](0080-plan-conformance-citation-corroboration-hybrid-mechanism.md) | The shared `plan-conformance` verifier dimension across create-quality/-standards/-operations/-principles gains independent, always-blocking citation corroboration — a deterministic `citation_check.py` floor plus a mandatory verifier substantiation ceiling (append-only; ADR-0004 itself unedited) | Accepted |
| [0081](0081-create-prd-plan-conformance-corroboration-three-family-mechanism.md) | `/acs:create-prd`'s dimension 7 "Plan conformance" gains independent, always-blocking three-family corroboration (code-evidence, answer-fidelity, roadmap-outline) via a new `prd_conformance_check.py` script that imports `citation_check.py`'s helpers unchanged, plus a mandatory verifier substantiation ceiling (append-only; ADR-0004 itself unedited) | Accepted |
| [0082](0082-session-anchored-transcript-measurement-statusline-cost-apportionment.md) | Session-anchored transcript measurement with statusLine-sourced real-cost apportionment, superseding an acs-owned price table | Accepted |
| [0083](0083-bootstrap-doc-skills-remediation-loop-execute-verify-only.md) | The 5 bootstrap-doc skills' (`create-prd`/`-quality`/`-standards`/`-operations`/`-principles`) remediation loops become execute → verify only, amending ADR-0004's `/acs:code` carve-out to also name all 5, and superseding ADR-0080's/ADR-0081's loop-topology-unchanged statements (their corroboration-mechanism statements stand) (append-only; ADR-0004/ADR-0080/ADR-0081 themselves unedited) | Accepted |
| [0084](0084-create-architecture-design-requirements-remediation-loop-execute-verify-only.md) | `/acs:create-architecture`'s, `/acs:create-design`'s, and `/acs:create-requirements`'s remediation loops become execute → verify only, completing the plan-once migration across all twelve triad-keeping skills, amending ADR-0004's `/acs:code` carve-out to also name these three (append-only; ADR-0004 itself unedited) | Accepted |
| [0085](0085-doc-bootstrap-parallel-fan-out.md) | Doc-bootstrap parallel fan-out: new unhooked umbrella skill `/acs:create-docs`, phase-level subagent-batch interleave, worktree-per-leg delivery, declared dependency table + eligibility helpers in `acs_lib.py`, v1 eligible set = `create-quality` + `create-operations` | Accepted |
| [0086](0086-in-repo-anchored-state-machine.md) | In-repo, main-checkout-anchored state (`.acs/state-machine`), superseding ADR-0003 | Accepted |
| [0087](0087-ticket-id-allocation-fail-closed-reconciliation.md) | Ticket-id allocation: fail-closed reconciliation gate plus a confirmable ranked local-evidence proposal | Accepted |

Format: status, date, context, decision, consequences (MADR-flavored, kept
short). New ADRs are appended by the pipeline with the next sequence number.
