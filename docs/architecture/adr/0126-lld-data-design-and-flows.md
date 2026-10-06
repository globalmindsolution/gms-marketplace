# 0126 — The low-level design is written per feature by `/acs:create-data-design` and `/acs:create-flows`

**Status**: Accepted — amended by [0127](0127-only-create-pr-commits.md) (documents staying local is now every skill's rule; `/acs:create-pr` commits them) and by [0137](0137-docs-sync-keeps-the-feature-lld-current.md) (`/acs:docs-sync` keeps `lld/<feature>/` current after implementation — P7 has landed) · **Date**: 2026-10-04

**Amends**: [0118](0118-discovery-design-development-phases.md) (two of the Design-phase
skills it names now ship), [0120](0120-design-document-catalog-and-ticket-features.md)
(the first readers of `design.lld_types` and of a ticket's `features`).

## Context

ADR-0118 split the design into a product-level HLD, which `/acs:create-architecture`
writes, and a low-level design partitioned by PRD feature under
`lld/<feature>/{api,data,flows,components}/`. ADR-0120 made the LLD document types a
catalog chosen at `/acs:setup` and gave tickets the `features` that name those folders.
Nothing wrote the data or behaviour folders yet: a ticket's entities, schema, flows and
state machines lived, if anywhere, in a one-off `design.md` that no later ticket
updates.

## Decision

1. **`/acs:create-data-design`** writes `lld/<feature>/data/` for a ticket: the logical
   ERD (entities, attributes, keys, cardinalities, DB-agnostic) and the physical schema
   (tables, types, indexes, constraints and a migration *outline*), for the enabled
   `logical-erd` and `physical-schema` types. One designer writes both, because they
   must agree.
2. **`/acs:create-flows`** writes `lld/<feature>/flows/` — one file per flow (its
   sequence diagram and, where the flow branches on business rules, its activity
   diagram) and one per entity state machine — and, only when enabled,
   `lld/<feature>/components/`. The writers run in parallel, one per flow group plus one
   for the state machines and one for the components, with an integration pass only
   when a writer reports a seam (ADR-0125's pattern).
3. Both are **ticket-scoped Design skills** (`PLANNING_SKILLS`, beside
   `/acs:create-design`), run by the SA or Tech Lead before implementation. They write
   **documents only** — never source, migrations or machine-readable contracts — and
   only inside the ticket's feature folders and only the enabled types. Each runs the
   write → judge loop with a gap analyst beside its survey (ADR-0122), versions every
   file through `acs.py design` with its `feature`, and runs its $0 checks beside the
   review (ADR-0125).
4. **Delivery: documents stay local.** Neither skill branches, commits or opens a PR,
   whichever branch is checked out. Each records every path it wrote, repo-relative, in
   its result's `states.files` and ends by listing those files as local changes; the
   user reviews them and commits them, or opens a PR, themselves. No later step commits
   them on the user's behalf: `/acs:analyze-requirements`' publish still commits only
   the ticket's docs folder (ADR-0090 unchanged).

## Consequences

- Skill count +2, six agent files, two hook pairs; the write → judge loops go from nine
  to eleven. No new role: `designer`, `reviewer` and `gap-analyst` already exist.
- `/acs:create-design`'s `design.md` keeps its job until P6 replaces it with
  `create-tech-design`, which will snapshot these documents for the team's review.
- `/acs:docs-sync` does not yet keep `lld/<feature>/` current after implementation
  (P7); until then a change that moves a schema or a flow is re-designed by re-running
  the skill.
