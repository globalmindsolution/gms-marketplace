# Reflection & Subagent Architecture

## Coordinator–subagents pattern

The workflow is built on a **coordinator–subagents** architecture:

- For each skill invocation, a **coordinator** (the main agent running the
  skill) orchestrates dedicated **subagents**.
- The coordinator performs **dynamic decomposition**: it breaks the skill's
  work into subagent tasks based on the actual ticket/specs at hand (e.g. one
  executor task per spec), rather than a fixed, hard-coded task list.
- The coordinator MUST NOT keep conversation history between workflow steps.
  Everything a later step needs is read from JSON files in the workspace
  (see [workspace-and-state.md](workspace-and-state.md)).

## Reflection pattern: plan → execute → verify

The twelve **triad-keeping skills** (code, docs-sync, create-prd, create-design,
create-architecture, create-project, create-quality, create-operations,
create-principles, create-standards, standardize-project, create-requirements) MUST apply the
Reflection pattern as a
**plan–execute–verify cycle**, with a **different subagent for each phase**.
All twelve now run a plan-once shape of this cycle, where the plan phase
runs exactly once per run before the loop rather than per iteration:
`/acs:code`, `/acs:docs-sync`, `/acs:create-project`,
`/acs:standardize-project`, `/acs:create-prd`, `/acs:create-quality`,
`/acs:create-standards`, `/acs:create-operations`, `/acs:create-principles`,
`/acs:create-architecture`, `/acs:create-design`, and
`/acs:create-requirements` — see the `code` conditional-triad note
immediately below and the Exception bullet under Requirements for the full
statement.
Each phase runs in a separate context window so the verify phase judges the work
fresh rather than rubber-stamping its own output. **`code` is a conditional
triad (MAR-72):** its plan phase spawns the `code-planner` subagent only on
STANDARD/COMPLEX lanes; on TRIVIAL/SMALL the coordinator authors the plan
artifact itself, with zero planner spawns, against the identical artifact
contract — execute and verify stay unconditional on every lane, so only the
plan phase's subagent-vs-coordinator authorship varies by lane. The table
below shows the three phases and their responsibilities for a representative
triad-running skill:

| Phase | Subagent (example for `/code`) | Responsibility |
|-------|--------------------------------|----------------|
| Plan | `code-planner` | Analyze inputs (workspace state, repo, docs, config); produce a concrete plan for the executor. |
| Execute | `code-executor` | Carry out the plan; produce the skill's artifacts (ticket, design, specs, code, PR, merge). |
| Verify | `code-verifier` | Independently check the executor's output against the plan and the skill's quality bar; report pass/fail with findings. |

### Apply-work skills: inline shape (MAR-55 invariant (b))

The **apply-work** group — `/acs:create-pr`, `/acs:merge-pr`, and
`/acs:create-ticket` — does **not** apply the Reflection pattern. These skills
are inline and deterministic: the coordinator handles the work directly,
optionally delegating to at most one executor subagent. No plan-phase subagent
and no verify-phase subagent are spawned — this holds in every lane. Upstream
quality is gated by the code-verifier (before the PR is opened or merged) or by
the user-confirmation gate (at ticket creation); there is no in-skill verify
phase for these three skills.

Requirements:

- The three phases MUST be separate subagents (separate context windows), so
  the verifier judges the work fresh rather than rubber-stamping its own
  output.
