# Requirements

The **living requirements** for `acs` — the standing behavioral contract:
every testable MUST/SHOULD/MAY, organized by feature area, plus the decision
log recording how the contract evolved.

> **Status: IMPLEMENTED (v0.1.0).** These documents are the requirements the
> implementation is built and verified against. The plugin lives at
> `plugins/acs/` (see `plugins/acs/docs/INTERNALS.md` for how requirements map
> onto the Claude Code plugin API). Requirement changes land here first, then
> in the implementation.

## Documentation altitude map

acs is a **specification-defined product**: the behavioral contract IS the
product. The repo carries four doc sets with deliberately different,
non-overlapping jobs — none replaces another:

| Set | Question it answers | Normative for |
|-----|---------------------|---------------|
| [../product/](../product/) (PRD, roadmap) | WHY & WHAT, prioritized | intent, goals, priorities |
| **this set (requirements/)** | the detailed behavioral contract | every testable MUST/SHOULD/MAY; the decision log |
| [../architecture/](../architecture/) (HLD/LLD) | HOW the system is structured | structure, flows, interface contracts |
| [../adr/](../adr/) | WHY a structural choice was made | architecture decision records |

On conflict: the PRD wins on intent and prioritization; this set wins on
behavior; the decision log records how each conflict was settled.
Implementation conventions live in `plugins/acs/docs/` (INTERNALS, AUTHORING).

