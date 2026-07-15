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
itself ([functional/workflow.md](functional/workflow.md#living-requirements))
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
2. **End-to-end delivery workflow**: acs MUST provide six
   workflow skills that run in a fixed order (one of them, `/create-design`,
   conditional on the ticket), a `/ship` umbrella command that drives them
   end-to-end up to the PR, and an `/init` bootstrap skill — normative clause
   in [functional/workflow.md](functional/workflow.md).
3. **Quality through reflection**: every workflow skill and every
   product-level skill MUST apply the Reflection pattern: a plan → execute →
   verify cycle using a dedicated subagent for each step — normative clause
   in [functional/reflection.md](functional/reflection.md).
4. **Hook-enforced sequencing**: pre/post hooks MUST gate each skill on the
   completion state of its predecessor and persist each skill's own state —
   normative clause in [functional/hooks.md](functional/hooks.md).
5. **Portability**: the plugin MUST be configurable per user and per project
   via `settings.json` files generated by `/init` — normative clause in
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
| [functional/skills.md](functional/skills.md) | Per-skill requirements (`/init`, `/ship`, `/handoff`, `/create-prd`, `/create-architecture`, `/create-project`, `/create-ticket`, `/create-design`, `/create-spec`, `/code`, `/create-pr`, `/merge-pr`) |
| [functional/reflection.md](functional/reflection.md) | Coordinator–subagents pattern, Reflection (plan–execute–verify), dynamic decomposition, XML communication |
| [functional/hooks.md](functional/hooks.md) | Pre/post hooks per skill: gating, exit codes, state writing |
| [functional/configuration.md](functional/configuration.md) | `/init` skill, `settings.json` scopes and keys |
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
| 2026-07-15 | **Flat `docs/requirements/` reorganized into `functional/` + `non-functional/`**: the 9 flat content files (`overview`, `skills`, `hooks`, `workflow`, `configuration`, `reflection`, `usage`, `workspace-and-state`, `tabp`) are re-split by requirement TYPE into `functional/<feature>.md` (8 files) and `non-functional/<item>.md` (7 files); `overview.md`'s Vision/Goals-framing/Target-domains/Out-of-scope is retained here as context; every repo reference to a `docs/requirements/<file>.md` path is repointed in lockstep (MAR-145 Spec 02). Content-preserving — every existing requirement clause lands in exactly one destination file. |
| 2026-07-15 | **Functional/non-functional settings-aware requirements MODEL adopted**: the new `requirements_layout` settings key (`functional_subdir`/`non_functional_subdir`, defaults `functional`/`non-functional`) resolves the two subfolders; `/acs:code`'s living-requirements merge step now classifies each merged requirement (behavior vs quality) and routes it into the matching subfolder, preserving the existing additive per-area no-overwrite semantics. See ADR 0060 and [functional/configuration.md](functional/configuration.md). |
| 2026-06-15 | `/ship` runs the pipeline by **invoking each step skill directly** in the ship coordinator's own context (it holds the Agent tool the steps need to spawn their planner/executor/verifier) — the fresh-subagent-per-step model is retired, because a subagent cannot spawn subagents. Between steps the coordinator reads only `pipeline-state.json`, `ticket.json`, and the step's `<handoff>` / `result.json`. Supersedes the 2026-06-12 fresh-subagent-per-step handoff row below. See [workflow.md](functional/workflow.md). |
| 2026-06-13 | **Docs restructured into the consumer-repo layout**: the hand-authored requirements corpus (formerly `docs/01–08.md` + `docs/README.md`) was folded into `docs/requirements/` — one file per feature area (`overview`, `workflow`, `skills`, `reflection`, `hooks`, `configuration`, `workspace-and-state`, `usage`) plus this index — so this repo's `docs/` matches the structure acs mandates for every consumer repo (`product/` + `requirements/` + `architecture/` + `adr/`). No special-case numbered corpus; the requirements set now plays the living-requirements role directly. |
| 2026-06-13 | **ADRs are default-on**: `adr_path` defaults to `docs/adr` (explicit `null` disables) — `/code` commits the accepted decision records from each ticket's `design.md` by default; the consumer docs structure is now product/ + requirements/ + architecture/ + adr/. This repo dogfoods it: `docs/adr/` holds the retrofitted architecture decision records. See [configuration.md](functional/configuration.md). |
| 2026-06-13 | **Living requirements** (`requirements_path`, default `docs/requirements/`): consumer repos get a standing behavioral contract that accumulates ticket by ticket — `/code`'s documentation step merges each merged ticket's acceptance criteria and behavior-defining clarifications into the touched feature area's requirements file; `/create-ticket` and `/create-spec` read it as the current behavior of the area and flag contradictions; the code-verifier's documentation dimension blocks drift. Mirrors the living-architecture induction; no new skill. See [workflow.md](functional/workflow.md), [skills.md](functional/skills.md), [configuration.md](functional/configuration.md). |
| 2026-06-13 | **`/update` skill + versioned marketplace**: the marketplace manifest carries a `version`; plugin updates reach consumers only on `plugin.json` semver bumps (automated release tagging). `/update` is a user-invoked upgrade assistant — version comparison, CHANGELOG delta with breaking-change callouts, marketplace refresh, post-update migration checks (settings schema, status-line paths) — never invoked by the model; reloading stays a user action. See [skills.md](functional/skills.md). |
| 2026-06-13 | Reflection phases persist their own artifacts: planner/executor/verifier write `iter-<n>-plan.md` / `-execute.json` / `-verify.md` into the partition; XML results carry file references only; the coordinator snapshots every raw XML message at each phase boundary. Native plan mode is not used (planners are spawned subagents with no user to approve a plan). See [reflection.md](functional/reflection.md). |
| 2026-06-13 | Grounding rules: every subagent decision/claim/finding cites the file/section or quoted command output it rests on; a missing input is an error, never a guess; unverifiable points are explicit assumptions; verifiers treat ungrounded plans/reports as blocking findings. See [reflection.md](functional/reflection.md). |
| 2026-06-13 | Subagent tool restrictions + altitude boundaries: planners/verifiers run on read allowlists (Write only for their own phase artifact), executors cannot spawn agents or invoke skills, coordinators never edit repo source; specs own the WHAT at contract level while the `/code` plan owns the authoritative file map; the code-verifier anchors on the gated contracts (specs/ticket/design) and consumes only the plan's verifier checklist. See [skills.md](functional/skills.md), [reflection.md](functional/reflection.md). |
| 2026-06-13 | Every skill ends a direct invocation with a **standard completion report** (Ticket / Status / Results / Findings / Artifacts / Metrics / Next), rendered only after its post-hook succeeded; under `/ship` the compact XML handoff replaces it. See [skills.md](functional/skills.md). |
| 2026-06-13 | **Size control**: a story/task is sized to ONE reviewable PR (rule of thumb ~<=400 changed lines, one concern); `/create-spec` escalates when an honest decomposition exceeds ~4 specs; `/create-ticket split <id>` converts the ticket to an epic **keeping its id** and mints PR-sized children. See [skills.md](functional/skills.md). |
| 2026-06-13 | **`docs_only` ticket flag** (planner-recommended, user-confirmed at `/create-ticket`): relaxes `/code`'s tests-first and coverage hard-fail; the full suite still runs once and must stay green; a diff line touching executable code under the flag is a blocking finding. Added to the ticket schema. See [skills.md](functional/skills.md). |
| 2026-06-13 | **Requirement clarification ledger**: per-ticket `clarifications.json` — research first, ask once at the cheapest phase (re-asking an answered question is a defect), record every Q&A before acting on it, assumptions are visible debt surfaced until user-confirmed; `/ship` relays answers, the step coordinator records them. See [skills.md](functional/skills.md), [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-13 | **E2E test layer by configuration, not a new skill**: `settings.e2e` (`command`, optional `setup`/`teardown`, `per_iteration` default false); specs declare e2e impact in their test plan, `/code` authors e2e tests in the same changeset, the code-verifier gates on a green suite (no zero-findings verdict without one); `/create-project` scaffolds the harness for user-facing surfaces. See [skills.md](functional/skills.md), [configuration.md](functional/configuration.md). |
| 2026-06-13 | Living-architecture enforcement: the code-verifier makes a positive, evidenced architectural-impact determination per changeset (docs current **by induction**); design/code planners repair area-scoped doc drift (boy-scout) from out-of-band commits; widespread drift triggers a recommended `/create-architecture` re-run. See [workflow.md](functional/workflow.md). |
| 2026-06-13 | Optional **status lines** (`statusLine` prompt line: ticket + pipeline glyphs + cost; `subagentStatusLine`: agent-panel rows for reflection subagents) ship as scripts and are wired opt-in by `/init` with resolved absolute paths — user-owned settings, never forced. See [configuration.md](functional/configuration.md). |
| 2026-06-12 | Hook event binding resolved at implementation: pre-hooks bind to `PreToolUse` on the `Skill` tool via a dispatcher routing to `pre-<skill>.py` (exit 2 blocks); post-hooks are coordinator-invoked scripts backed by the `runs[-1].status` gate (a skipped post-hook leaves the pipeline closed); a `SessionEnd` hook finalizes abnormal endings as `interrupted`. See [hooks.md](functional/hooks.md). |
| 2026-06-12 | Remote ticket import: `/create-ticket <remote-key>` (e.g. a Jira key) pulls the issue from the configured tracker into a local ticket (fresh local id + external mapping, normal analysis applies) so PM-created tickets can be shipped. See [skills.md](functional/skills.md), [usage.md](functional/usage.md). |
| 2026-06-12 | **Every change is a ticket** — including product-level work: each `/create-prd` / `/create-architecture` / `/create-project` run creates its own **delivery ticket** (type task) with a normal id, partition, tracker sync, and archive lifecycle; state files live in the partition; no repo-level state or locks; `/merge-pr` works as for any ticket. Supersedes the reserved-delivery-id scheme below. See [skills.md](functional/skills.md). |
| 2026-06-12 | `ticket_prefix` is **required at `/init`, per repo** (suggested from the repo name) — no global `ACS` default; different consumer repos get different prefixes. Doc examples now use `SHOP-…`. The `ACS` PR label stays (it marks the tool, not the project). See [configuration.md](functional/configuration.md). |
| 2026-06-12 | *(superseded — replaced by real delivery tickets, see above)* Product-level deliveries via reserved delivery ids (`<prefix>-PRD`/`-ARCH`/`-PROJECT`) with repo-level state and locks. Still valid from this decision: `/code` creates the ticket branch, `/create-pr` pushes it and opens the PR; `{external_key}` carries the Jira/GitHub id in formats when synced. |
| 2026-06-12 | PRD layer added: new product-level `/create-prd` skill produces the product definition at `prd_path` (`prd.md`: vision, problem, personas, goals with measurable success metrics, prioritized features, product NFRs, constraints, out-of-scope; `roadmap.md`: milestones → epics). Elicited for greenfield, reverse-engineered as a baseline for existing products; re-runs amend in place. `/create-architecture` now **requires** and is verified against the PRD; `/create-ticket` traces tickets to PRD features and flags divergence (amendment via `/create-prd`, user-confirmed). Conformance chain: **PRD → architecture → design → specs → code**. See [skills.md](functional/skills.md). |
| 2026-06-12 | The umbrella command `/acs` is **renamed to `/ship`** (says what it does; avoids colliding with the plugin name). Older log rows keep the historical name. |
| 2026-06-12 | Greenfield support: new product-level `/create-project` skill scaffolds the repo skeleton from the approved architecture (layout, build, **test framework + coverage tooling**, lint, CI, minimal green vertical slice) — greenfield-only, runs after `/create-architecture`; its verifier must see build/lint/tests pass. Fresh-product flow: `/init` → `/create-architecture` → `/create-project` → MVP epic → `/ship` children. See [workflow.md](functional/workflow.md), [skills.md](functional/skills.md). |
| 2026-06-12 | `acs` = **Autonomous Coding Skills**. Distribution: GitHub URL only. Versioning: semver + CHANGELOG.md + automated releases. See [non-functional/packaging-distribution.md](non-functional/packaging-distribution.md). |
| 2026-06-12 | **All** verifier findings block in the `/code` review loop — remediation runs until zero findings (cap 3). See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Ticket ids: configurable prefix + per-repo sequence (`counters.json`). Schema: title, type, description, acceptance criteria, priority, parent epic, children, status, external mapping, assignee, story points — parent/child links in both directions. See [skills.md](functional/skills.md). |
| 2026-06-12 | Sync conflicts: ask the user. Specs: markdown with required sections (scope, approach, API/data changes, test plan, out-of-scope). See [skills.md](functional/skills.md). |
| 2026-06-12 | Coverage target missed → hard fail, recorded in `code-state.json`. See [skills.md](functional/skills.md). |
| 2026-06-12 | PRs target the default branch and carry the `ACS` label; `merge_strategy` configurable (default squash); post-merge: delete branch, clean worktree, mark ticket done + archive partition. See [skills.md](functional/skills.md). |
| 2026-06-12 | XML messages validated against a formal schema (XSD); decomposition is coordinator-only; parallel executors allowed within a skill. See [reflection.md](functional/reflection.md). |
| 2026-06-12 | Hooks: ticket id via per-checkout pointer file (`sessions/<checkout-id>.json`), branch name fallback; stdlib-only Python 3; abnormal endings still write state; event binding deferred to implementation. See [hooks.md](functional/hooks.md). |
| 2026-06-12 | Config: per-key precedence `settings.local.json` → project `settings.json` → user; machine-specific keys (e.g. `workspace_path`) live in gitignored `settings.local.json`; `/init` re-runs update in place. Placeholder vocabulary, description-template set, and tracker mappings defined in [configuration.md](functional/configuration.md). |
| 2026-06-12 | State: current state + append-only `runs` array; per-ticket `.lock` for parallel worktree sessions; done partitions archived; repo-level `tickets-index.json`, `counters.json`, `sessions/`, `metrics.json`; JSON Schemas shipped with the plugin. See [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-12 | `/acs` context handoff: each skill runs in a fresh subagent context, returns a compact XML handoff; `pipeline-state.json` step ledger lets `/acs` clear/compact context at step boundaries. See [workflow.md](functional/workflow.md). |
| 2026-06-12 | Metrics recorded per run (time, tokens, cost), rolled up per ticket (`pipeline-state.json`) and per repo (`metrics.json`: ticket/PR counts + totals). See [workspace-and-state.md](functional/workspace-and-state.md). |
| 2026-06-12 | Target domains documented: strong fit = automatically testable, git/GitHub-delivered, code/text artifacts (backends, libraries, CLIs, web apps, data pipelines); caveats and out-of-scope listed, incl. `gh`/GitHub being assumed for PRs (other forges = future enhancement). See this file's Target domains section above. |
| 2026-06-12 | Architecture doc set structured as **full system design**: HLD = C4 model levels 1–3 (`hld/c4-context/-container/-component.md`) + overview, data model, deployment, tech stack; LLD = per-flow **sequence diagrams** (`lld/flows/`) + interface contracts; C4 level 4 out of scope. Ticket designs carry sequence diagrams for new/changed flows; `/code` merges them into the LLD; the architecture verifier checks HLD↔LLD agreement. See [skills.md](functional/skills.md). |
| 2026-06-12 | Product-level architecture: ticket-independent `/create-architecture` skill bootstraps a living architecture doc set (overview, components, data model, deployment, tech stack — all diagrams **Mermaid**) at `architecture_path` in the consumer repo; reverse-engineered for existing codebases, elicited for greenfield; delivered as a docs-only PR. `/create-design` designs against it; `/code` keeps it current. Conformance chain: **architecture → design → specs → code**. See [workflow.md](functional/workflow.md), [skills.md](functional/skills.md). |
| 2026-06-12 | Design phase added: conditional `/create-design` between `/create-ticket` and `/create-spec` — epics always, stories/tasks via a `needs_design` flag set during ticket analysis. Produces `design.md` (options & trade-offs, decision & rationale, architecture, risks, rollout) under the full Reflection cycle; specs must conform to it; epic children inherit it (cross-partition read); optional `adr_path` commits decision records into the repo via `/code`. See [workflow.md](functional/workflow.md), [skills.md](functional/skills.md). |
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
