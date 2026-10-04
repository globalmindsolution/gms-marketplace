# 0119 — ADRs live under `docs/architecture/adr/`

**Status**: Accepted · **Date**: 2026-10-04

**Amends**: [0118](0118-discovery-design-development-phases.md) (the documents-by-level
layout gains the decision records).

## Context

ADR-0118 files the design documents by level under `docs/architecture/`: `hld/` for
the product views and `lld/<feature>/` for the detailed ones. The architecture
decision records sat beside that tree at `docs/adr/`, so the reasons for a design
lived one folder away from the design itself, and a repo's architecture set could
not be handed over, reviewed or owned as one tree.

acs finds a repo's documents rather than reading configured paths (ADR-0102), so
where an existing repo keeps its ADRs is the repo's business. Only the folder acs
creates when a repo has none is acs's choice.

## Decision

1. **This repository's ADRs move** to `docs/architecture/adr/`, numbering and file
   names unchanged. Links are re-pointed; no decision text is edited.
2. **A repo's first ADR folder** is created at `docs/architecture/adr/` (it was
   `docs/adr/`) by the skills that write decision records (`/acs:create-design`,
   and `/acs:docs-sync` when it records one).
3. **An existing ADR folder is still found where it is**: a consumer with
   `docs/adr/` keeps it, and nothing migrates it.

## Consequences

- `docs/architecture/` is the whole design record: `hld/`, `lld/` and `adr/`.
  `/acs:docs-sync` already classifies `adr_dir` separately from the rest of
  `architecture_dir`, so an ADR folder nested inside it needs no rule change.
- Not breaking: no setting changes and no consumer file moves.
