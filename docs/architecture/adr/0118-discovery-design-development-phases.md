# 0118 — Discovery, Design, Development: three phases, and the project and requirements skills go

**Status**: Accepted — amended by [0124](0124-remove-create-docs.md) (`/acs:create-docs` leaves the Design phase; the principles and standards are hand-written) and [0129](0129-discovery-design-development-regroup.md) (Discovery is `create-prd` and `analyze-requirements`; `create-ticket` moves to Utility) · **Date**: 2026-10-04

**Supersedes**: [0091](0091-design-phase-entry-point-fold.md) (the `/acs:project`
fold and its auto-detected mode), [0048](0048-standardize-project-scaffolds-e2e-no-branch-protection.md)
(standardize-project's e2e scaffold), [0061](0061-create-requirements-brownfield-reverse-engineer-producer.md)
and [0062](0062-create-requirements-greenfield-elicitation-draft-discipline.md)
(`/acs:create-requirements`).

**Amends**: [0109](0109-subagents-per-skill-logic-and-no-skill-manifest.md) (the
`auditor`, `scaffolder`, `build-checker` and `additive-checker` roles go with
their skills; `SKILL_LEGS` keeps only `code`'s four delivery paths).

## Context

The skills that run before `/acs:ship` were grouped as one "Design" phase that
mixed four different jobs: defining the product (`create-prd`,
`create-requirements`), ticketing (`create-ticket`), designing (`create-architecture`,
`create-design`) and setting up the repository (`/acs:project` with its
`create-project` and `standardize-project` legs, and `create-docs`). An audit of
that phase found ~5,400 lines of SKILL.md and ~4,100 of agent prompts, much of it
repeated across skills.

Three of those skills did work that acs already does elsewhere:

- **`/acs:project` → `create-project`** scaffolded a greenfield repository once.
  A scaffold is ordinary ticket work: it can be ticketed and shipped like any
  other change, with the plan, review and PR that brings.
- **`/acs:project` → `standardize-project`** audited an existing repository and
  added missing tooling. `/acs:setup` installs the CI gates and the e2e workflow
  and runner templates; `/acs:create-docs` writes the principles and standards
  sets; anything structural it found was only ever a recommended follow-up ticket.
- **`/acs:create-requirements`** produced a `requirements/` doc set between the
  PRD and a ticket. The PRD carries the product's features and NFRs, and
  `/acs:analyze-requirements` pins each ticket's acceptance criteria; the middle
  layer duplicated both.

## Decision

1. **Three phases.** The skills group as **Discovery** (what to build:
   `create-prd`, `create-ticket`, and a `breakdown-ticket` that splits an epic or
   a large story), **Design** (how to build it: `create-architecture` for the
   product HLD; `create-api-contract`, `create-data-design` and `create-flows` for
   the low-level design; `create-tech-design` assembles them for the team's
   review before implementation) and **Development** (everything `/acs:ship`
   drives, plus `merge-pr`). `create-docs` and the setup/update/release/handoff
   commands are Utility. The grouping is a reader's aid, as before — the code
   knows skills, not phases.
2. **Documents by level.** `docs/architecture/hld/` holds the high-level views
   (C4, the conceptual ERD, the API landscape …), owned by `create-architecture`.
   `docs/architecture/lld/{api,data,flows,components}/` holds the detailed
   documents, one subfolder per owning skill. Which HLD and LLD types a repo
   produces is chosen at `/acs:setup`.
3. **Removed now:** `/acs:project`, `create-project`, `standardize-project` and
   `create-requirements` — their skills, agents, hooks, eval cases and tests, and
   the `project_mode` detector and `classify_additive_diff` helper only they used.
   A greenfield repository is scaffolded by `/acs:create-ticket "Scaffold the
   repository per the architecture docs"` and `/acs:ship`.
4. **Landed in later changes**, each with its own ADR: the doc-type settings
   and setup step; `create-architecture` writing HLD only; the new LLD skills;
   `create-api-contract` moving out of `ship.yaml` into Design;
   `create-design` becoming `create-tech-design`; `docs-sync` keeping `lld/`
   current; and `breakdown-ticket` replacing `create-ticket --fan-out`.

## Consequences

- 29 skills become 25 (hooked 19 → 16, unhooked 6 → 5, legs 6 → 4) and 33 agent
  files become 25.
- **Breaking.** A consumer with an open scaffold, standardization or requirements
  PR merges or closes it by hand (`gh pr merge`) before upgrading: `/acs:merge-pr`
  no longer reads those skills' step state. A repo's existing `requirements/` set
  stays readable context for the skills that used it.
- Old clarification ledgers that name the removed skills still validate: the
  ledger schema keeps retired skill names, as it already does for `create-spec`.
- `hld/project-structure.md` stays: `create-architecture` writes it and other
  skills read it.
