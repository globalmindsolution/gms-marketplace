# 0109 — Subagents follow each skill's logic, and a skill carries no manifest

**Status**: Accepted — amended by [0118](0118-discovery-design-development-phases.md) (the project and requirements skills' roles are gone; `SKILL_LEGS` holds only `code`'s legs) · **Date**: 2026-09-27

**Amends**: [0092](0092-skill-machinery-declared-per-skill.md) (class D's
"executor + verifier" shape is replaced by roles named for each skill's own
work, and class C's single executor goes inline),
[0096](0096-workflow-is-a-list-not-a-graph.md) (the list still decides order
and membership; the order is no longer validated against per-skill reads and
writes, because those declarations are gone),
[0101](0101-gating-skills-that-are-not-workflow-steps.md) (the brakes and the
`SUBJECT_GATES` table stand; the generic input gate beside them is removed)

## Context

ADR-0092 stopped the planner/executor/verifier trio from being the default and
declared the machinery per skill. What it declared, though, was the same shape
fourteen times: every authoring skill got an `acs:<skill>-executor` and an
`acs:<skill>-verifier`, and every SKILL.md ran an "execute → verify, no
planner" loop. Those names described the loop's plumbing, not the skill's work.
`create-prd`'s executor ran two different jobs, a read-only survey that ends in
questions and a write pass after the answers. `standardize-project`'s did the
same with an audit and an additive scaffold. `create-impl-plan`'s executor was
a planner in everything but name. The three apply skills (`create-ticket`,
`create-pr`, `merge-pr`) still spawned an executor for a sequence of commands
that nothing independent reviews.

Beside each skill sat `skills/<name>/acs.yaml`, declaring its `phase`,
`leg_of`, and the artifacts it `reads` and `writes`. Two enforcers read it:
`acs workflow validate` refused a `ship.yaml` whose step read an artifact that
no earlier step wrote, and the pre-hook's generic input gate refused (under a
workflow) or warned (standalone) when a required read was absent. That made a
skill's independence depend on a declaration it did not need. Every skill
already falls back to the run's subject (the ticket's acceptance criteria, the
prompt or the document) when an upstream artifact is missing. The workflow
exists to keep the order of the skills, not to make them strict.

## Decision

**1 · Subagents are named for what the skill does, and a skill owns only the
roles its logic needs.** Each role has a kind the hooks act on
(`acs_lib.skills.ROLE_KINDS`): `survey` (read-only on the repo, records notes
and questions), `write` (produces the deliverable; the executor file-map guard
applies while it runs), or `judge` (read-only, re-derives and judges fresh).

| Skill | Subagents |
|---|---|
| analyze-requirements | analyst · impact-reviewer |
| create-prd, create-requirements | surveyor · author · reviewer |
| create-architecture | architect · reviewer |
| create-design | designer · design-reviewer |
| create-docs | author · reviewer (one pair per doc set) |
| create-impl-plan | planner · plan-reviewer |
| create-api-contract | contract-author · contract-reviewer |
| create-test-docs | test-designer · trace-reviewer |
| code (and its four legs) | implementer (one per file-map partition) |
| review-code | lens · adjudicator (unchanged) |
| create-e2e-tests | test-writer · suite-runner |
| docs-sync | doc-updater · drift-reviewer |
| create-project | scaffolder · build-checker |
| standardize-project | auditor · scaffolder · additive-checker |
| create-ticket, create-pr, merge-pr | none: the coordinator runs the steps inline from `references/` |

Where a former executor ran two jobs, the jobs are now two roles: the
surveyor and the auditor run on iteration 1 only and freeze their notes, and
the author or scaffolder writes from them.

**2 · The phase is the role.** A task and its result carry `phase="<role>"`,
the SubagentStop snapshot is `iter-<n>/<role>-message.xml`, and each agent's
report is `iter-<n>/<role>.json` (`.md` for a judge). The model tier comes
from the kind (`survey` → `planner`, `write` → `executor`, `judge` →
`verifier`, and create-impl-plan's `planner` → `planner`), so `settings.models`
keeps its three keys and a new role needs no new setting.

**3 · No per-skill manifest.** `skills/<name>/acs.yaml` and
`schemas/acs-skill.schema.json` are deleted. A skill is its `SKILL.md`; its
agents are found by the `agents/<skill>-<role>.md` naming convention; the legs
are one table, `acs_lib.skills.SKILL_LEGS`.

**4 · The workflow only orders skills.** `acs workflow validate` checks that
every step is a skill that ships and not another skill's leg, and that every
loop goes back. It no longer derives an order from reads and writes, and the
pre-hook no longer gates inputs. It keeps the invariants, the safety brakes,
`SUBJECT_GATES` and the evidenced no-op.

## Consequences

- A skill invoked on its own and the same skill invoked by `/acs:ship` pass
  the same gate. An out-of-order `ship.yaml` override validates, and its
  steps run on their fallbacks.
- The prose is longer where a role split in two (a surveyor or auditor file
  beside the author or scaffolder). Each file now does one job.
- `acs_lib.lifecycle.parse_agent_type` no longer splits on the last hyphen.
  Role names contain hyphens (`plan-reviewer`), so it matches the longest
  shipped skill name as a prefix.
- A run started before this change keeps its `execute.json` reports.
  `derive` reads `implementer*.json` and still accepts `execute*.json`.
