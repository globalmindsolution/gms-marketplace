# HLD — Overview

> Living architecture doc set for the **GMS Marketplace** — a curated plugin
> catalog for Claude Code (dogfooding: this repo is itself a consumer of acs,
> the marketplace's plugin).
> Bootstrapped from the implemented system; kept current by the pipeline per
> the living-architecture rules in `docs/requirements/functional/workflow.md`. All
> diagrams are Mermaid.

## System context

The GMS Marketplace is a curated plugin catalog distributed from this
repository. It is built to host plugins of differing shapes (ADR 0021); one
is published today:

- **acs** (full-shape: `.acs/`, schemas, hooks, agents, skills) — targets
  **Claude Code**; drives an agentic software-delivery workflow on any
  **consumer repository**, persisting all pipeline state into a gitignored
  **`.acs/state-machine/` folder inside that repo**, anchored to the repo's
  main checkout so every linked worktree resolves to the same on-disk state
  (no setting overrides it; ADR-0086,
  [ADR-0102](../adr/0102-documents-are-found-not-configured.md)).

## Quality attributes (drive the design)

| Attribute | Architectural answer |
|-----------|----------------------|
| Enforceable ordering | Deterministic gate scripts on the `PreToolUse(Skill)` event; exit 2 blocks; gates fail closed. |
| Resumability | File-based state only: append-only run history, phase artifacts, pipeline ledger; no conversation memory between steps. |
| Verification independence | Separate writer and judge contexts on the nine authoring skills, each named for the skill's own work (ADR 0109): analyze-requirements (analyst / impact-analyst / impact-reviewer), create-prd (surveyor / author / reviewer), create-architecture (architect / reviewer, with a gap-analyst beside its survey, ADR-0122), create-design (designer / design-reviewer), create-impl-plan (planner / plan-reviewer), create-api-contract (contract-author / contract-reviewer), create-test-docs (test-designer / trace-reviewer), create-e2e-tests (test-writer / suite-runner), docs-sync (doc-updater / drift-reviewer) — no skill has a planning pass before its writer (ADR 0092); `code`'s implementers are judged by `/acs:review-code`'s lenses and adjudicators, a step of its own (ADR 0099). Judges anchor on gated upstream contracts and the authoring notes, and re-run all cheap checks. Apply-work skills (create-ticket, create-pr, merge-pr) run inline with no subagent and are gated upstream by `/acs:review-code`. The read-only `/acs:audit-design` judges nothing it wrote: its gap analysts compare the architecture set with the code and report every gap, cited on both sides (ADR-0122). The read-only `/acs:audit-security` keeps its judges apart from its surveyors: one fresh-context adjudicator per candidate finding, seeing neither the other findings nor which auditor raised it, tries to refute it and defaults to refuted when uncertain (ADR-0123). |
| Parallelism | Workspace partitioned by repo → ticket; per-checkout pointers; re-entrant per-checkout locks; worktree-per-ticket. Inside a step, a coordinator fans a role out over disjoint slices — writers by default, judges at five or more check dimensions, surveys over disjoint repo areas — at most `parallel.max_agents` (default 4) instances per message, waves beyond it, joined deterministically by `acs.py notes merge` and reconciled by an integration pass (ADR-0110, ADR-0125); a long deterministic command (a build, a suite) runs beside those agents as an `acs.py job` (ADR-0125). The ship pipeline runs one stage at a time: `ship.yaml` v3 carries no `max_parallel` (ADR-0096), and steps overlap only in a parallel group the list declares — the shipped one is `[create-e2e-tests, docs-sync]` — whose members `/acs:ship` drives in lockstep inside its own session (ADR-0110). |
| Portability | stdlib-only Python ≥ 3.9 hooks; markdown skills/agents; no pip installs on consumer machines. |
| Auditability | Pretty-printed JSON everywhere; archives never deleted; clarification ledger; an append-only invocation history per step. |

## Key architectural decisions

1. **Two-layer split**: everything deterministic (gating, ids, locks, state
   writes, validation) lives in Python scripts; everything judgment-shaped
   (analysis, authoring, review) lives in prompts (skills/agents). The prose
   layer is forced to leave deterministic footprints the script layer gates on.
2. **The run is the only inter-step channel** — coordinators are stateless
   between steps; `/ship`'s context can be cleared at any boundary. Two state
   machines, separate on purpose: `run.json` for the run and
   `steps/<skill>/state.json` for each step, with the cursor DERIVED from them
   rather than stored beside them (ADR-0097).
3. **Conformance chain** PRD → architecture → principles → standards → design → code, each level verified against the one above by a fresh context.
4. **Fail-safe prose**: a skill that forgets its post-hook leaves its last
   invocation `in_progress` — which is not `completed`, so the derived cursor
   is still on that step; nothing unlocks by omission.
5. **Complexity-adaptive delivery, review-as-gate**: each change is judged
   onto one of four DELIVERY PATHS (`trivial`, `small`, `standard`, `complex`)
   — once, by `/acs:create-impl-plan`, from the plan's own scope, and recorded
   in the plan's `## Contract` block, which is its only home (ADR-0095 as
   amended by ADR-0098). `/code` is a dispatcher over four legs, one per path.
   **The review is a step, not a phase inside `/code`** (ADR-0099): every path
   gets `/acs:review-code`'s five lenses, per-finding adjudication and final
   gate, and the iteration ceiling is the workflow's one `loops:` entry rather
   than a per-leg property. What the path still scales is the implementer shape
   and whether plan approval is enforced. Spec content is authored inside
   `/create-impl-plan`'s plan when the run's `specs/` is absent or empty
   (pre-existing specs are still read when present). The path never moves
   mid-run: this replaces the `size` × `stakes` axes, the lane
   `derive_lane()` derived from them, the upward mid-flight escalation and the
   user-confirmed de-escalation that balanced it. What catches a wrong
   judgement is the review's path-audit lens, whose remedy is a replan, not a
   re-route.
6. **Entry-point folds over skill collapses**: where several skills form one
   user-facing job, the surface is narrowed by declaring an entry point, not by
   merging the skills. The **legs** are one table in the plugin's code,
   `acs_lib.skills.SKILL_LEGS` (ADR 0109) — there is no per-skill manifest —
   and each leg's SKILL.md names the entry point that owns it (four legs today:
   the delivery paths behind `/acs:code`; ADR 0118 removed `/acs:project` and
   its two project-scaffold legs), and
   the entry point invokes a leg as a genuine Skill-tool call. A code leg runs
   under `code`'s own gate, hooks and implementer (ADR 0095). The consequence
   that matters architecturally: a narrower surface costs no verification
   independence and no gate integrity, because no gate moved.

## Document map

- `c4-context.md`, `c4-container.md`, `c4-component.md` — C4 levels 1–3.
- `data-model.md` — workspace state entities (ER).
- `deployment.md` — distribution & runtime topology.
- `tech-stack.md` — languages, formats, conventions.
- `../lld/flows/*.md` — sequence diagrams for the key runtime flows.
- `../lld/contracts.md` — interface contracts between components.
