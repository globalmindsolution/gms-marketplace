# 0120 — Design documents are a fixed catalog chosen at setup; tickets name their PRD features

**Status**: Accepted — amended by [0128](0128-requirements-from-any-container.md) (a run's features come from its requirements, ticket or not; a feature slug also names `<prd_dir>/features/<feature>/` and `<development_dir>/<feature>/`) · **Date**: 2026-10-04

**Amends**: [0118](0118-discovery-design-development-phases.md) (gives its
"types chosen at `/acs:setup`" and "LLD partitioned by feature" their contracts).

## Context

ADR-0118 files design documents by level — `hld/` for the product views,
`lld/<feature>/{api,data,flows,components}/` for the detailed ones — and lets a
repo choose which document types it produces. Two things were left without a
contract: the set of types a repo can choose from, and how a ticket says which
`lld/<feature>/` folders it belongs to. Without the first, every Design skill
would invent its own list; without the second, a skill could not know where a
ticket's design goes.

PRD features carry no ids today: they are named, grouped by priority, and
referred to by name from the roadmap.

## Decision

1. **A fixed catalog**, declared once in `acs_lib.design_types` and mirrored
   (under test) by the settings schema:
   - HLD, always written and not a choice: `overview`, `tech-stack`, `cross-cutting`.
   - HLD, default on: `c4-context`, `c4-container`, `c4-component`, `data-model`,
     `integration-map`, `deployment`, `project-structure`; opt-in: `data-flow`,
     `capability-map`.
   - LLD, default on: `api-contract`, `logical-erd`, `physical-schema`,
     `sequence`, `activity`, `state`; opt-in: `component-detail`, `class`.
2. **`design.hld_types` / `design.lld_types`** hold a repo's choice. `/acs:setup`
   asks one multi-select question per kind, and — like every setting — writes
   only a choice that differs from the default, compared in catalog order.
3. **Tickets carry `features`**: the slugs of the PRD features they trace to,
   made by `acs.py slug --text "<PRD feature name>"`. `/acs:create-ticket`
   proposes them, `/acs:analyze-requirements` confirms or corrects them with
   `acs.py ticket save`, and children inherit their epic's. A feature's slug
   names its `lld/<feature>/` folder.

## Consequences

- The Design skills (later changes) read the enabled types and the ticket's
  `features`; nothing reads them yet, so this change alters no behaviour.
- Adding a type is a catalog row plus the skill that writes it; the schema
  test fails until the schema agrees.
- A slug follows its feature's name, so renaming a PRD feature renames its
  slug: the rename has to carry to the `lld/<feature>/` folder and the tickets
  that name it. Stable feature ids in the PRD would remove that, at the cost of
  a PRD format change; it is not taken now.
- Additive: no setting or ticket changes shape, and tracker sync ignores
  `features`.