- On verification failure, the cycle reflects: the coordinator feeds the
  verifier's findings back into another iteration. For every one of the
  twelve triad-keeping skills, findings feed the **executor's** `<context>`
  on the next iteration — execute → verify only, with no re-plan and no
  second planner spawn (MAR-71, slice 1b of MAR-69, for `/acs:code`;
  MAR-300 for `/acs:docs-sync`; MAR-301 for `/acs:create-project`; MAR-302
  for `/acs:standardize-project`; MAR-305 for `/acs:create-prd`,
  `/acs:create-quality`, `/acs:create-standards`, `/acs:create-operations`,
  and `/acs:create-principles`; and completing the migration for
  `/acs:create-architecture`, `/acs:create-design`, and
  `/acs:create-requirements`). For `/acs:code` on TRIVIAL/SMALL specifically
  there is no planner to feed back into in the first place — the plan was
  coordinator-authored with zero planner spawns, so the loop-back is
  executor-only on every lane; escalating mid-flight to STANDARD/COMPLEX
  never retro-spawns a planner either (MAR-72, D-3). None of the other
  eleven triad skills has a lane-conditional planner — each runs a fixed
  iteration cap of 3 in every lane (MAR-300, MAR-301, MAR-302, MAR-305, and
  the completion of this migration for `/acs:create-architecture`,
  `/acs:create-design`, and `/acs:create-requirements`).
  - The cycle runs at most **lane-driven iterations**:
    - **TRIVIAL/SMALL lanes** (low/normal stakes): at most **1 iteration** (light
      verify — single verifier pass that may iterate once on blocking findings;
      cap = `VERIFY_ITERATION_CAP["light"]` = 1).
    - **STANDARD/COMPLEX lanes**, or any **high-stakes** ticket: at most
      **3 iterations** (full verify — execute → verify loop, with the plan
      authored once before it starts rather than a per-iteration
      plan→execute→verify loop, + full 16-dimension, multi-lens review + e2e
      when configured; an iteration is one execute+verify round; cap =
      `VERIFY_ITERATION_CAP["full"]` = 3). Full verify's 16 dimensions are
      split across 4 parallel independent lenses (each reading a distinct
      evidence source), followed by a coordinator-performed
      confidence-scoring/adversarial merge pass before findings count; light
      verify keeps today's single-subagent, 15-dimension pass unchanged.
    - When `ticket.lane` or `ticket.stakes` are absent or unrecognized, default
      conservatively to full (3-iteration ceiling).
    - On hitting the lane's cap with findings remaining, the skill stops and
      records its findings and stop reason in its state file.

  **Absolute invariants — apply in every lane regardless of verify depth:**

  - The **verifier subagent is the in-loop quality gate in every lane** (C-5).
    Light verify differs from full only in iteration ceiling; the verifier always
    runs. There is no inline human-approval gate; the human-in-the-loop
    checkpoint is the PR review before merge.
  - The **TDD/coverage gate runs in full in every lane and is never trimmed by
    verify-depth selection** (invariant a, MAR-55). Depth selection is not a
    verify dimension that light mode drops.

  **Mid-flight ceiling raise on escalation (MAR-57).** The lane-driven ceiling
  stated above is the *initial* ceiling, computed at the start of the `/code`
  run. If an in-flight escalation trigger fires mid-run (verifier finding of
  higher stakes/size, a `high_stakes_paths` glob match on a touched file, or an
  explicit user/agent request), the coordinator recomputes the ceiling via
  `VERIFY_ITERATION_CAP[verify_depth(new_lane, new_stakes)]` and raises the
  in-flight ceiling **monotonically** — it is never lowered. A ticket that
  starts at a TRIVIAL/SMALL ceiling (1 iteration) and escalates to
  STANDARD/COMPLEX (3 iterations) immediately acquires the full 3-iteration
  ceiling for all remaining iterations. The absolute invariants above (verifier
  always runs in every lane; TDD/coverage gate immutable in every lane) hold
  regardless of any in-flight ceiling change. Every escalation event is
  durably recorded — not just a ceiling change — via `record_escalation_event`
  appending a fixed 13-field event (from/to lane, from/to axes, trigger,
  source, ceiling before/after, direction, confirmation ref) to
  `runs[-1].escalations` on `code-state.json` (MAR-106), so no lane change is
  silent. Re-selection happens at the iteration-start **detection point**: the
  start of each iteration, after the prior verifier and before the current
  execute — so an escalation always lands before the next verifier pass
  (MAR-107 D4). When a fast lane (TRIVIAL/SMALL) crosses the fold boundary
  into a full lane (STANDARD/COMPLEX), the former fold-boundary stage re-entry
  no longer applies: since ADR 0066 every lane authors its spec content inside
  `/code`'s own plan phase, so there is no decomposition stage left to
  re-enter — the crossing raises the verify depth and the in-flight iteration
  ceiling only, monotonically and never lowered (`code/SKILL.md`'s "In-loop
  escalation check" and "Spec authoring fold" sections). The lane/axes are never *automatically* downward — the
  one exception is a user-confirmed de-escalation (MAR-108), offered only at
  an iteration or run boundary, never mid-iteration, requiring an explicit
  `AskUserQuestion` confirmation recorded via `clarify.py` before the
  dedicated `confirm_deescalation` writer (`acs_lib.py`) is called with that
  ledger reference. `confirm_deescalation` is unreachable without a resolved,
  answered `clarify_ref`, and every such drop is durably audited exactly like
  an upward event (`direction: "down"`, non-null `confirmation_ref`) — no
  lane change, up or down, is ever silent.

- Subagent naming convention: `<skill>-planner`, `<skill>-executor`,
  `<skill>-verifier`. 45 agent files exist on disk in total and are retained
  (C-4) — three role files for each of fifteen skill prefixes that have agent
  files. Only the **twelve** triad-keeping skills listed in the heading above
  actively spawn the full plan→execute→verify triad. The other three prefixes
  belong to the **apply-work** skills, which run inline and never spawn a
  plan-phase or verify-phase subagent (see the "Apply-work skills" subsection
  below).
- For the **apply-work** group, only the executor-suffix agent file may be
  delegated to at most once per invocation; the plan-phase and verify-phase
  agent files are retained on disk but the coordinator no longer spawns them.
  See the "Apply-work skills" subsection above for the full inline shape.
- Each role's **model and reasoning effort are user-configurable** in
  `settings.json` (`models.planner` / `executor` / `verifier`, with
  per-skill overrides); unset values inherit the parent context's model and
  effort ([configuration.md](configuration.md#subagent-models)).

> **Note:** the `code-verifier` carries the broadest verification scope: in
> addition to spec conformance, tests, and coverage, it reviews the whole
> changeset (business logic, features, quality, technical standards
> (conformant with the `standards/` doc set at `standards_path` when
> configured; falls back to documented architecture when unset),
> architecture, system design, security, documentation, and
> **Simplicity & scope** — overcomplication and out-of-scope edits are
> blocking). There is no separate review skill — see [skills.md](skills.md).
>
> **Verifier anchoring**: a verifier judges the work against the **gated
> upstream contracts** (specs, ticket, design), never against the
> same-iteration plan — an unverified plan must not be able to certify the
> work it shaped. The plan's contribution to verification is its **verifier
> checklist** section only (a floor, never a ceiling), and verifiers never
> read executor reasoning — only artifacts.
>
> **Bounded exception — `/acs:code` plan conformance (MAR-74, slice 4 of
> MAR-69, ADR 0073)**: for `/acs:code` alone, and for the `code-verifier`'s
> plan-conformance dimension (15) alone, the approved plan's `## Executor
> tasks & file map` and its folded `Approach`/`API/data changes` content are
> additionally a bounded conformance contract. The dimension is active only
> while the verifier itself computes — never from a coordinator-relayed
> value — that `<partition>/phases/code/plan-approval.json` exists and
> parses, carries `eligible: true` and `plan_path == phases/code/plan.md`,
> and pins a `plan_sha256` equal to the current `plan.md` bytes; when any
> condition fails the dimension reports an evidenced **N/A**, never a block.
> The hazards ADR-0004 named are structurally absent in exactly this case:
> the approval is a deterministic non-LLM predicate over the plan's own
> bytes (MAR-73), and since MAR-71 the plan is not a same-iteration artifact
> at all — it is authored once, before the loop. The dimension is strictly
> **subordinate to acceptance-criteria conformance** (dimension 1): an
> approved plan is never evidence that an acceptance criterion is satisfied.
> Everywhere else — every other dimension, every other skill, and every case
> where the record is absent or does not hold — the rule above stands
> unchanged, the plan a floor and never a ceiling. When the plan itself is
> wrong, the boundary-gated, `clarify.py`-recorded revocation path
> (`plan-superseded-<k>.md`) revises and re-approves it instead of bending
> the rule.
>
> **Spec-time vs. code-time simplicity (MAR-88)**: the plan's author (the
> `code-planner` on STANDARD/COMPLEX; the coordinator on TRIVIAL/SMALL,
> **best-effort**, MAR-72)
> evaluates each decomposition for a **materially** simpler alternative
> meeting the **same acceptance criteria**, and **surfaces** (never blocks) a
> finding to the user/spec owner for a **decision** — a spec-time check on
> the chosen **approach**, before any code exists. `code-verifier` dimension
> 12 ("Simplicity & scope") is a code-time, **blocking** check on the
> **code** the executor wrote against the already-accepted spec. The two
> never double-count: they inspect different artifacts (approach vs. diff) at
> different times, so a decomposition accepted at spec time is never
> re-litigated by dimension 12 — it only judges conformance and internal
> simplicity of the code against that accepted spec.

```mermaid
flowchart TD
    CO[Coordinator] -->|XML task| PL[planner]
    PL -->|XML plan| CO
    CO -->|TRIVIAL/SMALL: self-authors plan.md, no planner spawn| CO
    CO -->|XML task + plan| EX[executor]
    EX -->|XML result| CO
    CO -->|XML task + result| VF[verifier]
    VF -->|XML verdict| CO
    CO -->|verdict = fail, iterations left| PL
    CO -->|verdict = fail, iterations left (/acs:code)| EX
    CO -->|verdict = pass| ST[(write state JSON via post-hook)]
```

For `/acs:code` (MAR-71, slice 1b of MAR-69), a failing verdict with
iterations left routes straight back to the **executor** (`EX`), never to
the planner — the plan is authored once, before iteration 1. **The `CO
-->|XML task| PL` edge is itself lane-conditional (MAR-72, ADR-0074):** it
fires only on STANDARD/COMPLEX; on TRIVIAL/SMALL the coordinator instead
takes the self-loop edge above, authoring `plan.md` itself with zero
`code-planner` spawns.

## Coordinator ↔ subagent communication: XML

- All communication between the coordinator and subagents MUST use a defined
  **XML format** — both task assignments (coordinator → subagent) and results
  (subagent → coordinator).
- Messages MUST be **validated against a formal schema (XSD)** shipped with
  the plugin, so malformed messages fail fast instead of silently degrading
  the pipeline.
- The format SHOULD carry, at minimum: ticket id, skill, phase, task
  description, references to workspace input files, and (on the way back)
  status, findings, error details, and output file references.

**[ASSUMPTION]** Illustrative shape — the concrete schema is to be defined
during design:

```xml
<task skill="code" phase="execute" ticket-id="SHOP-123">
  <objective>Implement spec 02-api-endpoints</objective>
  <inputs>
    <file>specs/02-api-endpoints.md</file>
    <file>plan.json</file>
  </inputs>
  <constraints>
    <tdd>true</tdd>
    <coverage-target>90</coverage-target>
  </constraints>
</task>

<result skill="code" phase="execute" ticket-id="SHOP-123" status="completed">
  <outputs>
    <file>code-progress.json</file>
  </outputs>
  <findings>…</findings>
  <errors>…</errors>
  <stop-reason>…</stop-reason>
</result>
```

## File-based state instead of conversation memory

- Subagents MUST write their **states, findings, error details, and stop
  reasons** into JSON files in the workspace folder. Concretely, every phase
  writes its own artifact into `<partition>/phases/<skill>/`: the planner
  `iter-<n>-plan.md` (the complete plan) — except `/acs:code`, whose planner
  writes a single per-ticket `plan.md` (MAR-70), written once per run,
  before the loop (MAR-71, slice 1b of MAR-69) — each executor
  `iter-<n>-execute[-<k>].json` (artifacts produced,
  repo files changed, commands run with outcomes), the verifier
  `iter-<n>-verify.md` (every check with evidence, every finding in detail).
  `/acs:code` additionally persists `phases/code/plan-approval.json` on
  STANDARD/COMPLEX — written by `plan-approval.py`, **not** by a subagent
  (MAR-73, slice 3 of MAR-69). XML results reference these files, never
  inline their bodies.
- **Grounding**: every subagent decision, claim, and finding MUST be traceable
  to a source read or run in that task — cited file/section next to the
  statement, or the quoted command and output. A missing input is an error,
  not a guess; an unverifiable point is an explicit assumption with rationale;
  verifiers treat ungrounded plans/reports as blocking findings.
- Native **plan mode is not used** for the reflection plan phase: planners are
  spawned subagents with no user to give **human/interactive** approval to a
  plan, and resumability comes from the phase artifacts plus gates. This is
  unaffected by `/acs:code`'s deterministic plan-approval record (MAR-73,
  slice 3 of MAR-69) — a machine conformance verdict over the plan's own
  bytes, never an interactive gate. The planner's read-only discipline is
  enforced by its tool allowlist (planners/verifiers: read tools + Write
  solely for their own phase artifact; executors additionally may not spawn
  agents or invoke skills).
- The coordinator MUST persist each phase's output (plan, executor results,
  verifier verdict) to the ticket partition **at the phase boundary**,
  before starting the next phase — a context loss or crash never loses more
  than the in-flight phase
  ([workflow.md](workflow.md#resuming-a-ticket)).
- The coordinator reads these files to decide the next action; it never
  depends on having seen earlier messages.
- This makes every step **resumable** (a crashed or interrupted skill can be
  re-run and continue from recorded state) and **inspectable** (the user can
  audit any step's reasoning trail in the workspace).

## Decomposition & concurrency rules

- Decomposition is **exclusively the coordinator's job**: planner, executor,
  and verifier subagents MUST NOT spawn their own sub-subagents. This keeps
  the state files and the XML message flow predictable.
- The coordinator MAY run **multiple executors in parallel** within one
  skill (e.g. one executor per spec in `/code`), provided their outputs do
  not conflict; the verifier runs after all parallel executors complete and
  judges the combined result.
- The exact XSD is defined during design; the XML shapes in this document
  are illustrative.
