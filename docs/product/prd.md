# PRD — GMS Marketplace

> Bootstrapped as the dogfood baseline, derived from the requirements set
> (`docs/requirements/`) and the implemented plugin. Amendments go through
> `/acs:create-prd` re-runs — each amendment is its own delivery ticket and
> docs PR. This PRD covers the GMS Marketplace product and its plugin features
> (acs, active; tabp, retired — see the MAR-97 Reversal note in Out of scope;
> and future plugins); each plugin is a distinct capability delivered and
> updated through one marketplace.

## Vision

The GMS Marketplace is a curated catalog of Global Mind Solution Claude plugins,
each plugin a distinct team capability — coding delivery today, with future
capabilities added through a documented, gated onboarding path (see **G20**) —
delivered and kept current through one marketplace. Teams adopt exactly the
plugins they need; the marketplace ensures versioning, discoverability, and
consistent quality across all plugins. The catalog grows through that gated
onboarding path, and every catalog plugin meets a shared quality bar
(trigger-eval baseline + namespace isolation) — see **G20**.

acs's primary near-term consumer, alongside this repo's own dogfooding, is an
**external commercial consumer product** (an agentic hiring SaaS) delivered
*using* acs: acs runs the same gated pipeline against that product's codebase
as it does against this one. That consumer product is **not a marketplace
plugin** — it is a consumer of acs like any other repo, not a catalog entry —
see **G30** and the Out-of-scope external-consumer-product scope-clarity note.

The **acs** feature delivers: every software change — from product definition to
merged PR — driven through one auditable, resumable, hook-enforced agentic
pipeline, on any consumer repository, with the human owning **requirement
decisions**. Merge is **gated, not ungoverned**: `/acs:merge-pr` is invocable by the
user *or* an authorized agent/model, and a merge happens only when the readiness gate
(CI, approvals, conflicts, protections) **and** the repo's branch protection pass, by
whoever invokes — failures are report-only and every attempt is audited;
agent-invoked merges additionally require an **approved** review, **scoped by
invoker**: the approved-review mandate applies to agent-invoked merges only, while
human-invoked merges defer to the repo's own branch protection, and an out-of-band
merge is **reconciled, not stranded** (see **G26**). `/acs:ship` still
deliberately stops at create-pr so a reviewer sees the PR before merge. acs **meets
teams where they are**: when a team has no PRD/roadmap/architecture and its PO works
only in a remote tracker, the pipeline runs **tracker-first** — the tracker issue
(description + acceptance criteria) governs as the requirement source of truth and the
**same gates** (TDD, coverage, review, audit, merge readiness) still apply; no PRD is
required to deliver, and none is ever auto-authored without opt-in.

## Problem

GMS teams need a single curated source of vetted, versioned Claude plugins that
each solve a distinct team problem — coding delivery via acs today — instead
of ad-hoc one-off tools with no shared versioning, quality bar, or
discoverability. Future problem domains are added through the catalog's
documented, gated onboarding path and quality bar (**G20**), not by
proliferating one-off tools outside the marketplace.

**acs feature problem:** Agentic coding today loses state between sessions, skips steps when the model
forgets, mixes planning with implementation in one context, and leaves no
audit trail of what was decided, built, verified, and why. Teams cannot trust
a pipeline whose ordering depends on model goodwill, and cannot resume or
parallelize work that lives in a conversation window. Many teams, moreover,
never produce a PRD/roadmap/architecture at all — their PO authors requirements
only in a remote tracker (e.g. Jira) and may not know how to create the upstream
docs. A pipeline that **requires** a PRD to start locks those teams out; they
need to deliver tracker-defined work through the same gates without first
authoring product docs they do not have.

Today the pipeline runs the full plan-execute-verify ladder (create-ticket →
[create-design] → create-spec → code → create-pr → merge-pr) on **every** ticket
regardless of size. An over-engineering audit found that a trivial one-line ticket
pays ~5 coordinators + ~15 subagent spawns (~20 fresh model contexts), so simple,
supervised changes cost disproportionate wall-clock time and token/cost. The rigor
that is the product is right for unattended and complex work, but is double-paid on
interactive simple work where a human is already the reviewer. Rigor is scaled today
by design-significance (the `needs_design` flag) but never by implementation size or
supervision level. A residual problem remains even once a lane is assigned: the lane
fixed once at create-ticket can be **wrong for what the change turns out to be** — a
fast-lane ticket can, mid-implementation, touch a high-stakes surface (auth,
migrations, money paths) that was not visible at ticket creation, so the pipeline
needs to **re-decide the lane in flight** rather than under-verify on a stale
create-time assumption.

**tabp feature problem — *(RETIRED — superseded by an external consumer product; see the MAR-97 Reversal note in Out of scope)*:** Manual CV-vs-JD screening is slow, inconsistent, and hard to audit for
fairness — hiring managers cannot reproduce scoring decisions or demonstrate
that protected characteristics played no role. tabp was a team-demo answer to
this problem; it is retired, and the problem is now addressed by the external
consumer product, not by a marketplace plugin.

**acs team-scale problem:** acs's durable delivery state (ticket ids, the tickets
index, locks, per-repo metrics, clarification ledgers) lives in a **per-user local
workspace**, while the repo id/prefix a workspace resolves to is shared (derived from
the git remote). A team of engineers working the same repo therefore computes the
**same** ticket prefix but writes to **separate, unsynced local workspaces**: ticket-id
allocation collides across engineers (two engineers can independently mint the same
ticket id), there is no shared visibility into which teammate holds the lock on an
in-progress ticket, and metrics/observability stay per-person rather than team-wide.
Beyond delivery state, the settings cascade has no org- or department-level source
today (only user → project → local) — a team-shared *non-enforcement* default (models,
tracker, doc paths, formats) or a shared-workspace convention can only be distributed
by hand-copying the committed project file to every repo, and org-wide policy
enforcement (G12) does not yet cover this defaults/distribution half.

**acs merge-gate-friction problem:** ADR-0028's mitigation **m6** requires an
**APPROVED review for every** `/acs:merge-pr` merge, implemented as the conservative
**require-APPROVED-for-all** fallback because the coordinator cannot reliably tell an
agent invocation from a direct human one. On a solo-author repo whose own branch
protection requires zero reviews, GitHub forbids self-approval, so a solo author can
never satisfy m6 and therefore cannot use `/acs:merge-pr` at all — the sanctioned merge
path is a phantom gate for exactly the users most likely to run it. The observed
consequence is PRs merged **out-of-band** directly on GitHub, bypassing
`/acs:merge-pr`; each such merge strands the ticket at `in_review` (never archived, no
tracker-Status→Done transition, metrics never bumped), and today there is no visibility
into how often merges bypass the sanctioned path.

**acs brownfield-coverage problem:** the single repo-wide `test_coverage_percent`
hard-fail (default 90) is blunt on a legacy codebase already below that bar — it either
blocks all delivery until a large backfill lands or forces lowering the bar globally,
and neither option ratchets new code upward while tolerating pre-existing legacy debt.

## Target users & personas

| Persona | Need |
|---------|------|
| **Solo developer** | Ship features end-to-end with one command (`/acs:ship`), trust the gates instead of self-discipline, resume after any interruption. |
| **Tech lead** | Enforce a delivery process (design gates, TDD, review dimensions, PR size) uniformly across repos and teammates; inspect any ticket's full audit trail. |
| **Team on a shared repo** | Parallel tickets in worktrees without state collisions; team-shared settings; tracker sync to Jira / GitHub Projects; shared ticket/id/lock/metrics state across engineers (not just worktrees on one machine), so no cross-engineer id collisions and every teammate can see who holds an in-progress ticket's lock. |
| **Team with a tracker-only PO** | Deliver requirements that live only in a remote tracker (Jira), with no PRD/roadmap/architecture and no need to author one — the tracker issue governs, and the full gated pipeline (TDD, coverage, review, audit) still applies. |
| **Org / Platform admin (Security/Compliance owner)** | Apply organization-wide enforcement policy — required convention checks, security gates, standards/conventions floors — across *all* of the org's repos, cascading through **department** and project layers (most-specific-wins, floors compose down, never loosen); guarantee repos cannot silently loosen or self-exempt from a mandate; see which layer each effective rule came from and who can change it (provenance/audit); ALSO distribute org- and department-wide shared, overridable defaults (models, tracker, doc paths, formats) and a shared/central workspace convention to all org repos, without hand-duplicating settings per repo; consume/maintain **shared, versioned/pinned context doc sets** (standards, principles) at the org/department level, with drift and provenance surfaced to consuming projects. |

*(Retired: the TABP recruiter / hiring team persona is removed — tabp is retired; see the MAR-97 Reversal note in Out of scope.)*

### AI-native operating model (personas extension)

This subsection extends the persona table above with **how the personas above
operate the pipeline day to day** on an AI-native team: roles are framed as
**decision rights over the conformance chain**, not headcount or job titles
(see **C-19**). **AI triads (planner/executor/verifier) do the labor; humans
own the decisions and gates** — the pipeline's existing gate/review model
(Vision; Verifier-as-gate NFR) is the mechanism, the seats below are who holds
each decision right.

**Operating rule (governs all seats):** **work-in-progress (WIP) is capped by
human review bandwidth** — a team runs only as many parallel worktree
pipelines as its humans can actually review (PR review, design sign-off,
merge-pr judgment), never more just because the AI capacity exists. This is
the load-bearing constraint the five seats below orbit.

**Five seats**, instantiated per product team on the org structure (**G23**,
**G24**), plus one rotation hat:

| Seat | Owns (decision rights) | Operates (skills) |
|------|------------------------|--------------------|
| **Product Manager (PdM)** | PRD / roadmap / ticket requirements; clarification answers | `/acs:create-prd`, `/acs:create-ticket`, `/acs:metrics` |
| **Principal AI Platform** | Architecture sign-off; design sign-off; standards/principles; platform + org policy — at a **declared capacity split** (a per-team-declared attribute of this role, not a number this PRD fixes) | `/acs:create-architecture`, `/acs:create-standards`/`/acs:create-principles`, org-policy configuration |
| **AI Product Builder** ×N | Spec/code/PR/merge execution judgment within the gated pipeline; runs **parallel worktree pipelines**; subject to a **cross-review quota** (a per-team policy knob — see **C-3**; the normative rule is WIP capped by human review bandwidth, above) | `/acs:create-spec`, `/acs:code`, `/acs:create-pr`, `/acs:merge-pr`, `/acs:ship`, `/acs:handoff` |
| **AI Quality & Evals Engineer** *(renamed from "AI QA")* | The verification **system**: eval suites, e2e config, coverage policy, verifier efficacy, failure-mode dashboards | `/acs:create-quality`, `/acs:test`, eval-harness maintenance, `/acs:metrics`/failure-observability panels |
| **Ops/Release** *(a rotation hat, not a seat)* | Release cut; operations runbooks | `/acs:create-operations`, the release-cut capability (**G17**) |

Each seat maps to skills it operates and decisions it owns; no seat's decision
right duplicates another's. **Traces G33, G35** (below).

## Goals & success metrics

### acs feature — goals & success metrics