This is the doc set acs mandates for every consumer repo as the **living
requirements** (`requirements_path`, default `docs/requirements/`): the
current behavioral contract, accumulated ticket by ticket by the pipeline
itself — or bootstrapped via `/acs:create-requirements`
([functional/workflow.md](functional/workflow.md#living-requirements))
— per-ticket specs are change-deltas that get archived, and tests encode how
behavior is verified, not what was agreed. On this repo (acs dogfooding
itself) the set is hand-authored and doubles as the contract-test anchor;
ticket-driven requirement changes land in these files.

## The functional/non-functional model

Each requirement is one of two types, and lives under a matching subfolder
of `requirements_path` (MAR-145): **functional** — a behavior/feature the
software DOES, one file per feature under `functional/`; **non-functional**
— a quality/constraint the software operates WITHIN (performance, security,
reliability, portability, operability, …), one file per NFR item under
`non-functional/`. The two subfolder names default to `functional` and
`non-functional` and resolve via the additive `requirements_layout` settings
key (`requirements_layout.functional_subdir` /
`requirements_layout.non_functional_subdir`) — see
[functional/configuration.md](functional/configuration.md). `/acs:code`'s
living-requirements merge step classifies each merged requirement against the
same functional-vs-non-functional rubric and routes it into the matching
subfolder, preserving the existing additive, per-area, no-overwrite
semantics (see [functional/skills.md](functional/skills.md)).

## Vision

**`acs` (Autonomous Coding Skills)** is a Claude Code plugin providing a
complete, agentic software-delivery workflow: from a raw user request,
through ticketing, design (when needed), specification, TDD implementation,
code review, and pull request creation, all the way to merge.

acs works on **any consumer repository**. All durable state lives in a
user-configured **workspace folder outside the consumer repo**, which also
enables git-worktree-based parallel work.

## Goals

Product-level altitude framing (overlaps the PRD); each goal's normative
clause is carried by the linked functional/ or non-functional/ file, which is
where `/code`'s documentation step and the verifier's documentation dimension
actually enforce it.

1. **Installable plugin**: acs MUST be installable as a Claude Code plugin,
   distributed through a marketplace manifest — normative clause in
   [non-functional/packaging-distribution.md](non-functional/packaging-distribution.md).
2. **End-to-end delivery workflow**: acs MUST provide five
   workflow skills that run in a fixed order, plus one planning skill
   (`/create-design`, conditional on the ticket), a `/ship` umbrella command
   that drives them end-to-end up to the PR, and an `/initialize` bootstrap
   skill — normative clause in [functional/workflow.md](functional/workflow.md).
3. **Quality through reflection**: every workflow skill, the planning skill
   (`/create-design`), and every product-level skill MUST apply the
   Reflection pattern: a plan → execute → verify cycle using a dedicated
   subagent for each step — normative clause in
   [functional/reflection.md](functional/reflection.md).
4. **Hook-enforced sequencing**: pre/post hooks MUST gate each skill on the
   completion state of its predecessor and persist each skill's own state —
   normative clause in [functional/hooks.md](functional/hooks.md).
5. **Portability**: the plugin MUST be configurable per user and per project
   via `settings.json` files generated by `/initialize` — normative clause in
   [non-functional/portability.md](non-functional/portability.md).
6. **Stateless orchestration**: the coordinator MUST NOT rely on conversation
   history between workflow steps; all inter-step knowledge is persisted as
   JSON files in the workspace — normative clause in
   [non-functional/statelessness.md](non-functional/statelessness.md).
7. **Living architecture**: a product-level architecture doc set (Mermaid
   diagrams-as-code) is bootstrapped by `/create-architecture` in the
   consumer repo and kept current by the pipeline — see
   [functional/workflow.md](functional/workflow.md#product-level-architecture).
8. **Greenfield ready**: for a fresh product, the product-level skills
   define the product (PRD), design its architecture, and scaffold the
   project skeleton (test harness, CI, green vertical slice) before the
   first ticket — see
   [functional/workflow.md](functional/workflow.md#starting-a-fresh-product).

## Target domains

`acs` fits wherever three assumptions hold: correctness is verifiable by
**automated tests** (the TDD, coverage, and verifier gates), delivery is
**git/GitHub PR-based**, and the artifact is **code/text** (docs and
diagrams as code).

| Fit | Domains |
|-----|---------|
| Strong | Backend services & APIs (REST/GraphQL/gRPC, microservices), full-stack web apps, libraries/SDKs/frameworks, CLI & developer tooling, data pipelines/ETL, internal tools, integrations/bots — and the `acs` plugin itself (dogfooding). |
| With caveats | Frontend-heavy UI (logic testable; visual/UX verification needs an E2E strategy in the spec's test plan), mobile apps (logic yes; device testing & store delivery out of band), ML applications (serving/app layer yes; model training & experimentation no), infrastructure-as-code (adapted test strategy, per-repo coverage target), games/embedded (host-testable cores only). |
| Out of scope | Work whose correctness automated tests cannot judge (visual design, content, game feel), hardware-in-the-loop testing, non-GitHub forges (GitLab/Bitbucket — a possible future enhancement; `gh` is assumed for PRs). |

## Out of scope (for now)

- Non–Claude Code runtimes for the *implemented* contract. *(OpenAI Codex CLI is a
  planned **second** runtime — see [prd.md](../product/prd.md) "Multi-runtime support"
  and the roadmap. It is not yet implemented; when it ships, gate integrity on Codex is
  best-effort by default and non-bypassable only via org-managed `requirements.toml`
  hooks, since Codex exposes no skill-invocation hook matcher and no `SessionEnd` event.)*

## Documents

One file per behavioral feature under `functional/`, one file per
quality/NFR item under `non-functional/` (MAR-145; subfolder names resolve
via `requirements_layout`, defaults shown).

### functional/

| Doc | Topic |
|-----|-------|
| [functional/workflow.md](functional/workflow.md) | The end-to-end 6-step workflow and step gating |
| [functional/skills.md](functional/skills.md) | Per-skill requirements (`/initialize`, `/ship`, `/handoff`, `/create-prd`, `/create-architecture`, `/create-project`, `/create-ticket`, `/create-design`, `/code`, `/docs-sync`, `/create-pr`, `/merge-pr`) |
| [functional/reflection.md](functional/reflection.md) | Coordinator–subagents pattern, Reflection (plan–execute–verify), dynamic decomposition, XML communication |
| [functional/hooks.md](functional/hooks.md) | Pre/post hooks per skill: gating, exit codes, state writing |
| [functional/configuration.md](functional/configuration.md) | `/initialize` skill, `settings.json` scopes and keys |
| [functional/workspace-and-state.md](functional/workspace-and-state.md) | Workspace folder, `<ticket-id>` partitioning, state files, worktree support |
| [functional/usage.md](functional/usage.md) | Usage walkthroughs: setup, brownfield/greenfield bootstrap, `/ship` vs step-by-step, parallel worktrees, handoff, PRD amendments |
| [functional/tabp.md](functional/tabp.md) | tabp feature areas |

### non-functional/

| Doc | Topic |
|-----|-------|
| [non-functional/packaging-distribution.md](non-functional/packaging-distribution.md) | Plugin bundling, marketplace distribution, semver/CHANGELOG |
| [non-functional/portability.md](non-functional/portability.md) | Per-user/per-project configurability, workspace isolation |
| [non-functional/statelessness.md](non-functional/statelessness.md) | No coordinator conversation-memory dependency; file-based state |
| [non-functional/security.md](non-functional/security.md) | Secrets handling, subagent tool-restriction cross-reference |
| [non-functional/reliability-resumability.md](non-functional/reliability-resumability.md) | Resume/handoff/reconcile qualities (cross-references `functional/`) |
| [non-functional/performance-cost.md](non-functional/performance-cost.md) | Token/cost/time metrics bounds (cross-references `functional/`) |
| [non-functional/quality-gates.md](non-functional/quality-gates.md) | Cross-cutting governance principles: reflection, TDD, review loop, design gate, human merge gate, PRD-at-the-top |

## Decision log

Resolved questions, newest first. Details live in the linked docs.

| Date | Decision |
|------|----------|
| 2026-08-24 | **`/acs:standardize-project`'s reflection loop becomes execute → verify only, with a frozen iteration-1 additive-surface allowlist and a narrow, class-scoped `severity="info"` degradation** (MAR-302, ADR 0079, #377 — amends, without rewriting, the 2026-08-24 MAR-301 row below, whose "…now hold for the **ten** other triad skills" becomes **eight**: `/acs:standardize-project` also keeps its plan artifact's *name* (`iter-<n>-plan.md`), so the naming half of the MAR-70/MAR-71 rows further below still stands for it too, but it no longer writes one per iteration): the plan phase now runs exactly once per run, before the loop — exactly one `standardize-project-planner` subagent is spawned across the whole run, however many iterations it uses, and a resumed run reuses the existing `iter-1-plan.md` instead of spawning a second planner. On iteration 2+, verifier findings are delivered to the executor's `<context>` — never to a new planner spawn — and the executor authors the remediation. The max-3 cap is unchanged in value; it now counts execute+verify rounds rather than plan+execute+verify triads. `/acs:standardize-project` has no lane-conditional planner and no lane-driven verify depth — its cap is a fixed 3 in every lane. Unlike MAR-300/MAR-301, this ticket also closes a genuine plan-conformance-trust gap unique to this skill: the Additive-surface allowlist is authored exactly once, by the iteration-1 planner, and is frozen and authoritative for the whole run — the additive-only guarantee (D6) is unchanged and independently re-verified every iteration by the verifier re-running `git diff --name-status`; and a narrow, class-scoped `severity="info"` degradation routes an out-of-frozen-allowlist `plan-conformance` missing-scaffold finding to `recommended_follow_ups` instead of blocking, while `additive-only` and `doc-set-authorship` findings (and dimension 4's "no unplanned extra scaffold file" clause) always remain blocking; a fail-closed default applies wherever the four-condition conjunction is undetermined. ADR-0079 amends ADR-0004 append-only, ADR-0004 itself unedited. No settings key, schema, state-file shape, or artifact path changes. See [functional/reflection.md](functional/reflection.md), [functional/skills.md](functional/skills.md), [../adr/0079-standardize-project-remediation-loop-execute-verify-only.md](../adr/0079-standardize-project-remediation-loop-execute-verify-only.md), [../architecture/hld/data-model.md](../architecture/hld/data-model.md). |
| 2026-08-24 | **`/acs:create-project`'s reflection loop becomes execute → verify only** (MAR-301, ADR 0078, #374 — amends, without rewriting, the 2026-08-24 MAR-300 row below, whose "…now hold for the **ten** other triad skills" becomes **nine**: `/acs:create-project` also keeps its plan artifact's *name* (`iter-<n>-plan.md`), so the naming half of the MAR-70/MAR-71 rows further below still stands for it too, but it no longer writes one per iteration): the plan phase now runs exactly once per run, before the loop — exactly one `create-project-planner` subagent is spawned across the whole run, however many iterations it uses, and a resumed run reuses the existing `iter-1-plan.md` instead of spawning a second planner. On iteration 2+, verifier findings are delivered to the executor's `<context>` — never to a new planner spawn — and the executor authors the remediation. The max-3 cap is unchanged in value; it now counts execute+verify rounds rather than plan+execute+verify triads. `/acs:create-project` has no lane-conditional planner and no lane-driven verify depth — its cap is a fixed 3 in every lane. The verifier's independent build/lint/test/coverage re-run behavior — ADR-0004's actual subject — is unchanged. ADR-0078 amends ADR-0004 append-only, ADR-0004 itself unedited. No settings key, schema, state-file shape, or artifact path changes. See [functional/reflection.md](functional/reflection.md), [../adr/0078-create-project-remediation-loop-execute-verify-only.md](../adr/0078-create-project-remediation-loop-execute-verify-only.md), [../architecture/hld/data-model.md](../architecture/hld/data-model.md). |
| 2026-08-24 | **`/acs:docs-sync`'s reflection loop becomes execute → verify only** (MAR-300, ADR 0077, #373 — amends, without rewriting, the 2026-08-23 MAR-71 row and the 2026-08-21 MAR-70 row below, whose "the eleven other triad skills" clauses now hold for the **ten** other triad skills: `/acs:docs-sync` keeps the plan artifact's *name* (`iter-<n>-plan.md`), so that half of both rows still stands for it, but no longer writes one per iteration): the plan phase now runs exactly once per run, before the loop — exactly one `docs-sync-planner` subagent is spawned across the whole run, however many iterations it uses, and a resumed run reuses the existing `iter-1-plan.md` instead of spawning a second planner. On iteration 2+, verifier findings are delivered to the executor's `<context>` — never to a new planner spawn — and the executor authors the remediation. The max-3 cap is unchanged in value; it now counts execute+verify rounds rather than plan+execute+verify triads. `/acs:docs-sync` has no lane-conditional planner and no lane-driven verify depth — its cap is a fixed 3 in every lane. The verifier's independent doc-impact re-derivation — ADR-0004's actual subject — is unchanged. ADR-0077 amends ADR-0004 append-only, ADR-0004 itself unedited. No settings key, schema, state-file shape, or artifact path changes. See [functional/reflection.md](functional/reflection.md), [../adr/0077-docs-sync-remediation-loop-execute-verify-only.md](../adr/0077-docs-sync-remediation-loop-execute-verify-only.md), [../architecture/hld/data-model.md](../architecture/hld/data-model.md). |
| 2026-08-24 | **`/acs:code`'s verifier anchors on an approved plan; plan revocation lands** (MAR-74, slice 4 of MAR-69, ADR 0073, #359 — amends, without rewriting, the two 2026-08-23 rows below, which remain true for the plan-approval record's own writer/eligibility mechanics, and the 2026-06-13 "Subagent tool restrictions + altitude boundaries" row below, whose "the code-verifier anchors on the gated contracts (specs/ticket/design) and consumes only the plan's verifier checklist" now holds for every dimension except 15: for that dimension alone, and only under the approval record's eligibility/plan_path/digest conditions, the approved plan's `## Executor tasks & file map` + Approach is additionally a bounded conformance contract, strictly subordinate to dimension 1 — the plan stays a floor, never a ceiling, everywhere else): `code-verifier` gains two new blocking dimensions — 15 (plan conformance: judges only against an approved plan's `## Executor tasks & file map` + Approach, activation computed by the verifier itself from `plan-approval.json`'s `eligible`/`plan_path`/`plan_sha256`, strictly subordinate to dimension 1) and 16 (approval-audit: re-runs `recommend_stakes` over the changed files, blocking on an unaccounted-for high-stakes match); the verifier now reads `plan-approval.json` itself — never a coordinator-relayed value; `plan-superseded-<k>.md` becomes a real, written-and-read artifact of the boundary-gated, `clarify.py`-confirmed plan-revocation path (superseding the 2026-08-23 row's "remains reserved and unused" and the 2026-08-21 row's "neither written nor read today"); ADR-0073 amends ADR-0004 append-only, ADR-0004 itself unedited; approval still gates nothing — the `/create-pr` gate remains `verifier_passed` alone. See [functional/skills.md](functional/skills.md), [functional/reflection.md](functional/reflection.md), [functional/workspace-and-state.md](functional/workspace-and-state.md), [../adr/0073-verifier-anchors-on-an-approved-plan.md](../adr/0073-verifier-anchors-on-an-approved-plan.md), [../architecture/hld/data-model.md](../architecture/hld/data-model.md). |
| 2026-08-23 | **The MAR-70 read-both resume fallback for `/acs:code`'s plan artifact is retired** (MAR-73, slice 3 of MAR-69, #358 — per explicit product decision; amends, without rewriting, the 2026-08-21 row below): `/acs:code` (and its downstream consumers, `/acs:test` and `plan-approval.py`) now read and write only `<partition>/phases/code/plan.md` in every case, on every lane — there is no longer a fallback to the highest-numbered `<partition>/phases/code/iter-*-plan.md` when `plan.md` is absent on resume. A ticket that started before the MAR-70 rename and never completed its transition to `plan.md` is no longer resumable via this path. `<partition>/phases/code/plan-superseded-<k>.md` remains reserved and unused, unaffected by this change. See [functional/skills.md](functional/skills.md). |
| 2026-08-23 | **`/acs:code` records a deterministic plan-approval verdict** (MAR-73, slice 3 of MAR-69, ADR 0076 — amends, without rewriting, the two rows below, which remain true for the plan phase's lane-conditionality and loop topology): computed by `acs_lib.plan_approval_eligible` from the plan artifact's own content plus `settings.test_coverage_percent`, written **only** by `plan-approval.py` to `<partition>/phases/code/plan-approval.json` once per approved plan digest, mirrored to `states.plan_approved`; STANDARD/COMPLEX only; **gates nothing** (the `/create-pr` gate stays `verifier_passed`); no settings key, no schema, no artifact rename; the verifier does not yet anchor on it — that's slice 4. See [functional/skills.md](functional/skills.md), [functional/reflection.md](functional/reflection.md), [../adr/0076-plan-approval-deterministic-predicate-hook-script-sole-writer.md](../adr/0076-plan-approval-deterministic-predicate-hook-script-sole-writer.md), [../architecture/hld/data-model.md](../architecture/hld/data-model.md). |
| 2026-08-23 | **`/acs:code`'s plan phase becomes lane-conditional** (MAR-72, slice 2 of MAR-69, ADR 0074 — amends, without rewriting, the MAR-71 and MAR-70 rows below, which remain true for STANDARD/COMPLEX and for the plan artifact's name on every lane, and the 2026-07-30 ADR-0066 row below, whose `code-planner` fold attribution narrows to the plan's author (`code-planner` on STANDARD/COMPLEX, coordinator on TRIVIAL/SMALL) while the fold's every-lane **activation** — and its `<partition>/specs/`-absent trigger and read-pre-existing-specs behavior — stands unchanged): STANDARD/COMPLEX still spawn exactly one `code-planner`; TRIVIAL/SMALL spawn none and the coordinator authors `plan.md` itself against the identical contract. The lane is the freshly recomputed `derive_lane(...)`, never cached `ticket.lane` (D-2); escalation never retro-spawns a planner (D-3); on fast lanes there is no `<task phase="plan">` message and therefore no `iter-<n>-plan.xml` snapshot (D-4 — this narrows the row below's "message snapshots are unchanged" statement to STANDARD/COMPLEX). Iteration caps, the verifier gate, and the TDD/coverage gate are unchanged. See [functional/reflection.md](functional/reflection.md), [functional/skills.md](functional/skills.md), [functional/workflow.md](functional/workflow.md), [../adr/0074-lane-conditional-planning-no-planner-spawn-on-fast-lanes.md](../adr/0074-lane-conditional-planning-no-planner-spawn-on-fast-lanes.md), [../adr/0066-fold-spec-authoring-into-code-ticket-json-fixed-point.md](../adr/0066-fold-spec-authoring-into-code-ticket-json-fixed-point.md). |
| 2026-08-23 | **`/acs:code`'s reflection loop becomes execute → verify only** (MAR-71, slice 1b of MAR-69 — amends, without rewriting, the 2026-08-21 row below, which remains true for the plan artifact's *name* and for the eleven other triad skills): the plan phase now runs exactly once per run, before the loop — exactly one `code-planner` subagent is spawned across the whole run, however many iterations it uses. On iteration 2+, verifier findings are delivered to the executor's `<context>` — never to a new planner spawn — and the executor authors the remediation. The light=1 / full=3 verify-depth caps are unchanged in value; they now count execute+verify rounds rather than plan+execute+verify triads. Mid-flight escalation (MAR-57)'s detection point and monotone ceiling are unaffected. No settings key, schema, state-file shape, or artifact path changes. See [reflection.md](functional/reflection.md), [skills.md](functional/skills.md), [workflow.md](functional/workflow.md). |
| 2026-08-21 | **`/acs:code`'s plan artifact is renamed to a single per-ticket `plan.md`** (MAR-70, slice 1a of MAR-69 — amends, without rewriting, the 2026-06-13 "Reflection phases persist their own artifacts" row below, which remains true for the eleven other triad skills): the `code-planner` writes `<partition>/phases/code/plan.md`, rewritten in place on each planning iteration, instead of one `iter-<n>-plan.md` per iteration. Read-both compatibility is resume-only for one release — when `plan.md` is absent, `/code` resolves the highest-numbered `<partition>/phases/code/iter-*-plan.md` instead of writing it, never renaming, moving, or copying it. `<partition>/phases/code/plan-superseded-<k>.md` is reserved for a future plan-revocation path (MAR-69 slice 4) and is neither written nor read today. The executor's `-execute[-<k>].json`, the verifier's `-verify.md`, and the per-iteration `phases/code/iter-<n>-plan.xml` message snapshots are unchanged. See [reflection.md](functional/reflection.md), [skills.md](functional/skills.md). |
| 2026-08-20 | **Epic fan-out moves out of an epic's own creation run into `/acs:create-ticket <epic-id> --fan-out`, run after `/create-design`** (MAR-78, amends the 2026-06-12 "Epics fan out" row below — that row is not rewritten in place; this row supersedes it). An epic's own `/create-ticket` run now ends with `children: []`; no child breakdown is proposed at creation time. Children are minted only by the new `--fan-out` mode (or by a split/restructure run), invoked once the epic's design is approved — the proposed breakdown is derived from the design's slice/seam content when present and user-confirmed at the same Step-2 gate. The Step-5 tracker-sync set now also excludes any ticket whose `external` is already non-null, so a `--fan-out` (or split/restructure) run never re-syncs an already-synced ticket as a duplicate. See [functional/skills.md](functional/skills.md), [functional/workflow.md](functional/workflow.md). |
| 2026-08-20 | **`/create-design` is reclassified from a workflow skill to a planning skill**: `acs_lib.PLANNING_SKILLS = ['create-design']` is introduced and `acs_lib.HOOKED_SKILLS = PRODUCT_SKILLS + WORKFLOW_SKILLS + PLANNING_SKILLS` (total membership and the 15-skill hooked count are unchanged, so every hooked consumer — dispatch, skill-start, clarify, metrics, handoff — keeps routing `/create-design` exactly as before); `/acs:ship`'s implementation step table stops listing it as an implementation step (MAR-77). `functional/workflow.md`'s six-step pipeline table is not yet updated to match — that repoint is tracked separately. See [functional/skills.md](functional/skills.md). |
| 2026-08-13 | **The bootstrap skill is renamed from `init` to `initialize`** (invoked as `/acs:initialize`) — a breaking bootstrap-command change, no alias/shim/redirect ships: the skill directory, `acs_lib.UNHOOKED_SKILLS`, and the three skill-name enums (`acs-messages.xsd`, `skill-state.schema.json`, `clarifications.schema.json`) move together (MAR-184). See [functional/configuration.md](functional/configuration.md), [functional/skills.md](functional/skills.md). |
| 2026-07-30 | **`/acs:create-spec` is retired** (ADR 0066): spec authoring is folded into `/code`'s plan phase on every lane — the `code-planner` self-authors the spec content inside its plan artifact when `<partition>/specs/` is absent or empty, and still reads a pre-existing `specs/` directory when one is present; the vacated pipeline slot goes to `/docs-sync` (MAR-160), which runs after `/code` and before `/create-pr`. See [functional/skills.md](functional/skills.md), [functional/workflow.md](functional/workflow.md). |
| 2026-07-28 | **`coordinator` role retired from the `models` settings contract**: acs no longer supports a distinct coordinator model tier — `models.coordinator` and `overrides.<skill>.coordinator` are removed from the schema and settings; the default planner/verifier tier renames from `claude-opus-4-8` to `claude-opus-5`. The ship coordinator's own session simply inherits whatever model/effort the invoking session already has, with no configurable override left in settings. Supersedes the two 2026-06-12 rows below ("Coordinator model is configurable..." and "Per-role subagent models configurable..."). See [configuration.md](functional/configuration.md). |
| 2026-07-15 | **`/acs:create-requirements` bootstrap/amend path**: the requirements doc set can now be bootstrapped in one run — brownfield (reverse-engineer from code), greenfield (elicit from the user), or amend (augment absent/ungrounded areas, preserve existing files byte-for-byte) — as an alternative to organic ticket-by-ticket growth; every produced requirement is DRAFT / human-confirm-required (uniform across all three modes, C-22). Decision D1 outcome: requirements stays a **living contract** alongside the (unchanged) conformance chain, **not** a verified conformance level — no code-verifier dimension gates a ticket against it. See [../architecture/lld/contracts.md](../architecture/lld/contracts.md), ADR 0060/0061/0062, and [functional/skills.md](functional/skills.md). |
| 2026-07-15 | **Flat `docs/requirements/` reorganized into `functional/` + `non-functional/`**: the 9 flat content files (`overview`, `skills`, `hooks`, `workflow`, `configuration`, `reflection`, `usage`, `workspace-and-state`, `tabp`) are re-split by requirement TYPE into `functional/<feature>.md` (8 files) and `non-functional/<item>.md` (7 files); `overview.md`'s Vision/Goals-framing/Target-domains/Out-of-scope is retained here as context; every repo reference to a `docs/requirements/<file>.md` path is repointed in lockstep (MAR-145 Spec 02). Content-preserving — every existing requirement clause lands in exactly one destination file. |
| 2026-07-15 | **Functional/non-functional settings-aware requirements MODEL adopted**: the new `requirements_layout` settings key (`functional_subdir`/`non_functional_subdir`, defaults `functional`/`non-functional`) resolves the two subfolders; `/acs:code`'s living-requirements merge step now classifies each merged requirement (behavior vs quality) and routes it into the matching subfolder, preserving the existing additive per-area no-overwrite semantics. See ADR 0060 and [functional/configuration.md](functional/configuration.md). |
| 2026-06-15 | `/ship` runs the pipeline by **invoking each step skill directly** in the ship coordinator's own context (it holds the Agent tool the steps need to spawn their planner/executor/verifier) — the fresh-subagent-per-step model is retired, because a subagent cannot spawn subagents. Between steps the coordinator reads only `pipeline-state.json`, `ticket.json`, and the step's `<handoff>` / `result.json`. Supersedes the 2026-06-12 fresh-subagent-per-step handoff row below. See [workflow.md](functional/workflow.md). |
| 2026-06-13 | **Docs restructured into the consumer-repo layout**: the hand-authored requirements corpus (formerly `docs/01–08.md` + `docs/README.md`) was folded into `docs/requirements/` — one file per feature area (`overview`, `workflow`, `skills`, `reflection`, `hooks`, `configuration`, `workspace-and-state`, `usage`) plus this index — so this repo's `docs/` matches the structure acs mandates for every consumer repo (`product/` + `requirements/` + `architecture/` + `adr/`). No special-case numbered corpus; the requirements set now plays the living-requirements role directly. |
| 2026-06-13 | **ADRs are default-on**: `adr_path` defaults to `docs/adr` (explicit `null` disables) — `/code` commits the accepted decision records from each ticket's `design.md` by default; the consumer docs structure is now product/ + requirements/ + architecture/ + adr/. This repo dogfoods it: `docs/adr/` holds the retrofitted architecture decision records. See [configuration.md](functional/configuration.md). |
| 2026-06-13 | **Living requirements** (`requirements_path`, default `docs/requirements/`): consumer repos get a standing behavioral contract that accumulates ticket by ticket — `/code`'s documentation step merges each merged ticket's acceptance criteria and behavior-defining clarifications into the touched feature area's requirements file; `/create-ticket` reads it as the current behavior of the area and flags contradictions; the code-verifier's documentation dimension blocks drift. Mirrors the living-architecture induction; no new skill. See [workflow.md](functional/workflow.md), [skills.md](functional/skills.md), [configuration.md](functional/configuration.md). |
| 2026-06-13 | **`/update` skill + versioned marketplace**: the marketplace manifest carries a `version`; plugin updates reach consumers only on `plugin.json` semver bumps (automated release tagging). `/update` is a user-invoked upgrade assistant — version comparison, CHANGELOG delta with breaking-change callouts, marketplace refresh, post-update migration checks (settings schema, status-line paths) — never invoked by the model; reloading stays a user action. See [skills.md](functional/skills.md). |
| 2026-06-13 | Reflection phases persist their own artifacts: planner/executor/verifier write `iter-<n>-plan.md` / `-execute.json` / `-verify.md` into the partition; XML results carry file references only; the coordinator snapshots every raw XML message at each phase boundary. Native plan mode is not used (planners are spawned subagents with no user to approve a plan). See [reflection.md](functional/reflection.md). |
| 2026-06-13 | Grounding rules: every subagent decision/claim/finding cites the file/section or quoted command output it rests on; a missing input is an error, never a guess; unverifiable points are explicit assumptions; verifiers treat ungrounded plans/reports as blocking findings. See [reflection.md](functional/reflection.md). |
| 2026-06-13 | Subagent tool restrictions + altitude boundaries: planners/verifiers run on read allowlists (Write only for their own phase artifact), executors cannot spawn agents or invoke skills, coordinators never edit repo source; specs own the WHAT at contract level while the `/code` plan owns the authoritative file map; the code-verifier anchors on the gated contracts (specs/ticket/design) and consumes only the plan's verifier checklist. See [skills.md](functional/skills.md), [reflection.md](functional/reflection.md). |
| 2026-06-13 | Every skill ends a direct invocation with a **standard completion report** (Ticket / Status / Results / Findings / Artifacts / Metrics / Next), rendered only after its post-hook succeeded; under `/ship` the compact XML handoff replaces it. See [skills.md](functional/skills.md). |
| 2026-06-13 | **Size control**: a story/task is sized to ONE reviewable PR (rule of thumb ~<=400 changed lines, one concern), enforced at two levers — `/create-ticket`'s upfront rubric plus a non-blocking, plan-time oversize signal in `code-planner.md` (ADR 0069) that surfaces through the clarification ledger and never halts the run; `/create-ticket split <id>` converts the ticket to an epic **keeping its id** and mints PR-sized children, and a "split" answer terminates `/code` with a recorded `failed` status. See [skills.md](functional/skills.md). |
| 2026-06-13 | **`docs_only` ticket flag** (planner-recommended, user-confirmed at `/create-ticket`): relaxes `/code`'s tests-first and coverage hard-fail; the full suite still runs once and must stay green; a diff line touching executable code under the flag is a blocking finding. Added to the ticket schema. See [skills.md](functional/skills.md). |
| 2026-06-13 | **Requirement clarification ledger**: per-ticket `clarifications.json` — research first, ask once at the cheapest phase (re-asking an answered question is a defect), record every Q&A before acting on it, assumptions are visible debt surfaced until user-confirmed; `/ship` relays answers, the step coordinator records them. See [skills.md](functional/skills.md), [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-13 | **E2E test layer by configuration, not a new skill**: `settings.e2e` (`command`, optional `setup`/`teardown`, `per_iteration` default false); specs declare e2e impact in their test plan, `/code` authors e2e tests in the same changeset, the code-verifier gates on a green suite (no zero-findings verdict without one); `/create-project` scaffolds the harness for user-facing surfaces. See [skills.md](functional/skills.md), [configuration.md](functional/configuration.md). |
| 2026-06-13 | Living-architecture enforcement: the code-verifier makes a positive, evidenced architectural-impact determination per changeset (docs current **by induction**); design/code planners repair area-scoped doc drift (boy-scout) from out-of-band commits; widespread drift triggers a recommended `/create-architecture` re-run. See [workflow.md](functional/workflow.md). |
| 2026-06-13 | Optional **status lines** (`statusLine` prompt line: ticket + pipeline glyphs + cost; `subagentStatusLine`: agent-panel rows for reflection subagents) ship as scripts and are wired opt-in by `/initialize` with resolved absolute paths — user-owned settings, never forced. See [configuration.md](functional/configuration.md). |
| 2026-06-12 | Hook event binding resolved at implementation: pre-hooks bind to `PreToolUse` on the `Skill` tool via a dispatcher routing to `pre-<skill>.py` (exit 2 blocks); post-hooks are coordinator-invoked scripts backed by the `runs[-1].status` gate (a skipped post-hook leaves the pipeline closed); a `SessionEnd` hook finalizes abnormal endings as `interrupted`. See [hooks.md](functional/hooks.md). |
| 2026-06-12 | Remote ticket import: `/create-ticket <remote-key>` (e.g. a Jira key) pulls the issue from the configured tracker into a local ticket (fresh local id + external mapping, normal analysis applies) so PM-created tickets can be shipped. See [skills.md](functional/skills.md), [usage.md](functional/usage.md). |
| 2026-06-12 | **Every change is a ticket** — including product-level work: each `/create-prd` / `/create-architecture` / `/create-project` run creates its own **delivery ticket** (type task) with a normal id, partition, tracker sync, and archive lifecycle; state files live in the partition; no repo-level state or locks; `/merge-pr` works as for any ticket. Supersedes the reserved-delivery-id scheme below. See [skills.md](functional/skills.md). |
| 2026-06-12 | `ticket_prefix` is **required at `/initialize`, per repo** (suggested from the repo name) — no global `ACS` default; different consumer repos get different prefixes. Doc examples now use `SHOP-…`. The `ACS` PR label stays (it marks the tool, not the project). See [configuration.md](functional/configuration.md). |
| 2026-06-12 | *(superseded — replaced by real delivery tickets, see above)* Product-level deliveries via reserved delivery ids (`<prefix>-PRD`/`-ARCH`/`-PROJECT`) with repo-level state and locks. Still valid from this decision: `/code` creates the ticket branch, `/create-pr` pushes it and opens the PR; `{external_key}` carries the Jira/GitHub id in formats when synced. |
| 2026-06-12 | PRD layer added: new product-level `/create-prd` skill produces the product definition at `prd_path` (`prd.md`: vision, problem, personas, goals with measurable success metrics, prioritized features, product NFRs, constraints, out-of-scope; `roadmap.md`: milestones → epics). Elicited for greenfield, reverse-engineered as a baseline for existing products; re-runs amend in place. `/create-architecture` now **requires** and is verified against the PRD; `/create-ticket` traces tickets to PRD features and flags divergence (amendment via `/create-prd`, user-confirmed). Conformance chain: **PRD → architecture → design → specs → code**. See [skills.md](functional/skills.md). |
| 2026-06-12 | The umbrella command `/acs` is **renamed to `/ship`** (says what it does; avoids colliding with the plugin name). Older log rows keep the historical name. |
| 2026-06-12 | Greenfield support: new product-level `/create-project` skill scaffolds the repo skeleton from the approved architecture (layout, build, **test framework + coverage tooling**, lint, CI, minimal green vertical slice) — greenfield-only, runs after `/create-architecture`; its verifier must see build/lint/tests pass. Fresh-product flow: `/initialize` → `/create-architecture` → `/create-project` → MVP epic → `/ship` children. See [workflow.md](functional/workflow.md), [skills.md](functional/skills.md). |
| 2026-06-12 | `acs` = **Autonomous Coding Skills**. Distribution: GitHub URL only. Versioning: semver + CHANGELOG.md + automated releases. See [non-functional/packaging-distribution.md](non-functional/packaging-distribution.md). |
| 2026-06-12 | **All** verifier findings block in the `/code` review loop — remediation runs until zero findings (cap 3). See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Ticket ids: configurable prefix + per-repo sequence (`counters.json`). Schema: title, type, description, acceptance criteria, priority, parent epic, children, status, external mapping, assignee, story points — parent/child links in both directions. See [skills.md](functional/skills.md). |
| 2026-06-12 | Sync conflicts: ask the user. Specs: markdown with required sections (scope, approach, API/data changes, test plan, out-of-scope). See [skills.md](functional/skills.md). |
| 2026-06-12 | Coverage target missed → hard fail, recorded in `code-state.json`. See [skills.md](functional/skills.md). |
| 2026-06-12 | PRs target the default branch and carry the `ACS` label; `merge_strategy` configurable (default squash); post-merge: delete branch, clean worktree, mark ticket done + archive partition. See [skills.md](functional/skills.md). |
| 2026-06-12 | XML messages validated against a formal schema (XSD); decomposition is coordinator-only; parallel executors allowed within a skill. See [reflection.md](functional/reflection.md). |
| 2026-06-12 | Hooks: ticket id via per-checkout pointer file (`sessions/<checkout-id>.json`), branch name fallback; stdlib-only Python 3; abnormal endings still write state; event binding deferred to implementation. See [hooks.md](functional/hooks.md). |
| 2026-06-12 | Config: per-key precedence `settings.local.json` → project `settings.json` → user; machine-specific keys (e.g. `workspace_path`) live in gitignored `settings.local.json`; `/initialize` re-runs update in place. Placeholder vocabulary, description-template set, and tracker mappings defined in [configuration.md](functional/configuration.md). |
| 2026-06-12 | State: current state + append-only `runs` array; per-ticket `.lock` for parallel worktree sessions; done partitions archived; repo-level `tickets-index.json`, `counters.json`, `sessions/`, `metrics.json`; JSON Schemas shipped with the plugin. See [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-12 | `/acs` context handoff: each skill runs in a fresh subagent context, returns a compact XML handoff; `pipeline-state.json` step ledger lets `/acs` clear/compact context at step boundaries. See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Metrics recorded per run (time, tokens, cost), rolled up per ticket (`pipeline-state.json`) and per repo (`metrics.json`: ticket/PR counts + totals). See [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-12 | Target domains documented: strong fit = automatically testable, git/GitHub-delivered, code/text artifacts (backends, libraries, CLIs, web apps, data pipelines); caveats and out-of-scope listed, incl. `gh`/GitHub being assumed for PRs (other forges = future enhancement). See this file's Target domains section above. |
| 2026-06-12 | Architecture doc set structured as **full system design**: HLD = C4 model levels 1–3 (`hld/c4-context/-container/-component.md`) + overview, data model, deployment, tech stack; LLD = per-flow **sequence diagrams** (`lld/flows/`) + interface contracts; C4 level 4 out of scope. Ticket designs carry sequence diagrams for new/changed flows; `/code` merges them into the LLD; the architecture verifier checks HLD↔LLD agreement. See [skills.md](functional/skills.md). |
| 2026-06-12 | Product-level architecture: ticket-independent `/create-architecture` skill bootstraps a living architecture doc set (overview, components, data model, deployment, tech stack — all diagrams **Mermaid**) at `architecture_path` in the consumer repo; reverse-engineered for existing codebases, elicited for greenfield; delivered as a docs-only PR. `/create-design` designs against it; `/code` keeps it current. Conformance chain: **architecture → design → specs → code**. See [workflow.md](functional/workflow.md), [skills.md](functional/skills.md). |
| 2026-06-12 | Design phase added: conditional `/create-design` between `/create-ticket` and `/code` — epics always, stories/tasks via a `needs_design` flag set during ticket analysis. Produces `design.md` (options & trade-offs, decision & rationale, architecture, risks, rollout) under the full Reflection cycle; specs must conform to it; epic children inherit it (cross-partition read); optional `adr_path` commits decision records into the repo via `/code`. See [workflow.md](functional/workflow.md), [skills.md](functional/skills.md). |
| 2026-06-12 | Docs updates are part of `/code`: affected consumer-repo documentation (README, API/usage docs, comments, changelog per repo convention) is updated with the change; **documentation** added to the verifier's review dimensions; specs flag docs impact in the API/data changes section. See [skills.md](functional/skills.md). |
| 2026-06-12 | Reasoning **effort** configurable alongside models: a role accepts a model string or `{model, effort}` object; model and effort resolve independently (per-skill override → role default → inherit); unsupported effort fails at spawn. See [configuration.md](functional/configuration.md). |
| 2026-06-12 | Coordinator model is configurable but enforceable only for `/acs`-spawned coordinators; direct invocations run on the session model, and the skill surfaces a notice if `models.coordinator` is set and differs (no silent divergence). See [configuration.md](functional/configuration.md). |
| 2026-06-12 | Per-role subagent models configurable in `settings.json`: `models.planner/executor/verifier` (+ `models.coordinator` for `/acs`-spawned coordinators), per-skill overrides, `inherit` default, no silent fallback on unknown ids. See [configuration.md](functional/configuration.md). |
| 2026-06-12 | Session handoff: a long session hands a ticket to a fresh one via a graceful flush — soft context persisted, run entry finalized as `handed_off` with a summary, lock released; triggered by the new `/handoff` utility skill or proactively by coordinators on context pressure. See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Resume designed in at three levels: between steps (ledger + gates), within `/acs` (first incomplete step), and mid-skill (`in_progress` run entry written at skill start, phase-boundary persistence, reconcile mode on re-run; `.lock` re-entrant per checkout). See [workflow.md](functional/workflow.md). |
| 2026-06-12 | State files normalized — no duplicated fields: status/stop reason live only on `runs` entries (last entry = current state, pre-hooks gate on `runs[-1].status`); durations computed from timestamps; `skill`/`ticket_id` kept in-file deliberately for self-description after archiving. See [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-12 | **`/review-code` is removed.** The `code-verifier` performs the changeset-level review inside `/code`; the review/remediation loop is internal to `/code`. Supersedes the three earlier review decisions below. See [skills.md](functional/skills.md). |
| 2026-06-12 | `/acs` umbrella command added: runs `/create-ticket` → `/create-spec` → `/code` → `/create-pr` end-to-end, stopping before the user-invoked `/merge-pr`. *(Amended by the design-phase decision above: `/create-design` now runs conditionally between `/create-ticket` and `/create-spec`.)* See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Epic status lifecycle: **In Progress** when work starts on any child, **Done** when all children are merged. See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Tracker pulls are **on-demand** for now; scheduled sync routines are a later enhancement. See [skills.md](functional/skills.md). |
| 2026-06-12 | Reflection/remediation iteration cap confirmed: **3**. See [reflection.md](functional/reflection.md). |
| 2026-06-12 | `/merge-pr` readiness failure is **report-only** — it never routes fixes back to `/code` automatically. See [skills.md](functional/skills.md). |
| 2026-06-12 | *(superseded)* The review → code feedback loop is automatic: blocking findings re-enter `/code` until the review passes — the loop is now internal to `/code`. |
| 2026-06-12 | `/merge-pr` is a **user action**: invoked explicitly after the user has reviewed the PR themselves; the pipeline never triggers it. See [skills.md](functional/skills.md). |
| 2026-06-12 | Epics auto-complete when all child tickets are merged. See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Tracker sync is **two-way**; `ticket.json` holds the local-id ↔ remote-key mapping (e.g. Jira key); access via the `gh` CLI (GitHub) and `acli` (Jira). See [configuration.md](functional/configuration.md). |
| 2026-06-12 | `<repo>` partition identity derives from the git remote, so all worktrees of a repo share one partition. See [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-12 | Branch name format is configurable (`formats.branch_name`, must embed the ticket id); long descriptions (PR, tickets) use **pre-defined templates**. See [configuration.md](functional/configuration.md). |
| 2026-06-12 | *(superseded)* No duplicated review work: `/review-code` consumes `code-state.json` as trusted input instead of re-running the `code-verifier`'s checks. |
| 2026-06-12 | *(superseded)* `/review-code` stays a separate skill: the `code-verifier` checks spec/TDD conformance (micro), `/review-code` reviews the whole changeset (macro). |
| 2026-06-12 | Epics fan out: `/create-ticket` suggests creating child story/task tickets; each child runs its own pipeline. See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Tickets are **local-first**; optional sync to a GitHub Project or Jira board, driven by `settings.json`. See [skills.md](functional/skills.md), [configuration.md](functional/configuration.md). |
| 2026-06-12 | Workspace is partitioned by repo, then ticket: `<workspace>/<repo>/<ticket-id>/`. See [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-12 | Ticket id for skills after `/create-ticket`: explicit argument, else detected from session context or branch name. See [workflow.md](functional/workflow.md). |
| 2026-06-12 | PR title/description, commit message, and per-ticket-type ticket formats are configurable in `settings.json`. See [configuration.md](functional/configuration.md). |

## Conventions used in these docs

- **MUST / MUST NOT** — a hard requirement.
- **SHOULD** — a strong default; deviation needs a reason.
- **MAY** — optional / nice to have.
- **[OPEN]** — an open question to be resolved before implementation.
- **[ASSUMPTION]** — a proposed interpretation not yet confirmed by the
  product owner; treat as provisional.

## Glossary

| Term | Meaning |
|------|---------|
| **Marketplace** | The Claude Code plugin marketplace (`gms-marketplace`) this repo publishes, through which `acs` is distributed. |
| **`acs` plugin** | The plugin implementing the delivery workflow these requirements describe. |
| **Consumer repo** | Any user repository where the `acs` plugin is installed and used. |
| **Workspace** | A folder *outside* the consumer repo where all skills and hooks read/write state, partitioned per repo and ticket. |
| **Coordinator** | The main agent that orchestrates a skill's subagents. |
| **Subagent** | A planner, executor, or verifier agent spawned by the coordinator for one step of a skill. |
| **Skill state file** | A JSON file (e.g. `code-state.json`) written into the workspace recording a skill's outcome, with an append-only `runs` history. |
| **Pipeline ledger** | `pipeline-state.json` — a compact per-ticket step ledger (status, timestamps, handoff summaries) used by `/ship` and pre-hooks. |