| Goal | Measurable success metric |
|------|---------------------------|
| G1 — Gated pipeline integrity | 0 instances of a skill running with an unmet predecessor (gate escapes); every blocked attempt produces an actionable message. First validated 2026-06-13 (acs v0.1.2, M2-0 spike): 0 gate escapes; gate advanced exactly one step at each of init → create-ticket → create-spec → code → create-pr. |
| G2 — Resumability | 100% of interrupted/handed-off tickets resumable from workspace state alone in a fresh session (no conversation history needed). First validated 2026-06-13 (acs v0.1.2, M2-0 spike): resumed from the code step in a fresh session using workspace state alone. |
| G3 — Quality via reflection | ≥ 90% of `/code` runs reach zero verifier findings within the 3-iteration cap; coverage target met or hard-failed (never silently waived) — the target may be a configurable policy (single repo-wide OR baseline-ratchet/per-path), still fail-closed, never silently waived (see **G27**). |
| G4 — Reviewable delivery | ≥ 80% of story/task PRs ≤ ~400 changed lines; every PR carries ticket trace, test plan, and findings. |
| G5 — Auditability | Every decision (clarification, assumption, finding, phase output) recoverable from the ticket partition; cost/tokens/time recorded per run, ticket, and repo. First measured 2026-06-13 (acs v0.1.2, M2-0 spike, 5 runs): ~$2.43 total, ~385k in / ~72k out tokens, ~1770 working-seconds, all recoverable from the partition. |
| G6 — Portability | Works on any git repo with `python3` + `gh`; zero pip installs; one `/acs:init` to onboard. First validated 2026-06-13 (acs v0.1.2, M2-0 spike): clean install + `/acs:init` in a throwaway repo, no Duplicate-hooks load failure. Each acs doc set (`prd`, `architecture`, `requirements`, `adr`, and future `standards`/`principles`/`quality`/`operations`) is independently relocatable to an external/absolute filesystem path via configuration; 100% of producer-skill runs preserve the per-backend reviewability + Git-audit guarantee (local/external-local = reviewable diff / repo PR; remote = backend-native review); 0 doc-set writes bypass the configured backend review path; measured per release. The acs pipeline is **runtime-portable**: the same gated pipeline (gating, TDD, coverage hard-fail, 12-dimension review, audit) runs on **≥ 2 supported runtimes** (Claude Code today + OpenAI Codex CLI). Gate-integrity strength is **runtime-dependent**: on Claude Code the pre-gate is non-bypassable (kernel `PreToolUse(Skill)` → exit 2); on Codex CLI — whose `PreToolUse` is documented as a guardrail rather than a complete enforcement boundary, which exposes **no skill-invocation matcher and no `SessionEnd` event**, and whose plugin hooks run only once user-trusted — gating is **best-effort by default**, with **non-bypassable enforcement available only via org-managed hooks** (`requirements.toml`). The second-runtime metric is **0 lost audit-trail artifacts** on a published end-to-end run, plus **0 gate escapes under managed-hook enforcement**, **validated within 1 release of the Codex CLI runtime capability shipping** (mirrors how G1/G2/G6 were first validated by the M2-0 spike). |
| G7 — Observability | Dashboard renders all 6 panels (throughput, pipeline funnel, cost/time per step, coverage vs target, review iterations, token burn by role) in ≤ 5 s for ≤ 50 tickets; reads only workspace artifacts; requires no network calls and no new config beyond `.acs/settings.json`. In-session status lines preserve 100% of Claude Code's default status-line fields and add acs state on top (zero default fields lost), render in < 100 ms per refresh, and never crash — any failure falls back to a valid line. *(Shipped — status-line refinement delivered in E3.4; verified live in-session.)* |
| G8 — Skill quality coverage | Structure, gating, and routing covered for 100% of the **16** skills (free, every PR; matches `s04_skill_triggers.py`'s 16-skill routing coverage); every critical-path skill has behavioral (artifact-level) eval coverage — including the dashboard skills `metrics`, `usage`, and `handoff`, which today have only trigger-level coverage (s04) and are the named gap this metric requires closing (see roadmap M3); no new skill ships without ≥ a trigger eval (CI guardrail); **0 orphaned agent files on disk — agent-file count == reachable-agent count** (currently 27 agent files vs 21 reachable; the 6 apply-work planner/verifier files are orphaned per MAR-62 and must be cleaned up or re-wired to close this metric). |
| G9 — Enforceable conventions | The configured branch/PR/commit formats are enforceable as a required merge gate on the consumer repo, blocking non-exempt violating PRs even when they bypassed `/acs:create-pr` (escape hatch: the `acs-exempt` label / release-branch allowlist). MAR-9 (PR #50, pending merge) completes the consumer side of that escape hatch: a legitimate non-ticket exempt PR lands via the sanctioned `/acs:merge-pr --pr` path (same readiness + branch/worktree cleanup as the ticket path, no ticket/partition/tracker/archive; it refuses and redirects ticket-backed PRs), and `/acs:init` Step 7e writes an idempotent `CLAUDE.md` acs-managed block that makes the pipeline the *default* for in-repo agent sessions (steering changes through `/acs:ship` rather than ad-hoc PRs). The gate itself is existence-proven by the live required-check ruleset on this repo's own `main` (ruleset 17602044, `active`; "Branch / PR / commit conventions" is a required status-check context). |
| G10 — Standards conformance & repo standardization | New design/code conforms to the principles + standards doc sets, verifier-checked: **100% of `/code` runs whose changeset touches a standards-governed area produce zero unwaived standards-conformance findings** (a violation is a blocking finding, never a silent pass), measured per release on the dogfood repo. Brownfield onboarding is additive and reviewable: **`/acs:standardize-project` lands its setup as exactly one reviewed PR that adds only docs/config/tooling and moves or renames zero existing source files** (0 source relocations; verified by the PR diff), with every target-layout structural gap emitted as a recommended follow-up ticket rather than an in-place move. |
| G11 — Tracker-first delivery / graceful degradation | A repo with **no PRD/architecture** delivers a remote-tracker-defined ticket end-to-end through the **same gates** (TDD, coverage hard-fail, 12-dimension review, audit, merge readiness) with **zero gate escapes** and **zero "missing PRD" hard-blocks** — the absent upstream artifact makes only its own trace step N/A, never blocking the run. Target: **100% of tracker-first runs (PRD absent) complete without a missing-upstream hard-block AND with 0 gate escapes**, validated on **≥ 1 real PRD-less repo within 1 release of the capability shipping**; tracker-issue acceptance criteria are carried into the spec for **100%** of such runs. |
| G12 — Org-level enforceable policy | An organization can define enforcement policy (required convention checks, security gates, standards/conventions floors) once and have it apply as a **non-overridable floor** across all its repos, with repos able to tighten but not loosen it, exemptions granted only at the org layer, and every effective rule traceable to the layer it came from. Floors compose down the org → department → project hierarchy (tighten-only; exemptions at the owning layer) — see C-6. **Measurable success metric:** on a pilot org of **≥ 3 repos**, **100% of those repos enforce the org-mandated convention/security checks as required status checks with 0 repo-level self-exemptions of a mandated rule**, and a deliberately non-conforming PR in any pilot repo is **blocked from merge** — first validated within **1 release** of the org-policy capability shipping (mirrors how G1/G9 are validated by an observed live gate, e.g. ruleset 17602044, prd.md). |
| G13 — Enforceable e2e integrity | When the optional e2e merge gate is enabled on a consumer repo, **0 PRs merge with a red e2e suite** (the required e2e status check is a fail-closed merge brake, symmetric to the G9 convention gate and the G3 coverage hard-fail), AND **100% of specs whose changeset touches a user-facing / cross-component surface declare e2e impact** (the spec's Test plan states e2e impact or an explicit "no e2e impact" reason — the code-verifier blocks any declared-impact spec lacking matching e2e test diffs; no zero-findings verdict without a green e2e run). The opt-in invariant holds: a repo with `settings.e2e` unset has no e2e suite and no e2e gate. Measured per release on the dogfood repo (gate-enabled repos). Traces the Tech-lead persona. |
| G14 — Complexity-adaptive delivery efficiency | A trivial, human-supervised ticket is delivered for substantially less wall-clock time and token/cost than the full pipeline. **Metric:** median wall-clock time AND median token/cost for a TRIVIAL-lane ticket are each reduced **≥ 60%** vs the same ticket run through the full plan-execute-verify ladder, measured on the dogfood repo within **1 release** of the capability shipping. |
| G15 — Fast-lane adoption | A meaningful share of tickets flow through the TRIVIAL/SMALL fast lanes (light verify) rather than the full ladder. **Metric:** **≥ 50%** of delivered tickets use the TRIVIAL or SMALL fast lane (vs the full STANDARD/COMPLEX ladder), measured per release on the dogfood repo once the lanes ship. |
| G16 — Rigor preserved where it matters (no regression) | Reducing process volume on simple work must not lower defect-catch. The verifier gates on every lane (autonomous-first); lighter lanes reduce only the verify-iteration ceiling, never whether the verifier or the TDD/coverage gate runs. **Metric:** **0 regression** in the code verifier's defect-catch rate — the TDD/coverage gate's hard-fail behavior is 100% in force on every lane, and full verify (the 12-dimension review) stays 100% on standard/complex lanes; measured by the existing eval harness (E1) showing no drop in verifier-caught findings per release vs the pre-feature baseline. |
| G17 — First-class release-version planning & one-command release cut | **100%** of roadmap versions carry an explicit version → milestone/epic mapping (every committed milestone resolves to exactly one release version, 0 orphan milestones), **AND** a release is cut in **1 command** producing an aggregated changelog/release notes from the merged tickets in that version, a version bump, a tag, and a GitHub release with **0 manual `release: cut vX.Y.Z` steps** — first validated by cutting **1** real acs release end-to-end within **1 release** of the capability shipping (mirrors how G1/G9/G11 are first validated by an observed live run). |
| G18 — Guided architecture selection (select-not-author) | For a repo with a PRD present, `/acs:create-architecture` presents a **pre-filtered/ranked shortlist across all FOUR catalog categories** (techstack, NFR templates, architecture patterns, design patterns) such that **≥ 80%** of finalized architecture selections are **chosen or refined from the offered shortlist rather than authored from scratch**, and the top-ranked shortlist is **non-empty for 100%** of the four categories on a PRD-present run — measured per release on the dogfood repo within **1 release** of the capability shipping. |
| G19 — Failure-mode / pipeline-health observability | A tech lead can see verifier cap-hits, gate-block counts, coverage hard-fail incidents, stale locks, abandoned/handed-off tickets, and out-of-band-merge / bypass-rate signals (see **G26**) over time — not just success/throughput. **Metric:** the cap-hit rate and gate-block count are visible for **100%** of tickets in the workspace, rendered in **≤ 5 s** for ≤ 50 tickets, read-only from existing workspace artifacts (no new config) — measured per release on the dogfood repo within **1 release** of the capability shipping. Extends G7's observability goal with failure-signal coverage. |
| G20 — Marketplace catalog growth & quality bar | The GMS Marketplace grows its plugin catalog through a documented, gated onboarding path while every catalog plugin meets a shared quality bar. **Metric:** a new plugin is added to the catalog through the documented path in **≤ 5 steps** (manifest entry, `marketplace.json` registration, namespace-isolation check, trigger-eval baseline, README), **AND 100%** of catalog plugins (currently 1: acs; tabp retired) pass the shared quality bar — a trigger eval baseline (mirrors G8's per-skill trigger-eval requirement) plus a verified namespace-isolation check (no cross-plugin prefix/token leakage, mirrors the tabp namespace rule, kept as a historical precedent) — measured per release. |
| G21 — Complete-configuration onboarding (init offers every user-configurable setting) | A fresh `/acs:init` actively offers every user-configurable acs setting — no user-settable capability is reachable only by hand-editing `.acs/settings.json` — and per-role model (at specific version), per-role reasoning effort, and e2e are each explicitly offered. **Measurable success metric:** on a fresh init, **100% of user-configurable `settings.schema.json` keys are reachable via the interactive `/acs:init` flow**, AND **per-role model (specific version, e.g. `claude-opus-4-8` / `claude-sonnet-5`), per-role reasoning effort, and e2e configuration are each explicitly offered** (not silently defaulted) — verified by a **fresh-init walkthrough on the dogfood repo within 1 release** of the capability shipping (mirrors how G1/G9/G11 are first validated by an observed live run). Extends **G7** (config-surface discoverability). Traces the **Solo-developer + Tech-lead personas**. |
| G22 — Complete tracker and PR metadata sync across the pipeline lifecycle | On a tracker-configured repo (provider `github`, a Project configured), **100%** of acs-opened PRs carry an assignee — **always the PR author (the authenticated `gh` user who runs the pipeline)**, so 0 PRs are ever left unassigned — plus the existing `Closes #<issue>` link, **AND 100%** of pipeline tickets show a GitHub Project **Status** matching their true pipeline stage across the full lifecycle (create → in-progress at create-ticket → **in-review at create-pr** → done at merge-pr), with **0 tickets left stale at "in-progress"** after their PR is open or after merge — first validated on **1** real end-to-end `/acs:ship` run within **1 release** of the capability shipping (mirrors how G1/G9/G11 are first validated by an observed live run). A field with no resolvable value is skipped as expected data, never a hard block (mirrors the create-ticket null-assignee rule). |
| G23 — Team-shared delivery state (no cross-engineer collisions) | Multiple engineers delivering on one repo share ticket/id/lock/metrics state so there are **0 duplicate ticket-id allocations across engineers** and **100% of active tickets are visible (with their lock holder) to every teammate** from shared state. **Metric (measurable at plan time):** on a **≥ 2-engineer, 1-repo pilot**, **0 id collisions** across **≥ 20 concurrently-allocated tickets AND** every in-progress ticket's lock holder is resolvable by a second engineer — first validated on **1 real 2-engineer concurrent run within 1 release** of the capability shipping (mirrors how G1/G9/G11 are first validated by an observed live run). Traces the **Team-on-a-shared-repo persona**. Reconciles with (does not duplicate) **G12**: G12 governs *policy floors* (what rules apply); G23 governs *shared delivery state* (tickets/ids/locks/metrics) — a distinct, narrower gap G12 does not cover. MECHANISM (shared vs synced workspace, tracker-as-id-authority vs a shared counter service, how locks federate) is deferred to the implementing epic's design phase. |
| G24 — Org-scale settings & workspace distribution (org → department → project cascade, additive, non-breaking) | An org distributes **shared non-enforcement defaults** (models, tracker, doc paths, formats) and a **shared/central workspace convention** to all its repos through a full **org → department → project** cascade above today's user → project → local chain — defaults resolve **most-specific-wins down the cascade** (org, then department, then project), so a repo can still override a *default* (distinct from a G12 *mandate* it cannot loosen). **Metric:** on a **pilot org with ≥ 2 departments and ≥ 3 projects**, **100%** of projects resolve org- and department-distributed defaults with **0 per-repo duplication**, and with **no org/dept source configured, resolution is byte-identical to today** (additive/non-breaking, mirrors C-6) — first validated within **1 release** of the capability shipping. **Extends G12** (the org/department layer) and the settings cascade — G12 stays the *mandate/floor* half (non-overridable), G24 is the *defaults/distribution* half (overridable); this amendment does not restate G12's enforcement floor. Traces the **Org/Platform-admin + Team-on-a-shared-repo personas**. MECHANISM (org/department source format, distribution transport) is deferred to the implementing epic's design phase. |
| G25 — Dynamic (mid-flight) lane correctness | A ticket whose real implementation turns out to touch a higher-stakes / larger surface than its create-time lane assumed is **automatically escalated to the correct lane before the verify gate runs**, so the change is verified at the rigor its actual content demands — not the rigor guessed at create-ticket. **Measurable success metric:** on the dogfood repo, within **1 release** of the capability shipping, **100% of tickets that touch a high-stakes surface after starting in a TRIVIAL/SMALL lane are escalated to ≥ STANDARD (full verify) before results are presented** (0 fast-lane merges of a change that touched a high-stakes surface), **AND 0 lane escalations are silently reversed** (escalation is upward-only and sticky — automatic; a **user-confirmed** mid-flight de-escalation is supported but is never a silent reversal, since it requires explicit user confirmation) — first validated by **≥ 1 real escalation event** observed on the dogfood repo (mirrors how G1/G9/G11 are first validated by an observed live run). **Extends G16** (rigor preserved / no regression) with the *dynamic* dimension — G16 keeps the static per-lane gate invariant; G25 adds that the lane itself self-corrects in flight. Traces the **Solo-developer + Tech-lead personas**. First validated 2026-07-06 (MAR-109/MAR-110): a real trigger-(b) escalation fired on fixture ticket MAR-110 (`direction: "up"`, `trigger: "b"`, TRIVIAL→STANDARD, `confirmation_ref: null`), recorded at `/Users/ngdduc92/acs-workspace/globalmindsolution-gms-marketplace/MAR-110/code-state.json` `runs[-1].escalations[0]`; the ticket completed a verifier pass at the escalated STANDARD depth before results were presented; `/acs:metrics` `delivery_summary.escalations` read `events: 1, fast_lane_escalated: 1, silent_reversals: 0` on this repo. |
| G26 — Invoker-scoped merge governance + out-of-band reconciliation | On a solo-author repo whose branch protection requires 0 reviews, **100% of human-invoked `/acs:merge-pr` runs complete without a phantom self-approval block** (the approved-review mandate applies to agent-invoked merges only; human-invoked merges defer to the repo's own branch protection), AND **100% of out-of-band-merged PRs whose ticket is still `in_review` are reconciled** (ticket→done, partition archived, metrics updated) rather than stranded — **0 stranded tickets** after an out-of-band merge — first validated on **1 real solo-author end-to-end run within 1 release** of the capability shipping (mirrors how G1/G9/G11 are first validated by an observed live run). Traces the **Solo-developer + Tech-lead personas**. Reconciles with (does not duplicate) ADR-0028: G26 is the product requirement that authorizes ADR-0028's line-47 narrowing ("m6 can be narrowed to agent invocations only") once a reliable invocation-source signal exists — the readiness gate + branch protection remain the two independent brakes unchanged; this only narrows the require-APPROVED-for-ALL fallback to require-APPROVED-for-AGENT, never removing the approved-review safety guarantee. The bypass-rate visibility sub-requirement is folded into **G19 by extension** (see above), not a separate metric. MECHANISM (how the coordinator learns the invoker, how out-of-band merges are detected) is deferred to the implementing epic. |
| G27 — Brownfield-adaptive coverage policy | A repo can configure coverage as a **baseline ratchet** (no coverage regression vs the recorded baseline + a configurable new-code coverage target) OR **per-path targets**, instead of only a single repo-wide `test_coverage_percent` hard-fail. **Metric:** on a legacy repo below the global target, **100% of `/code` runs hard-fail on a coverage REGRESSION or an unmet NEW-CODE target while never hard-failing solely because the pre-existing repo-wide percentage is below the global default** — measured per release; with **no coverage-policy config set, behavior is byte-identical to today's single repo-wide hard-fail** (additive/non-breaking, mirrors C-6). Extends **G3** (coverage hard-fail, never silently waived — the ratchet still fails closed) and the **G6** onboarding/portability story. First validated on 1 real legacy-repo run within 1 release of the capability shipping. Traces the Tech-lead + brownfield-onboarding story. MECHANISM (ratchet vs per-path, config key shape, baseline storage) is deferred to the implementing epic. |
| G28 — Org/department-shared context lifecycle | Orgs/departments keep **shared, versioned/pinned context doc sets**; projects consume a pinned version; verifiers surface **drift + provenance** (feature + M3 epic). **Metric:** on a pilot org, **100%** of projects resolve pinned context with provenance and drift within **1 verifier run**, validated within **1 release**. MECHANISM deferred. |
| G29 — Human-readable doc management (first-class) | Every acs producer skill keeps docs human-friendly; each verifier gates readability as blocking findings, mirroring G10 (detail in the feature + C-15). **Metric (new/amended content only; backlog phased via C-15):** **0** unwaived readability findings/release; **0** new lines > 500 chars; new cells ≤ ~50 words. |
| G30 — External-consumer delivery readiness | acs delivers an **external commercial consumer product's** codebase (an agentic hiring SaaS, GMS-internal today with future external sale) end-to-end through the **same gated pipeline** used for this repo's dogfooding — **0 gate escapes** and **100%** of that product's delivery tickets carry the full audit trail (ticket → spec → code → PR → merge) — first validated on **1 real delivery run on that repo within 1 release** of its onboarding kickoff (mirrors how G1/G9/G11 are first validated by an observed live run). Traces the external-consumer-product context in Vision; see **C-16**. |
| G31 — Full behavioral eval coverage for every active plugin (per-skill coverage ratio) | **100% of each active catalog plugin's user-facing skills have a runnable behavioral (artifact-level) eval** — today acs (19 skills), the sole active plugin — measured as `skills-with-a-runnable-behavioral-scenario / total-skills` per plugin, reported per release; the ratio is **monotonically non-decreasing release over release** and reaches **100% within 2 releases** of the delivering capability shipping (N=2). Behavioral = asserts on produced artifacts, never prose (mirrors the harness discipline, `evals/README.md`). **Extends G8** (which names only the three dashboards as the behavioral gap); G31 generalizes the behavioral-coverage obligation to *all* skills of every active plugin and makes the per-plugin ratio the tracked progress number — it does not restate G8's dashboard clause. Traces the **Tech-lead persona**. |
| G32 — Marketplace-wide eval baseline enforced per plugin (trigger + namespace + release-gate obligation) | **100% of catalog plugins (today 1: acs) satisfy the eval baseline every release**, and the obligation applies to every future catalog plugin on onboarding = (i) a **trigger/routing eval** covering 100% of the plugin's skills, (ii) a **namespace-isolation eval** for any non-acs plugin proving no cross-plugin `.acs/`/`acs:` prefix or token leakage, and (iii) the plugin's **paid eval tier passes as a pre-release gate**, with **0 released versions cut on a failing eval suite** — measured per release. **Extends G20** (which states the baseline as a one-time onboarding checklist) by making it a **recurring per-release obligation** with a measurable pass/fail; cross-references G8/G20 without restating them. Traces the **Tech-lead + Org/Platform-admin personas**. |
| G33 — Full-SDLC phase coverage (every phase has an operating skill + a named accountable role) | **100% of the defined SDLC phases** (define → design → spec → code → PR → merge → release → quality → operate → standards/principles) **have both (a) an operating acs skill and (b) a named accountable role** from the AI-native operating model, with **0 phases reachable only by ad-hoc work** — first validated by an operating-model coverage walkthrough on the dogfood repo within **1 release** of the last committed tail skill (`/acs:create-quality`, `/acs:create-operations`, `/acs:test`, the release-cut capability) shipping. **Deploy is a deliberate exception, recorded as an explicit position:** there is **no deploy skill** — `/acs:create-project` scaffolds CI/CD, `/acs:create-operations` documents runbooks, and the release tag triggers the consumer repo's own CD. Extends the coverage story of **G8** (skill-quality coverage) without restating it. Traces the AI-native operating model + the full-SDLC coverage feature. |
| G34 — Headless unattended runner (canonical unattended execution mode) | **100% of runner-triggered (unattended) executions run the COMPLEX/UNATTENDED lane (full verify) and stop before `/merge-pr`; 0 unattended runs execute a fast lane and 0 unattended runs auto-merge** — first validated by **≥ 1 real runner-triggered `/acs:ship` run** (triggered from a tracker label / chat / CLI) on the dogfood repo within **1 release** of the runner capability shipping (mirrors how G1/G9/G11 are first validated by an observed live run). Extends **G6** (runtime portability) and **G30** (external-consumer delivery readiness). The **normative safety invariant** is stated as **C-18**. MECHANISM (SDK vs CI-runner host, trigger transport, auth) is **deferred to the implementing epic's design phase**. Traces the headless-runner feature + the Codex-rescope note (Features, Out of scope). |
| G35 — Operating-model role accountability (named owner per skill) | **100% of acs operating skills map to exactly one accountable role** in the AI-native operating model (0 orphan skills, 0 skills with no named owner), and the **WIP-cap = human-review-bandwidth rule** is recorded as the governing operating constraint — verified by the operating-model table on the dogfood repo at this amendment's landing release, re-checked each release the skill set changes. Traces the AI-native operating model (personas). |

### tabp feature — success metrics *(RETIRED — tabp superseded by an external consumer product; see the MAR-97 Reversal note in Out of scope)*

Historical record only — T1-T7 are frozen (not renumbered, not deleted) and no
longer tracked as live metrics; tabp is retired.

| Metric | Measurable success metric *(historical)* |
|--------|---------------------------|
| T1 — Speed *(retired)* | Screen a 20-CV batch ≥ 70% faster than manual screening, measured within 1 month of the feature's first use. |
| T2 — Reproducibility *(retired)* | ≥ 95% reproducible band/recommendation on a fixed 10-CV regression set, per release. |
| T3 — Evidence & auditability *(retired)* | 100% of judgments cite evidence and produce a scorecard, every run — no recommendation without a traceable rationale. |
| T4 — Fairness *(retired)* | 0 protected/proxy criteria used AND 100% of bias-relevant JD requirements flagged, measured on a ≥ 15-pair test set, per release. |
| T5 — Adoption *(retired)* | ≥ 80% of new TABP role openings use screen-cvs within 3 months of the feature's first use. |
| T6 — Verifier-as-gate *(retired)* | 100% of screen-cvs runs present results only after a clean verifier `pass` verdict from `screen-verifier-subagent.md` (0 results shown on cap-hit at N=3 unresolved-finding remediation attempts), measured per release on the run history in `.tabp/history.json`. |
| T7 — Resumability *(retired)* | 100% of interrupted screen-cvs runs resumable from `.tabp/` persisted state alone (run.json, evidence-*.json, decision.json, history.json), verified by 1 real interrupted-and-resumed run per release. |

## Features (MoSCoW)

The GMS Marketplace currently delivers **one active plugin feature — acs** —
prioritized internally via MoSCoW (tabp is retired; see the stub below). Future
plugins will be added as additional feature sections here, through the **G20**
growth path.

### Feature: acs (Autonomous Coding Skills)

**Must have** *(shipped in v0.1)*
- Claude Code plugin marketplace (this repo) with the `acs` plugin.
- 16 skills: `/init`, `/ship`, `/handoff`, `/update`, `/install-hooks`, 4
  product-level (`create-prd`, `create-architecture`, `create-project`, `metrics`),
  1 usage dashboard (`usage`), 6 workflow (`create-design`, `create-spec`,
  `create-ticket`, `code`, `create-pr`, `merge-pr`). Verified on disk: `ls
  plugins/acs/skills` = 16. **Historical v0.1 snapshot** — later releases grew
  the skill count past this figure (`/create-quality`, `/create-operations`,
  `/acs:test`; 19 skills as of MAR-114); this bullet records the v0.1
  shipped scope and is intentionally left as-is.
- Hook-enforced step gating (PreToolUse dispatch, exit-2 blocks, SessionEnd safety net).
- Workspace partitioned by repo/ticket, outside the consumer repo; locks, worktree parallelism.
- Reflection cycle (planner/executor/verifier) with XML messaging (XSD) and phase artifacts. The six triad-keeping skills (create-prd, create-architecture, create-project, create-design, create-spec, code) each spawn the full planner/executor/verifier triad; the three apply-work skills (create-ticket, create-pr, merge-pr) run **inline** (coordinator + at most one executor, no planner/verifier) since MAR-60. 27 agent files exist on disk (9 skills × 3 roles) but only 21 are reachable — 18 active triad agents + 3 apply-work executors; the 6 apply-work planner/verifier files are orphaned (MAR-62 tracks cleanup).
- TDD `/code` with coverage hard-fail and the 12-dimension changeset review loop (≤ 3 iterations).
- Local-first tickets: epics with child fan-out, per-repo id sequence, archive lifecycle.
- Resume at three levels (gates, `/ship` ledger, mid-skill reconcile) + deliberate handoff.
- Requirement clarification ledger; grounding rules; standard completion reports.
- `acs:metrics` dashboard skill — reads workspace artifacts (`metrics.json`, `tickets-index.json`, per-ticket `pipeline-state.json`, `code-state.json`, `create-pr-state.json`) and renders an interactive HTML dashboard inline in the Claude Code session (`show_widget`) covering: ticket throughput by status/type, pipeline funnel, cost and time per ticket broken down by pipeline step, test coverage achieved vs target, review iterations before verifier passed, and token burn by role (planner/executor/verifier). Read-only; no new file writes; no new config; single-repo scope. Traces G5, G7. *(Must have for M2 exit)*
- `acs:usage` dashboard skill — a separate, shipped delivery-metrics/AI-spend
  split from `acs:metrics`: reads workspace artifacts and renders cost, token,
  and time usage (AI spend) per ticket/run/role, distinct from `acs:metrics`'s
  delivery-KPI focus (throughput, funnel, coverage, review iterations). The two
  dashboards partition **delivery KPIs** (`acs:metrics`) from **AI-spend
  tracking** (`acs:usage`). Read-only; no new file writes; no new config;
  single-repo scope. Verified on disk: `plugins/acs/skills/usage/SKILL.md`.
  Traces G5, G7.
- Convention enforcement as a required merge gate — `/acs:init` Step 7c scaffolds a repo-side CI check (`.github/workflows/acs-conventions.yml`) backed by a stdlib-only `.acs/ci/check-conventions.py` (fail-closed; modes `pr` / `pre-push` / `commit-msg`) compiled from the configured `formats.*`, plus an `enforcement` settings block (`checks.{branch_name,pr_title,pr_description,acs_label,commit_message}`, `require_label`, `exempt_label` default `acs-exempt`, `exempt_branches`, `pr_description_sections`). Wired as a required status check on the consumer repo, it blocks non-exempt branch/title/description/label/commit-message violations even on PRs that bypassed `/acs:create-pr`; the `acs-exempt` label and a release-branch allowlist are the escape hatch. Observed live on this repo (ruleset 17602044, `active` on `main`; "Branch / PR / commit conventions" is a required context). Traces G9 (+ the Tech-lead persona). **MAR-9 (PR #50, pending merge)** extends this: the exempt PRs the gate lets through then land via a sanctioned merge path — `/acs:merge-pr --pr <n>` (also `#n` / a PR URL) runs the same four readiness dimensions and branch/worktree cleanup as the ticket path but resolves no ticket, writes no partition/state, and skips tracker sync and archiving (bumping only the repo `pr_merged` metric), refusing and redirecting when the PR is actually ticket-backed; and `/acs:init` Step 7e (opt-in, default-on) writes an idempotent, marker-delimited `CLAUDE.md` acs-managed block (rendered from `templates/CLAUDE.acs.md`) that steers in-repo Claude sessions to ship via `/acs:ship` instead of a raw `gh pr create`, making the pipeline the default rather than only the gate. **Maturing:** in addition to today's `--label ACS`, conditional `--milestone`, and `Closes #` body line, `/acs:create-pr` also sets the PR **assignee** (plus reviewers/labels beyond `ACS`/Project membership per the Two-way tracker sync feature's Group A) — see the Two-way tracker sync Should-have above and **G22**.
- `/acs:install-hooks` skill — the `pre-commit install` equivalent for acs (per-clone, user-invoked): installs the config-driven local git hooks (`commit-msg` + `pre-push`) that run the same `check-conventions.py` before a commit or push leaves the machine. A committed `.acs/ci/install-hooks.sh` lets teammates run it without the plugin. Traces G9 (+ the Tech-lead persona).
- **Tracker-first delivery (PRD-optional mode)** — a **configurable governance mode**
  so a team with no PRD/roadmap/architecture can deliver requirements that live only
  in a remote tracker (GitHub Projects / Jira) through the **same gated pipeline**.
  When upstream product docs are **absent**, the imported tracker issue (description +
  acceptance criteria) is the **requirement source of truth**; the conformance chain
  **degrades gracefully** — a missing upstream artifact makes only its own trace step
  **N/A**, never a hard block — while TDD, coverage hard-fail, the 12-dimension review,
  audit trail, and merge readiness are **unchanged**. Builds on the existing
  `/acs:create-ticket <remote-key>` import + two-way tracker sync (Should-have, above;
  `gh`/`acli`). **Divergence (C-3):** with **no PRD present**, tracing is N/A and the
  tracker ticket governs (nothing to flag); with a **PRD present**, today's behavior
  is kept — trace, flag divergence, user decides. This is **graceful degradation of
  the existing pipeline, not a parallel workflow**, and acs **never auto-authors a PRD
  without opt-in** (see Constraints). Traces **G11** (+ the Team-with-a-tracker-only-PO
  persona). *(Must have — urgent; see roadmap E6.)* The mechanism (config key name,
  explicit opt-in vs auto-detect, design-step optionality) is **deferred to the
  tracker-first epic's design phase** — this PRD states the requirement (what).
- **Complexity-adaptive delivery** *(shipped — MAR-55 epic: MAR-56/57/58/59/60/61 merged to main)* — acs scales the amount of process/structure it
  applies to a ticket based on the ticket's **complexity** AND the level of **human
  supervision**, instead of running the full plan-execute-verify ladder on every
  ticket. **Framing principle (autonomous-first):** acs is autonomous-first — the
  in-loop quality gate on every lane is the **verifier subagent**, and the
  human-in-the-loop checkpoint is the **PR review** before merge, not an inline
  human-approval gate. What scales with complexity is the *amount of process*
  (decomposition stages and verify iteration depth), **not whether the verifier
  runs**: the verifier always runs, and the TDD/coverage gate always runs, in
  every lane. (This generalizes Claude Code's own adaptivity — Plan mode for
  complex, skipped for simple — but keeps an automated in-loop gate because acs
  must stay correct on unattended `/acs:ship` runs where no human is watching.)
  Routing is **two axes — size × stakes** — assembled into four lanes; lighter
  lanes reduce process volume but never drop a gate. Four delivery lanes:
  1. **TRIVIAL** (trivial size, not high stakes) — no standalone create-spec and
     no separate planner subagent (spec authoring is folded into `/code`'s plan
     phase); **light verify**: a single verifier pass that may iterate at most
     **once** on blocking findings (`VERIFY_ITERATION_CAP["light"] = 1`). The
     verifier still gates; there is no human-approval gate.
  2. **SMALL** (small size, not high stakes) — same fast-lane fold and **light
     verify** (1-iteration cap) as TRIVIAL.
  3. **STANDARD** (standard size, or any ticket with `needs_design`) — full
     create-spec path; **full verify** (the existing up-to-3-iteration
     plan→execute→verify loop + 12-dimension review + e2e when configured).
     Apply-work skills (create-pr, merge-pr, create-ticket) run **inline**
     (coordinator + at most one executor), never a full triad, in every lane.
  4. **COMPLEX / UNATTENDED** (large size, epic, or `/acs:ship` autonomous run) —
     **full verify** exactly as today; the persisted artifacts are the audit
     trail; preserves the rigor that is the product.

  **High-stakes floor:** `stakes = high` resolves to at least STANDARD (full
  verify) regardless of size — a defense-in-depth floor a small lane value can
  never bypass. **Mid-flight escalation** raises a ticket to a higher lane (and
  re-introduces any skipped stage) on the first higher-stakes signal, upward-only
  and automatic; de-escalation is never automatic. The escalation trigger is a
  **defined in-flight higher-stakes / larger-scope signal observed during
  implementation** — escalation MUST be driven by an observable in-flight signal,
  not left to model goodwill — with the exact signal set and detection point
  **deferred to the implementing epic's design phase**. A **user-confirmed**
  mid-flight de-escalation is also supported — the lane can be lowered only with
  explicit user confirmation, never automatically. The lane is set once,
  user-confirmed, at create-ticket alongside `needs_design`; default is
  full/standard rigor; lighter lanes are opt-in and rigor is never silently
  dropped. Traces **G14, G15, G16, G25**.
- **Full-SDLC coverage (framing note, not a new skill)** — every SDLC phase
  has both an operating acs skill and a named accountable role (see the
  AI-native operating model, above Goals): release (**G17**, roadmap Wave 3),
  create-quality + `/acs:test` (**G8**, roadmap Wave 1 LEAD), create-operations
  (**G19**, roadmap Wave 1/4), standards/principles (**G10**, roadmap Wave 2).
  Records the deliberate **no-deploy-skill position**: `/acs:create-project`
  scaffolds CI/CD, `/acs:create-operations` documents runbooks, and the
  release tag triggers the consumer repo's own CD — acs never ships a deploy
  skill. The existing **`/acs:help`** discoverability feature (Could-have,
  below) gains importance for the operating model's non-builder roles (PdM,
  Principal, Quality) as an existing feature, cross-referenced here, not
  re-scoped. Traces **G33**.

**Should have** *(shipped in v0.1, maturing)*
- Two-way tracker sync (GitHub Projects / Jira via `gh` / `acli`), remote import.
  **Maturing (complete, lifecycle-accurate field coverage):** extends today's sync —
  create-ticket already fills Type/Status(in-progress)/Labels/Assignee/Milestone and
  merge-pr already sets Status→Done — with two grouped field sets. **Group A — PR
  metadata acs sets on create/update:** assignee (always the PR author — the
  authenticated `gh` user running the pipeline), reviewers, labels beyond `ACS` (e.g.
  the type label, mirroring the issue), and Project membership + field values for the
  PR itself, in addition to the existing `Closes #<issue>` link and milestone. **Group
  B — ticket fields acs keeps in sync with the tracker across the pipeline lifecycle:**
  Status at every stage (including the new **in-review** transition when
  `/acs:create-pr` opens the PR, alongside the existing in-progress-at-create and
  done-at-merge transitions), assignee, priority, story points, parent/epic link (as an
  explicit named Project field), and Project field values. MECHANISM (reviewer source,
  which Project Status option maps to each stage, the priority/story-points/parent
  field-to-column mapping) is deferred to the implementing epic's design/spec phase,
  matching every other deferral in this PRD. Traces **G22**.
- **Configured e2e test layer with an optional enforceable merge gate** — the opt-in `settings.e2e` layer ships today (`command` + optional `setup`/`teardown`, `per_iteration`; unset = no e2e suite): `/acs:create-spec` test plans declare e2e impact, `/acs:code` authors/runs affected e2e tests in the same changeset, and the code-verifier runs the FULL suite (no green run, no zero-findings verdict). **New:** `/acs:init` can scaffold a repo-side e2e CI workflow + runner and wire it as a REQUIRED status check on the consumer repo (opt-in, fail-closed), so a red e2e blocks PR merge — symmetric to the G9 convention gate and the G3 coverage hard-fail, and making the today-report-only `/acs:merge-pr` CI read ENFORCEABLE via branch protection. A fresh `/acs:init` **explicitly offers** e2e configuration (candidate-detected), rather than leaving it in the silently-defaultable optional batch — the exact prompt mechanism is deferred to the implementing ticket's design/spec phase. Traces G13, G9, **G21**. *(The opt-in invariant is preserved: no `settings.e2e`, no e2e suite and no gate.)*
- `docs_only` fast-path; PR-size control with ticket splitting.
- Per-role model + effort configuration *(shipped in v0.1, maturing)* — users can pin a specific model version (e.g. `claude-sonnet-5` / `claude-opus-4-8`) and set a reasoning effort per role in `.acs/settings.json` for all FOUR roles — `planner`, `executor`, `verifier`, `coordinator` — plus per-skill overrides (`models.overrides.<skill>.<role>`); a role value is a bare model string or a `{model, effort}` object, resolved override → role → inherit. A fresh `/acs:init` actively offers every user-configurable acs setting, so no user-settable capability is reachable only by hand-editing `.acs/settings.json`; the three under-offered surfaces today are per-role model at specific-version granularity, per-role effort, and e2e (traces **G21**). **Maturing enhancements (committed):** (1) init discoverability — a fresh `/acs:init` actively PROMPTS for per-role model at SPECIFIC-VERSION granularity (offering version-pinned choices, e.g. `claude-opus-4-8` / `claude-sonnet-5`, not only coarse tiers) AND for per-role reasoning EFFORT as a first-class choice (not only a documented example), including the coordinator-scope caveat, so the choice is fully discoverable — the exact init UX is mechanism, deferred to the implementing ticket's design/spec phase; (2) up-front value validation — validate supported effort values and model ids fail-closed at config time with a helpful error, instead of failing late at subagent-spawn time (the supported-effort enum exists today only in the advisory `settings.schema.json`, not enforced by the runtime gate, and there is no model-id validation) — the supported-model-id/effort source-of-truth is mechanism, deferred to the implementing ticket's design/spec phase. Traces G7 (observability/config surface — see the "convenience config (…models…)" framing below), **G21**. See roadmap **v0.3.4** (init prompt) and M3 Wave 4/v0.4.2+ (up-front validation + docs) for the committed delivery items.
- Status lines layer acs state onto Claude Code's defaults, never replacing them — both the prompt line and the reflection agent-panel compose with Claude Code's default rendering and add acs context on top: the **prompt** line surfaces the default's standard context (model, cwd, git branch, context-left, output style) **plus** acs pipeline state (active ticket, step glyphs, cost, lock); the **agent panel** keeps every non-acs row at its Claude Code default and enriches the recognized reflection-subagent rows with acs state (phase, role, ticket, tokens, elapsed), with room to surface more acs-relevant fields. *(Traces G7.)*
- Behavioral eval harness for skills: free contract/gate smoke (pre-commit + CI) + paid agentic evals as a pre-release gate. *(Delivered in M2, Epic E1. Traces G8.)*
- **Full behavioral eval coverage + per-release eval baseline** — extends the shipped eval harness (E1) with behavioral (artifact-level) scenarios for the currently-uncovered acs skills (the product-producer skills `create-prd`, `create-architecture`, `create-project`, `create-design`, plus `create-pr`, `merge-pr`, `ship`, `handoff`, and the dashboards `metrics`/`usage`) and a per-plugin coverage-ratio report, and wires the trigger + namespace-isolation baseline as a recurring per-release gate (not only a one-time onboarding check). Eval coverage is **additive over the shipped harness** — behavioral/LLM evals stay local-only, never in CI (C-17); the paid tier remains the manual pre-release gate. MECHANISM (which scenarios, scripted vs documented baseline check, where the coverage ratio is reported) is **deferred to the implementing epic's design/spec phase**, mirroring every other deferral in this PRD. Traces **G31, G32** (extends G8/G20).
- **First-class release versions + one-command release cut** — acs's release process gains two related capabilities: (a) a **cut-release capability** that aggregates the merged tickets belonging to a version into changelog/release notes, bumps the version, tags the commit, and creates the GitHub release — filling today's manual "release: cut vX.Y.Z" gap (see README "Releasing & updating"); and (b) the create-prd **roadmap models release versions as first-class planning units** distinct from milestones, with an explicit version → milestones/epics mapping (today the roadmap only *labels* milestones with versions, e.g. "M3 — v0.4.0"). This likely warrants a new producer/apply-work skill (e.g. `/acs:release` or `/acs:create-release`), but the exact **skill name/shape, the version-object schema, and the release-cut implementation are MECHANISM — deferred to the implementing epic's design phase** (mirrors the Notion/multi-runtime/org-policy deferrals above). Traces **G17**. See roadmap M3 Wave 3 (v0.4.1) for the committed delivery item.
- **Guided architecture selection — curated catalog, select-not-author** — `/acs:create-architecture` gains a **curated acs-shipped catalog** of common tech stacks, NFR templates, and architecture/design patterns, **pre-filtered/ranked** by what the PRD + codebase imply, so the user **selects/refines** from the most relevant options across all FOUR categories (techstack, NFRs, architecture patterns, design patterns) instead of inputting from scratch. This **enhances the existing `/acs:create-architecture` skill and adds no new doc set**. The **catalog source-of-truth and the exact selection UX are MECHANISM — deferred to the implementing epic's design phase.** Traces **G18** (+ the Tech-lead persona). See roadmap M3 Wave 4 (v0.4.2+) for the committed delivery item.
- **Failure-mode / pipeline-health observability** — extends the existing dashboard
  surfaces (`acs:metrics`, `acs:usage`), which today are strictly success/throughput
  oriented, with a failure-signal view: verifier cap-hits, gate-block counts,
  coverage hard-fail incidents, stale locks, and abandoned/handed-off tickets — read
  from existing workspace artifacts (same read-only, no-new-config discipline as
  G7). Mechanism (standalone panel vs a new `acs:metrics` section) is deferred to
  the implementing ticket's design/spec phase. Traces **G19** (extends G7). See
  roadmap M3 Wave 4 (v0.4.2+) for the committed delivery item.
- **Workflow-gap promotions (four items, AI-native operating model follow-through)**:
  1. **Team-shared delivery state (G23/G24) promoted to a P0 prerequisite for
     multi-person teams**, with **tracker-first (G11) recorded as the
     sanctioned INTERIM team protocol** until G23/G24 ship (residual risks:
     cross-machine id collisions in branch names; lock visibility gaps across
     engineers). Extends the existing G23/G24 features (above) without
     restating them. Traces **G23, G24, G11**.
  2. **Team-mode init option** — an `/acs:init` option that scaffolds
     **CODEOWNERS** mirroring `high_stakes_paths` plus docs-path ownership.
     **Role gates live at the forge, not in acs** (the **C-19** discipline) —
     acs scaffolds the CODEOWNERS file; GitHub enforces it. **MECHANISM**
     (exact CODEOWNERS template, path-to-owner mapping) is **deferred to the
     implementing epic's design phase**. Traces **G12, G24** + the AI-native
     operating model.
  3. **Design sign-off surface** — for `needs_design` tickets, publish the
     approved `design.md` to a **shared reviewable surface** (a tracker issue
     or a docs PR) for **Principal AI Platform sign-off** — today `design.md`
     is machine-local, the one real role-separation break in the pipeline.
     **MECHANISM** (which surface, transport) is **deferred to the
     implementing epic's design phase**. Traces the AI-native operating model
     + **G10**.
  4. **create-spec planner user-confirmed stakes-bump** — on discovering a
     high-stakes surface during spec authoring, the `/acs:create-spec` planner
     **may propose a user-confirmed ticket stakes bump** (a metadata-accuracy
     correction; verify depth is unaffected by this proposal alone — composes
     with **C-7**/**C-12** and does not alter **G25**'s in-flight escalation
     mechanism). **MECHANISM** deferred to the implementing epic's design
     phase. Traces **G25, C-12** (metadata-accuracy dimension).
- **Headless unattended runner** — a canonical **unattended execution mode**,
  mechanically an **autonomous `/acs:ship`** (Agent SDK / CI runner),
  triggerable from a **tracker label / chat / CLI**. Governed by the **C-18
  safety invariant**: unattended execution **always** runs the
  **COMPLEX/UNATTENDED lane (full verify)** — no configuration can assign a
  fast lane to an unattended run — and **always stops before `/merge-pr`**.
  Traces **G34** (extends G6, G30). **MECHANISM** (trigger wiring, Agent-SDK
  vs CI-runner host, auth) is **deferred to the implementing epic's design
  phase**. *Consequence:* the v0.5.0 multi-runtime (Codex) epic (roadmap M4)
  **re-scopes in intent** from a full-pipeline port to **triggering the runner
  + light authoring skills**, consistent with the already-documented Codex
  constraints (no skill-invocation hook matcher, no `SessionEnd` event,
  `PreToolUse` a guardrail rather than a complete enforcement boundary — see
  the Multi-runtime Could-have below and Reversal note MAR-2).

**Could have**
- Scheduled background tracker sync; cross-machine handoff (shared workspace) — both sequenced into v0.7.0 (see roadmap M6); additional description templates.
- **Team-shared delivery state (shared/central workspace + collision-free ids)** — a
  configurable **shared workspace** (or a shared allocation authority / tracker-issued
  identity) so a team on one repo shares tickets/ids/locks/index/metrics with **0
  cross-engineer id collisions** and cross-engineer lock visibility. **Builds on** the
  "cross-machine handoff (shared workspace)" Could-have above (roadmap M6) — this
  generalizes it from *handoff* (one engineer, different machines) to *concurrent team
  delivery* (multiple engineers, same repo, at once). Traces **G23** + the
  Team-on-a-shared-repo persona. **MECHANISM** (shared-mount vs synced workspace vs
  tracker-as-id-authority vs a shared counter service; how locks federate) is **deferred
  to the implementing epic's design phase.**
- **Department metrics rollups** — project → department → org rollups of delivery
  throughput / cost metrics, extending the `acs:metrics` / `acs:usage` dashboard surface
  (read-only, same no-new-config discipline as G7). Traces the **Org/Platform-admin
  persona** and the hierarchy goals (**G24**; relates to **G19** observability).
  MECHANISM (rollup source, org/dept grouping key) deferred to the implementing
  ticket's design/spec phase.
- **Discoverability — skill index / next-step advisor** — with 16 acs skills
  (2 tabp skills retired) there is no in-plugin "what can I do / where am I in
  the pipeline / what's the next step" surface today; `install-hooks` and `update` are
  `disable-model-invocation: true` (verified in frontmatter) so they are
  discoverable only if the user already knows them. Adds a read-only skill index /
  next-step advisor (e.g. `/acs:help`) that lists available skills and the current
  ticket's next pipeline step from workspace state. Mechanism deferred to the
  implementing ticket's design/spec phase. Distinct from the M3 onboarding-polish
  epic (which addresses `/acs:init` flows, not a skill catalog); maps to the
  Solo-developer persona. See roadmap M3 Wave 4 (v0.4.2+) onboarding-polish epic.
- **Invoker-scoped merge governance + out-of-band reconciliation** — scope
  ADR-0028's approved-review mandate (m6) by invoker: agent-invoked merges keep
  the APPROVED requirement; human-invoked merges defer to the repo's own branch
  protection. Detect an out-of-band-merged PR whose ticket is still `in_review`
  and reconcile state (ticket→done, archive partition, update metrics) rather
  than leaving it stranded; surface bypass-rate as a failure signal (via G19).
  This **preserves ADR-0028's core safety guarantee** — a merge still happens
  only when the readiness gate + branch protection pass — and only narrows the
  require-APPROVED-for-ALL fallback to require-APPROVED-for-AGENT, exactly the
  narrowing ADR-0028 line 47 anticipates. **MECHANISM** (a reliable
  invocation-source signal, out-of-band detection, reconciliation transport) is
  **deferred to the implementing epic**. Traces **G26** + the Solo-developer /
  Tech-lead personas. See roadmap M3 Wave 4 (v0.4.2+).
- **Brownfield-adaptive coverage policy** — a configurable coverage policy:
  **baseline ratchet** (no regression + a new-code coverage target) or
  **per-path targets**, instead of only the single repo-wide hard-fail;
  additive (unset config = today's single hard-fail). **MECHANISM** (ratchet vs
  per-path, config key shape, baseline storage) is **deferred to the
  implementing epic**. Natural companion to `/acs:standardize-project`'s
  brownfield onboarding (above) — a coverage baseline pairs naturally with
  brownfield readiness setup, without restating that feature. Traces **G27**
  (extends G3, G6) + the brownfield-onboarding story. See roadmap M3 Wave 4 (v0.4.2+).
- acs maintains the `quality/` and `operations/` doc sets for consumers (test strategy + release/ops runbooks) via `/acs:create-quality` and `/acs:create-operations`, plus `/acs:test` — a schedulable regression runner that triages failures and opens a ticket per regression (closed loop). *(Proposed — see [ADR 0011](../adr/0011-sdlc-doc-sets-quality-and-operations.md).)*
- **acs maintains the `principles/` and `standards/` doc sets for consumers** — engineering principles (e.g. `/acs:create-principles` → `principles/`) and coding standards/conventions (e.g. `/acs:create-standards` → `standards/`), each a product-level producer skill with its own planner/executor/verifier triad and acs-shipped templates, following the one-skill-per-set pattern of `/acs:create-architecture` and the proposed `/acs:create-quality` / `/acs:create-operations` (see [ADR 0011](../adr/0011-sdlc-doc-sets-quality-and-operations.md)). These sets sit between architecture and design in the conformance chain: **PRD → architecture → standards → design → specs → code**, each level verified against the one above it. Design and code MUST conform to the standards docs; the `/code` `code-verifier`'s technical-standards dimension and the design verifiers check conformance and block violations (no silent waivers). Traces G10 (+ the Tech-lead persona). *(Proposed — extends the chain at workflow.md and docs/README; see Constraints.)*
- **Architecture doc set gains an explicit project-structure target** — the `/acs:create-architecture` output set adds a project-structure document (the intended repo layout, derived from the C4 container/component views) as the canonical target a repo is expected to match. It is the layout `/acs:standardize-project` audits an existing repo against. Traces G10.
- **`/acs:standardize-project` — brownfield standardization (separate from `/acs:create-project`, which stays greenfield-only)** — audits an EXISTING repo against its principles + standards doc sets, the architecture project-structure target, and acs-readiness tooling (coverage/CI/pre-commit/e2e harness — scaffolding a repo-side e2e CI workflow + runner and, opt-in, wiring it as a required e2e merge-gate status check for an EXISTING repo that lacks one, the brownfield counterpart to greenfield-only `/acs:create-project`), then **additively** sets up the missing docs/config/tooling as **one reviewed PR**. It NEVER moves or renames existing source; structural gaps versus the target layout become **recommended follow-up tickets**, not in-place moves. Traces G10, G13 (+ the Tech-lead persona). *(Proposed; additive-only — see the C-2 guardrail in Constraints & assumptions.)*
- **Human-readable doc management (readability verifier-gate)** — every acs producer
  skill's verifier enforces doc readability as blocking findings: progressive
  disclosure, evidence archived to appendices, TOC on long docs, no mega table cells.
  Mirrors the G10 standards-conformance verifier-gate. Traces **G29**. MECHANISM (the
  per-producer readability checks, appendix/history layout) deferred to the
  implementing epic's design phase. Pairs with new constraint **C-15**.
- **Configurable doc-set storage location (external/local paths)** — each acs doc set's path is independently configurable and may point to an absolute/external path outside the consumer repo (not only repo-relative); generalizes the `prd_path`, `architecture_path`, `requirements_path`, `adr_path`, and future `standards_path`/`principles_path`/`quality_path`/`operations_path` keys under one doc-set storage-location config surface; producer skills resolve the configured location and preserve a reviewable diff there. This is the committed near-term deliverable. Traces extended G6.
- **Pluggable remote docs backend (Notion)** — mirrors the existing `tracker.provider` precedent (`local` filesystem default + `notion` as the first remote provider); supports BOTH modes per backend: (1) **publish/mirror** — repo stays source of truth, the docs-only PR is preserved, content synced to Notion for reading; (2) **authoritative-remote** — Notion is the system of record, no repo copy, review/audit happens in Notion. The **MECHANISM** — Notion API/auth, markdown→Notion-blocks mapping, PR-less vs sync delivery, per-mode review/audit — is **deferred to a dedicated future Notion/remote-docs epic's design phase**, mirroring how this PRD defers tabp's mechanism. Auth via external CLI/integration; no secrets in settings (mirrors the `tracker.provider` precedent and the Safety NFR). Traces extended G6. **Tentative version home: v0.6.0** (see roadmap M5 — v0.6.0), sequenced after the v0.4.x waves; the MECHANISM deferral above is unchanged.
- **Opt-in reverse-bootstrap from tracker + codebase** — an **opt-in** growth path
  that seeds a baseline `prd.md`/architecture by reverse-engineering from imported
  tracker issues plus the existing codebase, giving a tracker-only team a starting
  product-doc set **only when they ask for it**. Never automatic; tracker-first
  delivery works **without** it. Traces **G11**. *(Proposed; opt-in only — see the
  C-5 guardrail in Constraints & assumptions.)*
- **Org-level enforcement policy (organization & department layers).** acs gains an
  ordered **policy-source chain** above today's user + team(project) layers so an
  organization (and, optionally, a department/sub-group) can define both **shared
  defaults** (overridable convenience config — doc paths, models, tracker, formats:
  resolved most-specific-wins, extending the existing cascade) and **enforcement
  mandates** (non-overridable floors — required convention/security/standards checks:
  a repo may tighten but never loosen, may not self-exempt, and exemptions are granted
  only at the org layer, time-boxed and audited). Because a CI gate sees only the
  checked-out repo and the cascade is most-specific-wins, the enforceable part **cannot
  live in a developer-home or repo-editable file** — it must come from an org-controlled,
  non-overridable source and/or inverted floor precedence, and every effective rule
  exposes its **provenance** (which layer, who may change it). Adding the layers is
  **additive and non-breaking**: with no org source configured, resolution is identical
  to today. Connects to G10 (when the standards doc layer ships, org policy can mandate
  conformance as a floor). Traces **G12** (+ the new Org/Platform-admin persona).
  *(Proposed — the MECHANISM (cascade extension vs GitHub org rulesets / org-required
  workflows vs a versioned policy pack the repo cannot edit; the non-overridable mandate
  encoding) is deferred to a future design epic / ADR, per Constraints.)*
- **Org-scale settings & workspace distribution** — extends the **Org-level enforcement
  policy** Could-have above with the *defaults* half: an org-controlled source
  distributes shared non-enforcement defaults + a workspace convention across the full
  **org → department → project** cascade, resolved most-specific-wins (a repo may
  override a default), additive and non-breaking. Traces **G24** (extends **G12**: G12
  is the non-overridable mandate/floor half, this feature is the overridable
  defaults/distribution half — no restatement of G12's enforcement floor). **MECHANISM**
  deferred to the org epic's design phase / an ADR (same deferral as C-6).
- **Org/department-shared context lifecycle** — org/department shared, versioned/pinned
  context doc sets (standards/principles/similar) that projects consume at a pinned
  version; acs verifiers surface drift + provenance. Builds on the org/department layer
  (the feature above) and the principles/standards doc-set work (G10 features). Traces
  **G28** (+ the Org/Platform-admin persona). MECHANISM deferred to the implementing
  epic's design phase.

- **Multi-runtime support — OpenAI Codex CLI as an acs pipeline runtime** — the acs
  gated pipeline (ordering/gating, TDD, coverage hard-fail, the 12-dimension review
  loop, resumable workspace state, audit trail, merge readiness) becomes runnable on
  **OpenAI Codex CLI** in addition to Claude Code, so a team standardized on Codex CLI
  can adopt acs without switching agent runtimes. acs stays authored and distributed
  as a Claude plugin; this adds a **second execution runtime for the pipeline**, not a
  second product. The **MECHANISM** — how the Claude-Code-specific mechanisms map onto
  Codex CLI (hook gating, the planner/executor/verifier reflection-subagent protocol,
  skill/agent dispatch, per-role model/effort config, self-reported cost/tokens) — is
  **deferred to a dedicated future multi-runtime epic's design phase**, mirroring how
  this PRD defers the Notion/remote-docs and org-policy mechanisms. That design MUST
  account for documented Codex-platform constraints rather than assume a 1:1 mapping:
  Codex exposes **no skill-invocation hook matcher and no `SessionEnd` event**, its
  `PreToolUse` is a **guardrail, not a complete enforcement boundary** (so pipeline
  gating is best-effort unless deployed as org-managed `requirements.toml` hooks), and
  Codex spawns subagents **only on explicit request** via a different custom-agent
  format — so the reflection cycle is a genuine runtime divergence, not a thin shim. The
  deterministic layer is already stdlib-only Python (Portability NFR), which is the
  portable substrate this builds on. Traces **extended G6** (runtime portability).
  **Lowest-priority Could-have — sequenced after the v0.4.x waves ship, with a
  tentative version home at v0.5.0** (see roadmap M4 — v0.5.0): not started, designed,
  or ticketed until the v0.4.x waves ship; it does not compete with the v0.4.x-wave
  epics for capacity. *(Proposed — the MECHANISM is deferred to the multi-runtime epic's design
  phase / an ADR, per Constraints. Reverses the prior acs "non-Claude-Code runtimes"
  Won't-have — see Reversal note (MAR-2) in Out of scope; the separate GitLab/Bitbucket
  non-GitHub-forge Won't-have is reversed independently — see the acs Could-have
  "Non-GitHub forges (GitLab/Bitbucket) support" below and the Reversal note (MAR-71) in
  Out of scope.)*
- **Non-GitHub forges (GitLab/Bitbucket) support** — the delivery pipeline (tracker
  import/sync, PR flow) targets GitLab/Bitbucket in addition to GitHub, extending the
  Two-way tracker sync Should-have (above) to the additional forges. The **MECHANISM**
  (forge API/auth mapping, MR-vs-PR semantics) is **deferred to the forge epic's design
  phase**, mirroring the Notion/multi-runtime deferrals. **Tentative version home:
  v0.7.0** (see roadmap M6 — v0.7.0). Traces the Two-way tracker sync Should-have goals
  (above) + extended **G6** (portability). *(Reverses the prior acs "non-GitHub forges"
  Won't-have — see Reversal note (MAR-71) in Out of scope.)*

**Won't have (now)** *(acs feature scope)*
- Non-Notion remote docs providers (Confluence, Google Docs, SharePoint) — Notion is the only named remote provider; general CMS / doc-graph re-architecture is out of scope; bidirectional Notion→repo editing is out of scope now (authoritative-remote means Notion is the system of record with no repo copy, not a two-way file sync).
- Automatic downgrade of a ticket's complexity/supervision tier without explicit user confirmation — tiers are always user-confirmed; the system never silently reduces rigor.
- Claude Code plugin LSP servers (`.lsp.json`), background monitors (`monitors.json`), and `bin/` PATH executables — evaluated (MAR-82) and not adopted as acs features. **LSP** is an anti-fit: it breaks the G6 zero-install/language-agnostic portability guarantee (Portability NFR) and is redundant with Claude Code's official LSP plugins. **Background monitors** are session-scoped and overlap already-planned work — the `/acs:test` closed-loop (v0.3.8) and Scheduled background tracker sync (v0.7.0) Could-haves — so they are at most a deferred mechanism of those items, not a new feature. **`bin/` PATH executables** sit below PRD altitude: an internal helper-invocation mechanism with no user-facing change that would not serve the deliberately install-free CI path (Portability NFR). Revisit only if a concrete acs need appears.
- **GMS-built desktop app / agent host** — rationale: vendor velocity; this
  would be a **5th runtime anti-pattern** (the runtime surface today is already
  Claude Code + Codex CLI; a GMS-built host multiplies runtime coupling rather
  than reducing it, contrary to the Portability NFR). The tabp-on-Cowork
  precedent stands: build feature content on an existing host, never the host
  itself.
- **GMS-built coding SaaS for developers** — rationale: vendor surface; the
  **headless runner (G34) is the internal delegation service** — it, not a
  hosted coding product, is how unattended delivery gets triggered. Editors
  stay plural (any runtime a consumer already uses); forge-level enforcement
  (G9, G12) is what makes that heterogeneity safe, not a GMS-operated SaaS.
- **Per-department bespoke agent stacks** — rationale: **one shared core**.
  The org-structure goals (G23, G24) already provide department-level
  cascading defaults and shared delivery state; a department building its own
  agent stack instead of consuming the shared acs core would fragment the
  conformance chain. Frontend + skill content vary; the pipeline core does not.

### Feature: tabp *(RETIRED — team demo, superseded by an external consumer product; see the MAR-97 Reversal note in Out of scope)*

**What tabp was:** a recruiting/talent-screening plugin running in both Claude
Cowork and Claude Code. Its Must-have capability was **screen-cvs** — screen a
CV or a batch against a job description, producing evidence-based
Met/Partial/Missing per-requirement judgments, a weighted 0-100 match score, a
Strong/Moderate/Weak band with a Recommend/Hold/Reject recommendation, and an
inline summary + two-sheet Excel scorecard (one Sonnet subagent per CV, Opus
synthesis). It also shipped `tabp settings.json` (configurable models + CV/JD
folder paths), `.tabp/` workspace state (run history, per-screening archive,
atomic writes + spin-lock), the `/tabp:usage` skill (per-run cost/time/token
metrics), resumable runs, and an always-on verifier-as-gate
(`screen-verifier-subagent.md`, capped at N=3 remediation attempts). Its
namespace rule (never `.acs/`/`acs:` prefixes; canonical forms `.tabp/`, `tabp
settings.json`, `/tabp:usage`) and its engineering-rigor NFR (coordinator-plus-
subagents, reflection/self-verification, structured JSON state, source-grounded
evidence, decision recording) are historical record only.

**Why retired:** tabp was built and run as a **team demo** of talent
screening; it is no longer used. Its CV-screening capability is **superseded
by the external commercial consumer product** (an agentic hiring SaaS) that
acs now delivers as a consumer repo — see **G30** and the Vision's
external-consumer-product context — rather than by a marketplace plugin.

**Superseded by:** the external consumer product (unnamed in this PRD; see the
MAR-97 Reversal note). tabp's Should-have items (rich Claude artifact,
recruiter sign-off UX, Claude Cowork-runtime verification) and its Won't-have
(ATS integrations, automated hiring decisions) are retired along with the
feature and are not carried forward as acs or marketplace work.

**Git-history pointer:** the full pre-retirement feature text (Must/Should/
Won't-have bullets, the namespace rule, and the engineering-rigor NFR) is
preserved in this file's git history as of the MAR-97 amendment commit, and in
`plugins/tabp/` on disk pending its physical-removal follow-up ticket (see the
MAR-97 Reversal note in Out of scope; **docs_only** — this amendment does not
remove `plugins/tabp/**`).

## Product-level NFRs

These NFRs apply across all marketplace features. Each feature realizes them through
its own mechanisms (acs via stdlib Python + hooks; future plugins via their own patterns).

- **Determinism where possible**: ordering, gating, state writes, id allocation are scripts, never prose; gates fail closed.
- **Portability**: hooks and helpers are stdlib-only Python ≥ 3.9; no network dependencies of their own. `/acs:init` Step 0b runs a toolchain preflight — it detects and offers to install the tools acs leans on (`git`, `python3`, `gh`, `pre-commit`, `xmllint`, `acli`) so onboarding fails up front with consent rather than mid-pipeline; the convention checker stays stdlib-only so no acs install is needed on the CI runner. Runtime coupling is **isolated**: the deterministic layer (gating, state, id allocation, metrics, convention checks) stays runtime-agnostic stdlib-only Python so the acs pipeline can target a second agent runtime (e.g. OpenAI Codex CLI) without rewriting that core; runtime-specific glue (hook dispatch, subagent protocol) is the only part that varies per runtime (mechanism deferred to the multi-runtime epic).
- **Auditability**: every state file human-readable (pretty JSON), append-only run history, archived not deleted.
- **Safety**: no secrets in settings (CLIs own auth); locks prevent cross-session corruption; stale locks reported, never stolen.
- **Cost transparency**: tokens/cost/time per run, rolled up per ticket and repo.
- **Graceful degradation of the conformance chain**: the chain is **PRD (when present)
  → architecture (when present) → standards → design → specs → code**; each present
  level is verified against the present level above it, and a **missing upstream
  artifact makes only its own trace step N/A — never a hard block**. The pipeline's
  gates (ordering, TDD, coverage, review, audit, merge readiness) **fail closed
  regardless** of how many upstream docs exist.
- **Verifier-as-gate with lane-driven depth (autonomous-first)**: the verifier
  subagent is the **in-loop quality gate on every lane** — it always runs; the
  human-in-the-loop checkpoint is the PR review, not an inline approval. What
  scales with the lane is **verify depth**, not whether the verifier runs:
  `verify_depth(size, stakes)` returns `light` (a single verifier pass, iteration
  cap 1) for TRIVIAL/SMALL low/normal-stakes tickets and `full` (the up-to-3
  iteration loop + 12-dimension review + e2e when configured) for
  STANDARD/COMPLEX and **all** high-stakes tickets. The code TDD/coverage gate
  **always** runs in full in every lane and is never trimmed by depth selection.
  Gates fail closed — the gate is never the thing dropped; the lighter lane only
  reduces *iteration ceiling and decomposition stages*. (Composes with "Graceful
  degradation of the conformance chain" above: lane-driven depth scales
  *process volume*, the chain's gates still fail closed.) A mid-flight escalation
  **re-selects `verify_depth` upward** (and re-introduces any skipped
  decomposition stage) **before the verifier runs**, so a ticket that escalates
  in flight is verified at the escalated lane's depth — the escalation is a lane
  change, never a gate bypass, and never lowers depth; if a user-confirmed
  mid-flight de-escalation occurs, `verify_depth` follows the confirmed lane —
  still never a silent reduction.
- **Deterministic apply-tier executors**: apply-tier skills (create-ticket, create-pr,
  merge-pr) have deterministic executors with judgment front-loaded into
  clarification/gates; they do **not** need an iterating plan-execute-verify reflection
  loop. create-ticket's structural checks (schema-completeness, link bidirectionality)
  are a **script check, not an LLM verifier**.
- **Message-validation / per-send performance**: XML message validation runs
  **in-process** by default — `validate_xml.py`'s `validate_structurally()` (pure
  stdlib `xml.etree`, raised to XSD-equivalent coverage) is the fast path and spawns
  **no subprocess per send/receive**; a `validate_batch()` API validates a list in one
  in-process loop. `xmllint` is invoked **opt-in only** when `ACS_XML_AUTHORITATIVE=1`
  (and `xmllint` is on PATH and the XSD is present); its absence never blocks (MAR-61).
  Clarifications are **batched** at the coordinator level — when ≥ 2 are open they are
  presented in one grouped `AskUserQuestion`, each answer recorded as its own
  `clarify.py` entry.

## Constraints & assumptions

- **acs feature (runtime, revised MAR-2):** Claude Code is the **primary / today-shipping** runtime for the acs pipeline (Claude Code plugin API — skills/agents/hooks as documented). acs is **no longer Claude-Code-only**: **OpenAI Codex CLI is a supported pipeline runtime** (Could-have; see Features), so the pipeline targets **≥ 1 of an open set of agent runtimes** rather than Claude Code exclusively. The deterministic layer stays runtime-agnostic stdlib-only Python (Portability NFR); the runtime-specific MECHANISM (hook gating, reflection-subagent protocol, skill/agent dispatch on Codex CLI) is **deferred to the multi-runtime epic's design phase**. Different features may still target different runtimes (historical precedent: the retired tabp feature targeted both Claude Cowork and Claude Code).
- Delivery is git + GitHub PRs (`gh` assumed); correctness must be checkable by automated tests for the strong-fit domains (see `docs/requirements/overview.md`).
- Subagents cannot interact with the user — all user interaction happens in coordinators (drives the `needs_input` handoff design).
- **acs feature — brownfield standardization is additive-only (C-2).** `/acs:standardize-project` operates on an existing repo by ADDITION only: it adds principles/standards docs, config, and missing readiness tooling (coverage/CI/pre-commit/e2e — including scaffolding a repo-side e2e CI workflow/runner and opt-in wiring of a required e2e merge-gate status check), and it MUST NOT move, rename, delete, or rewrite existing source files. **The e2e layer stays OPT-IN: a repo with `settings.e2e` unset has no e2e suite and no e2e merge gate; the gate is configured only on explicit opt-in.** Structural gaps versus the architecture project-structure target are surfaced as recommended follow-up tickets for the user to decide on — never executed as an automatic restructure. This guardrail is deliberate: a wholesale-restructure mandate is explicitly out of scope (it is the over-engineering this product reset once before — see Out of scope). The greenfield/brownfield split is fixed: `/acs:create-project` is greenfield-only and refuses on any repo with substantive sources; brownfield onboarding is `/acs:standardize-project`'s job (C-1).
- **tabp feature — *(RETIRED — see the MAR-97 Reversal note in Out of scope)*.** tabp ran
  in both Claude Cowork and Claude Code as a fuller plugin; inputs were read from the
  project folder (in Claude Code the folder need not be a git repo; dual-runtime
  driven by MAR-40), falling back to chat attachments; the screen-cvs capability
  used one Sonnet subagent per CV with Opus synthesis; outputs included a two-sheet Excel
  scorecard and a per-run `.tabp/` archive. Historical record only — see the retired
  tabp feature stub above.
- **acs feature — doc-set storage & docs backend (MAR-48).** Doc producer skills today read/write `*_path` keys and deliver **docs-only PRs to the repo** — that is how review + Git-auditability work. Configurable external-local paths and remote backends change that delivery/audit model. **Requirement:** reviewability + auditability are preserved per configured backend — *mirror/publish* and *external-local* keep a reviewable diff / repo PR (repo stays source of truth); *authoritative-remote* uses backend-native review/audit (Notion is the system of record). **Deferral:** the MECHANISM (Notion API/auth, markdown→blocks mapping, PR-less vs sync delivery, per-mode review/audit) is deferred to the future Notion/remote-docs epic's design phase, mirroring how this PRD already defers tabp's mechanism. Auth via external CLI/integration; **no secrets in settings** (consistent with the `tracker.provider` precedent and the Safety NFR). The local filesystem backend with external/absolute paths is the near-term committed deliverable; the Notion/remote backend is future + deferred.
- **acs feature — tracker-first is graceful degradation, not a parallel pipeline (C-5).**
  Tracker-first / PRD-optional mode reuses the **one existing gated pipeline** (same
  gates, TDD, coverage, review, audit, merge readiness); it is **not** a second
  workflow. acs **never auto-authors a PRD/roadmap/architecture** — reverse-bootstrap
  is **opt-in** (Could-have) and off by default. The conformance chain degrades
  gracefully: **PRD (when present) → architecture (when present) → standards → design
  → specs → code**; a missing upstream artifact makes its trace step N/A, never a hard
  block. This guardrail is deliberate — a parallel "tracker pipeline" or
  auto-PRD-generation would repeat the abandoned MAR-16..24 over-engineering (see Out
  of scope).
- **acs feature — org enforcement uses an org-controlled, non-overridable source; layers are additive (C-6).** Org-level *defaults* extend today's most-specific-wins cascade (a new org source resolved below user, fully overridable). Org-level *mandates* are the opposite: because a CI gate sees only the checked-out repo (the convention checker reads the committed project `.acs/settings.json`, not a developer home dir) and the cascade is most-specific-wins (a repo layer would silently override an org layer), an enforceable org mandate MUST come from an org-controlled source the repo cannot edit and/or use inverted **floor** precedence (repo may tighten, never loosen), with exemptions granted only at the org layer (a repo cannot self-exempt from a mandate) and every effective rule carrying provenance (which layer it came from). Introducing org/department layers is **additive and non-breaking**: with no org source configured, resolution is identical to today's user + team(project) behavior. Floors **compose down the org → department → project hierarchy** — a department may tighten the org floor, a project may tighten both, none may loosen an inherited floor; exemptions are granted only at the layer that owns the mandate. The MECHANISM (cascade extension vs GitHub org rulesets / org-required workflows vs a versioned policy pack) is deferred to a future design epic / ADR (this PRD states the WHAT).
- **acs feature — complexity tier is a confirmed flag set once at create-ticket; default is full rigor; lighter tiers are opt-in (C-7).** The complexity/supervision tier is set **once, user-confirmed, at create-ticket**, alongside the existing `needs_design` flag and following that exact precedent (a confirmed flag gating downstream skills). The **default stays full/standard rigor**; trivial/small fast lanes are **opt-in**, so rigor is **never silently dropped**. The code TDD/coverage gate and the in-loop verifier gate both run in every lane (autonomous-first); what the lighter lanes make conditional is the **verify depth** (light = single pass, iteration cap 1) and the heavyweight decomposition stages (standalone create-spec / separate planner), never whether a gate runs. (Mirrors how `needs_design` is a confirmed flag gating the design step.) Cross-reference: the Out of scope section records that automatic downgrade of a ticket's complexity/supervision tier without explicit user confirmation is out of scope. *(Assumption: this constraint follows the `needs_design` confirmed-flag precedent — verified in `ticket.json` (`"needs_design": false` field present), confirming the precedent exists and no new pattern is invented.)*
- **acs feature — release versioning is additive to the existing roadmap/release model; the cut mechanism is deferred (C-8).** Modeling release versions as first-class planning units is **additive and non-breaking**: the roadmap already labels milestones with versions (e.g. "M3 — v0.4.0") and that labeling stays valid; this amendment adds an explicit version → milestone/epic mapping and a capability to cut a release — it does not restructure the existing milestone tracks. The **release-cut mechanism** (new skill name/shape, version-object schema, changelog-aggregation source, tag/GitHub-release implementation, and its coupling to the existing `marketplace.json`/`plugin.json` version-bump + Release workflow described in the README) is **deferred to the implementing epic's design phase / an ADR**, mirroring the Notion/org-policy deferrals above. Auth stays via `gh` (no secrets in settings — consistent with the Safety NFR).
- **acs feature — guided architecture selection is select/refine over an acs-shipped catalog; it never overrides the user's decision, and the catalog source-of-truth is deferred (C-9).** The catalog **augments** `/acs:create-architecture` — it offers a pre-filtered/ranked shortlist across the four categories, and the **user still owns the final selection** (decision-support framing, consistent with the human-owns-requirement-decisions Vision). It **adds no new doc set** and does not change the architecture doc-set outputs. The **catalog source-of-truth and the selection/ranking UX are MECHANISM — deferred to the implementing epic's design phase.**
- **acs feature — tracker/PR metadata sync is additive over the existing sync, and the value source-of-truth is deferred (C-10).** Setting PR assignee/reviewers and the intermediate ticket-Status transition is **additive and non-breaking**: create-ticket already fills Type/Status/Labels/Assignee/Milestone and merge-pr already sets Status→Done; this amendment adds the missing PR-side metadata and the in-review status transition, and NEVER reduces or reorders existing sync behavior. The PR **assignee is decided** — always the PR author (the authenticated `gh` user who runs the pipeline); the **value source-of-truth for the other fields** (which reviewers; which Project Status option maps to "in review"; the priority/story-points/parent field-to-column mapping) is **MECHANISM deferred to the implementing epic's design/spec phase**. A field with no resolvable value is skipped as expected data (mirrors the create-ticket null-assignee rule), never a hard block. Auth stays via `gh`/`acli` — **no secrets in settings** (Safety NFR).
- **acs feature — team-shared state is additive, honors the Safety + Auditability NFRs, and its mechanism is deferred (C-11).** A shared workspace / shared allocation authority for team delivery state (G23) **must not** weaken the "stale locks reported, never stolen" rule or the append-only/never-deleted audit invariant (Product-level NFRs above); with **no shared source configured, behavior is identical to today's per-user local workspace** (additive/non-breaking, mirrors C-6/C-8/C-10). The org-distributed defaults source (G24) is a *default* layer — overridable per repo — distinct from a **G12** *mandate*, which a repo cannot loosen. **MECHANISM** (shared-mount vs synced workspace vs tracker-as-id-authority vs a shared counter service; the org source's distribution transport) is **deferred to the implementing epic's design phase / an ADR**, mirroring the C-6/C-8/C-9/C-10 precedent.
- **acs feature — dynamic lane re-decision is additive, upward-only-automatic, and its trigger/mechanism is deferred (C-12).** Mid-flight lane re-decision **extends** the C-7 confirmed-flag model without replacing it: the lane is still *set once, user-confirmed, at create-ticket* (C-7, above); dynamic re-decision only **raises** it in flight on an observed higher-stakes/larger signal — **automatic, upward-only, and sticky**. Automatic **downgrade** stays out of scope (see Out of scope); a lane is never silently reduced. A **user-confirmed mid-flight de-escalation** is permitted **only with explicit user confirmation** — never automatic — which is consistent with, and does not contradict, the Out-of-scope entry (which bars only *automatic* downgrade). With **no higher-stakes signal observed, behavior is identical to today's static lane** (additive/non-breaking, mirrors C-6/C-7/C-8/C-11). The **MECHANISM** — the exact in-flight signal set (which surfaces/paths count as higher-stakes), the detection point in the pipeline, how re-decision re-enters a skipped stage, and how a user-confirmed de-escalation is requested/applied — is **deferred to the implementing epic's design phase / an ADR**, consistent with the C-6…C-11 deferral precedent.
- **acs feature — invoker-scoped merge governance preserves ADR-0028's safety model; the invocation-source signal is deferred (C-13).** The readiness gate + branch protection remain the two independent brakes unchanged (ADR-0028 m1/m2/m3/m4); this narrows ONLY the require-APPROVED fallback (m6) from "all invocations" to "agent invocations," which is exactly the narrowing ADR-0028 line 47 anticipates once a reliable invocation-source signal exists. Out-of-band reconciliation is additive — a repo that never merges out-of-band sees no change. **MECHANISM** (the invocation-source signal, out-of-band detection + reconciliation) is **deferred to the implementing epic's design phase / an ADR update**. Serves G26.
- **acs feature — brownfield coverage policy is additive; the policy mechanism is deferred (C-14).** With no coverage-policy config set, behavior is byte-identical to today's single repo-wide `test_coverage_percent` hard-fail (additive/non-breaking, mirrors C-6); the ratchet/per-path policy still fails closed (never silently waived — consistent with G3 and the Verifier-as-gate NFR). **MECHANISM** (ratchet vs per-path, key shape, baseline storage) is **deferred to the implementing epic's design phase**. Serves G27.
- **acs feature — amendments archive evidence, they do not inline it (C-15).** Historical/validation evidence goes to **appendix/history docs**, not inline in goal/feature cells (cells state goal + metric only, evidence linked); this makes **G29** durable. **Phasing:** applies to new/amended content; the pre-existing inlined-evidence backlog is remediated by the separate content-preserving restructure follow-up, not this amendment.
- **acs feature — the external consumer product is a consumer repo, not a marketplace plugin; no pipeline fork (C-16).** The external commercial consumer product (an agentic hiring SaaS) that acs delivers per **G30** is treated exactly like any other consumer repo acs runs against — it is **not** an entry in `marketplace.json`, not a catalog plugin, and not designed or built inside this repo. acs delivers its codebase through the **standard gated pipeline**, with **no consumer-specific pipeline fork or special-cased skill/gate behavior** (mirrors the "one pipeline, not a parallel workflow" discipline already used for tracker-first delivery, C-5). This repo's own dogfooding and that consumer's delivery are two separate consumer repos running the same acs pipeline, not two products.
- **acs feature — full eval coverage is additive over the shipped harness; the local-only, artifact-not-prose discipline and the pre-release paid gate are preserved (C-17).** Full-eval-coverage work (G31/G32) **extends** the shipped E1 harness and its per-plugin `evals/<plugin>/` seam; it does **not** move evals into CI (behavioral/LLM evals stay local-only, the paid tier remains a manual pre-release gate) and does **not** change the artifact-not-prose assertion rule. With no new scenarios added, behavior is identical to today (additive/non-breaking, mirrors C-6/C-14). **MECHANISM** (exact scenario list, coverage-ratio reporting surface, namespace-isolation check implementation) is **deferred to the implementing epic's design/spec phase**.
- **acs feature — headless runner safety invariant, NORMATIVE (C-18).** Unattended execution **ALWAYS** runs the **COMPLEX/UNATTENDED lane (full verify)** — **no configuration can assign a fast lane to an unattended run** — and **always stops before `/merge-pr`**. This composes with (does not weaken) the Verifier-as-gate NFR (above), **C-7** (lane set once, user-confirmed), and the existing `/acs:ship`-stops-before-merge rule. It is a **floor a fast-lane value can never bypass**, mirroring the existing high-stakes floor (Complexity-adaptive delivery feature, above). Serves **G34**. **MECHANISM** (how the runner forces the lane, trigger auth) is **deferred to the implementing epic's design phase**.
- **acs feature — the operating model is a role/decision-rights artifact, not a hiring/titles doc; role gates live at the forge (C-19).** The five-seat AI-native operating model (above) describes **decision rights over the conformance chain**, not headcount or job titles; concrete hiring/titles remain out of scope (see Out of scope). Role **enforcement** (who may approve, merge, or sign off) lives **at the forge** (CODEOWNERS, branch protection, org rulesets — **G9**, **G12**), **not inside acs skills** — acs itself stays role-agnostic; the forge is the gate. **Additive:** with no operating-model roles declared, acs behavior is unchanged.

## Out of scope

Visual/UX-judged work without an automatable test strategy, hardware-in-the-loop
testing, model training pipelines, registry distribution beyond the GitHub URL.

Per-plugin separate PRDs and per-plugin acs configuration are out of scope — this
single `prd.md` covers the GMS Marketplace product and all its plugin features. The
MAR-17 restructure (separate per-plugin PRDs) was abandoned. **tabp is now retired**
(see the MAR-97 Reversal note below); its physical removal — deleting
`plugins/tabp/**`, the tabp eval suite, and the tabp `marketplace.json` entry, plus
any tabp-coupled CI version logic — is a **recommended follow-up delivery ticket**,
explicitly **not** performed by this docs-only amendment (this PRD and the roadmap
record the retirement; the removal is out of scope here).

Automatic wholesale repository restructuring is out of scope. Brownfield
standardization (`/acs:standardize-project`) is additive-only by constraint
(C-2 above): it never moves or renames existing source. Re-laying-out an
existing codebase to match the architecture project-structure target is a
human-decided follow-up, surfaced as recommended tickets — not something acs
performs automatically. This guardrail exists to avoid repeating the abandoned
MAR-16..24 over-engineering reset.

A general CMS / document-management product or a doc-graph re-architecture is out of
scope — this is a bounded config + pluggable-backend capability only. Remote docs
providers other than Notion (Confluence, Google Docs, SharePoint, etc.) are out of
scope now — Notion is the only named remote provider; others are Won't-have (mirrors
the acs Features Won't-have). Bidirectional Notion→repo editing (treating Notion edits
as the inbound source that rewrites repo files) is out of scope now; the
authoritative-remote mode means Notion is the system of record with no repo copy, not
a two-way file sync.

**Auto-authoring product docs from a tracker is out of scope.** Tracker-first mode
never generates a `prd.md`/roadmap/architecture automatically; reverse-bootstrap
(seeding those from imported tickets + codebase) is an **opt-in Could-have** the user
must invoke. Tracker-first / auto-authoring applies to the supported trackers only
(GitHub Projects / Jira via `gh` / `acli`); **this tracker-first / auto-authoring scope
stays limited to those trackers** (GitLab / Bitbucket are not additional tracker-first
sources here). This is distinct from GitLab/Bitbucket as a **general delivery-forge
target** (tracker import/sync, PR flow), which is now a **Could-have** (MAR-71) with a
tentative v0.7.0 home — see the acs Could-have "Non-GitHub forges (GitLab/Bitbucket)
support" and the Reversal note (MAR-71) above.

**Reversal note (MAR-35):** this amendment reverses the prior "tabp is skills-only"
product decision that was previously stated in this PRD and in MAR-26 design C-arch-5
(skills-only plugin shape). tabp remains a **FEATURE of the one GMS Marketplace
product** — a fuller feature, not a separate product. This does NOT re-introduce the
abandoned MAR-17 per-plugin-sub-product / separate-per-plugin-PRD approach. The tabp
feature section above replaces the skills-only framing with the fuller-plugin shape.
**Update (MAR-85):** the tabp-upgrade epic's core capabilities — `tabp settings.json`,
`.tabp/` workspace state, `/tabp:usage`, resumable runs, and the reflection/
self-verification (always-on verifier) engineering-rigor pattern — are **now shipped**
(verified on disk: `plugins/tabp/README.md`, `plugins/tabp/agents/*`,
`plugins/tabp/helpers/tabp_helper.py`, `plugins/tabp/schemas/*`); the tabp feature
section above records them as Must-have (shipped). Only the rich-Claude-artifact
rendering, the explicit recruiter-sign-off UX, and Claude Cowork-runtime verification
of the shipped shape remain unbuilt — these carry forward as tabp Should-have items
and are the scope of the tabp-upgrade epic's remaining follow-on work.

**Reversal note (MAR-42):** this amendment reverses the prior Vision guardrail that the
human owns "the merge button" — i.e. that `/acs:merge-pr` is invocable only by a human. Per
MAR-42 (design approved; **ADR-0028** — "merge-pr is agent/model-invocable; readiness gate +
branch protection are the merge brakes"), `/acs:merge-pr` is now agent/model-invocable. The
human still owns **requirement decisions**. The safety guarantee shifts from "a human must
press merge" to "merge happens only when the readiness gate (CI/approvals/conflicts/
protections) and the repo's branch protection pass, by whoever invokes; failures are
report-only; every attempt is audited," with agent-invoked merges additionally requiring an
approved review (m6). `/acs:ship` still deliberately stops at create-pr (review separation, not
a merge prohibition). This is a product-level Vision change only; the detailed `/acs:merge-pr`
behavior lives in `docs/requirements/skills.md` and the skill prose and is delivered by MAR-42.

**Reversal note (MAR-2):** this amendment reverses the prior "non-Claude-Code runtimes
for the acs pipeline" product decision previously stated as an acs Won't-have. Per
MAR-2 (user-approved, C-1), **OpenAI Codex CLI is now a supported acs pipeline
runtime**. acs remains authored and distributed as a Claude plugin and the **one GMS
Marketplace product** — this adds a **second execution runtime for the pipeline**, not
a second product and not a per-runtime fork of the pipeline. Claude Code stays the
primary/today-shipping runtime; Codex CLI is a Could-have whose **MECHANISM** (mapping
the PreToolUse/SessionEnd hook gating, the planner/executor/verifier reflection-subagent
protocol, and skill/agent dispatch onto Codex CLI) is **deferred to a dedicated future
multi-runtime epic's design phase / an ADR** — exactly as this PRD defers tabp's and
the Notion/remote-docs mechanisms. MAR-2 reversed **only the runtime clause**; the
GitLab/Bitbucket non-GitHub-forge Won't-have is **separately reversed by MAR-71** —
see the Reversal note (MAR-71) below.

**Reversal note (MAR-71):** this amendment reverses the prior "non-GitHub forges
(GitLab/Bitbucket)" acs Won't-have. Per MAR-71, **GitLab/Bitbucket become a Could-have**
— the delivery pipeline's tracker import/sync and PR flow extend to the additional
forges, with a **tentative version home at v0.7.0** (see roadmap M6 — v0.7.0; see the
acs Could-have "Non-GitHub forges (GitLab/Bitbucket) support" above). The **MECHANISM**
(forge API/auth mapping, MR-vs-PR semantics) is **deferred to the forge epic's design
phase**, mirroring the Notion/multi-runtime deferrals. This reversal does **not** reopen
any other Won't-have: Notion-only remote providers, ATS integrations, and the
wholesale-restructure guardrail all remain out of scope, unchanged.

Non-GitHub org-policy backends are out of scope — org enforcement targets the GitHub
org-controlled surface first (org rulesets / org-required workflows); other forges remain
Won't-have, consistent with the acs Won't-have above. Automatic org-wide migration or bulk
retrofitting of existing repos to an org policy is out of scope — applying org policy to a
repo is an opt-in/rollout action surfaced per repo, never an automatic mass rewrite (same
additive, no-wholesale-restructure discipline as C-2 above and the MAR-16..24 reset note
above). A general non-GitHub policy distribution system is out of scope.

Automatic downgrade of a ticket's complexity/supervision tier without explicit user
confirmation — tiers are always user-confirmed; the system never silently reduces rigor.
A **user-confirmed** mid-flight de-escalation (G25/C-12) is in scope; only
**automatic** downgrade remains out of scope.

A hosted / multi-tenant acs server operated as a running service for shared team
delivery state is out of scope — team-shared state (G23) and org-distributed defaults
(G24) stay config + shared-filesystem/tracker conventions, not a new backend service
the org must run and operate.

**Reversal note (MAR-97) — tabp retired; external consumer product introduced:**
this amendment **retires the tabp feature**. tabp was built and run as a **team
demo** of talent screening; it is no longer used, and its CV-screening
capability is **superseded by an external commercial consumer product** (an
agentic hiring SaaS, GMS-internal today with future external sale — not named
in this PRD; the name lands in a later amendment at launch) that acs delivers
as a consumer repo (see **G30**, **C-16**). Consequences of this retirement,
recorded across this PRD:

- The **tabp feature section** collapses to a retired stub (what tabp was, why
  retired, superseded-by, git-history pointer) — see Features above.
- The **tabp success metrics (T1-T7)** are frozen — retitled RETIRED, kept in
  place (not renumbered, not deleted) as a historical record.
- The **TABP recruiter / hiring team persona** is removed from Target users &
  personas (see the retirement note beneath that table).
- The **tabp feature constraint** and the runtime constraint's tabp clause are
  marked historical.
- The Marketplace's active catalog is now **1 plugin (acs)**; the **G20**
  catalog-growth/quality-bar goal is unchanged in intent and metric-corrected
  (no longer counting tabp as a passing catalog plugin) — it remains the path
  by which future plugins, including a possible reintroduction of a
  screening-adjacent capability, would join the catalog.
- **Physical removal is a recommended follow-up ticket, not this PR.** This
  amendment changes only `docs/product/prd.md` and `docs/product/roadmap.md`;
  `plugins/tabp/**`, the tabp eval suite, and the tabp `marketplace.json` entry
  remain on disk pending that follow-up ticket.
- **MAR-94 / PR #182 re-scope flag — resolved.** MAR-94 (PR #182) landed
  **acs-only** (merged as `62b4c99`, "Amend PRD: full evaluation coverage for
  plugins"): its acs-behavioral eval-coverage half shipped as **G31/G32/C-17**
  (above); the tabp eval-coverage half it originally proposed — tabp trigger +
  namespace evals under the reserved goal/target **T8** — was **mooted by this
  retirement** and never built; **T8** stays frozen/historical alongside T1-T7
  (Feature: tabp, above). No further re-scope action is pending.

**External consumer product — scope clarity:** the external commercial
consumer product referenced by **G30** is an **external product delivered
using acs**, not a marketplace plugin and not a catalog entry. acs treats it as
a **consumer repo, like any other** — its codebase never lives in this repo,
and acs runs the **same gated pipeline** against it with **no
consumer-specific pipeline fork** (see **C-16**; mirrors the "one pipeline, not
a parallel workflow" discipline used for tracker-first delivery, C-5). This
repo's own dogfooding and that consumer's delivery are two separate consumer
repos running the same pipeline, not two products.

**Platform-strategy direction — now split between in-scope and still-out-of-scope:**
the platform-strategy direction flagged by the prior (MAR-97) amendment as a
candidate future amendment is **now partially activated** by this amendment:

- **NOW IN scope (this amendment):** the **headless runner** (see **G34**, the
  Headless unattended runner feature, and the **C-18** safety invariant);
  **persona-lane segmentation**, delivered as the **AI-native operating model**
  (the five-seat personas extension + **G35** role accountability, above); and
  **vertical frontends**, recorded as **guidance** rather than a committed
  feature — see the vertical-frontend ladder immediately below.
- **STILL OUT of scope:** GMS-internal **MCP connector infrastructure** —
  recorded as a context note only, not designed here (see immediately below);
  the **desktop-app / coding-SaaS / per-department-bespoke-stacks** direction,
  now explicit **Won't-haves** (Features, above); and concrete hiring/titles
  beyond what the operating model states as decision rights (**C-19**).

**Vertical-frontend ladder (guidance, not a committed feature):** if/when a
vertical (non-CLI) frontend for acs is warranted, the climb is: (1) **Desktop /
Cowork chat** surface first: (2) a **thin read/trigger web portal** next; (3)
**embed in an existing system of record** (e.g. the tracker or a docs tool)
after that; (4) a **standalone app** only as a last resort. Each rung is
climbed only on **observed adoption signals**, never speculatively; no rung of
this ladder is a committed deliverable of this amendment.

**MCP connector infrastructure (context note, not designed here):** a
GMS-internal MCP connector layer was part of the platform-strategy direction
this amendment activates in part. It remains **out of scope / context-only**:
this amendment does not goal, feature, or roadmap MCP connector infrastructure;
it is recorded here so a future amendment has the context without re-deriving
it.

**External-consumer-product PRD pointer:** the external consumer product's own
PRD and roadmap live in **its own repo**, authored via the same greenfield
`/acs:create-prd` chain acs uses for any consumer repo — never in this PRD, and
the external consumer product is **never named** here (see the MAR-97
confidentiality rule, above). The retired tabp feature's **T1-T7** quality
themes migrate conceptually to that product's own PRD, where its
CV-screening-adjacent capability is now delivered — this PRD carries T1-T7 only
as the frozen historical record (Feature: tabp, above); it does not restate
them there.
