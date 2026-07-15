# 0061 — `/acs:create-requirements` brownfield reverse-engineer producer

**Status**: Accepted · **Date**: 2026-07-15

## Context

G37 needs a bootstrap path for the `requirements/` doc set (MAR-145's
functional/non-functional model, ADR 0060) on a repo that already has real
code but no — or only a sparse — requirements set. The output is
behavioral-requirements PROSE per feature area, inherently LLM-driven (like
`/acs:create-prd`'s and `/acs:create-architecture`'s brownfield modes), so
the extraction mechanism (Decision A) and the feature-area enumeration
strategy (Decision C) both need settling before the skill can be built.

## Decision A1 — extraction mechanism: mirror create-prd's brownfield producer triad

**Selected.** The planner surveys code + the architecture doc set + any
existing requirements and produces the feature-area inventory, a per-area
requirement outline, and open points; the coordinator resolves open points
via the clarify ledger (interactive-confirm) BEFORE the executor writes; the
executor writes `<functional_subdir>/<feature>.md` /
`<non_functional_subdir>/<item>.md` as DRAFT, code-cited; the verifier
checks coverage / citation / structure / routing / no-fabrication.

Rejected alternatives:

- **A2 — deterministic scaffold then LLM-fill.** A stdlib helper enumerates
  areas and emits empty section skeletons, then the triad fills them.
  Rejected — a deterministic "feature area" detector is a genuine research
  project (route-group / CLI / package heuristics per language) and a new
  runtime component fighting the stdlib-only / no-new-dependency
  constraint; empty skeletons invite invented content, cutting directly
  against C-22's no-fabrication rule. Its enumeration idea survives as
  Decision C1's fallback inventory (done by the planner, not a helper).
- **A3 — fully-autonomous single-pass draft (no interactive-confirm).**
  Rejected — violates the settled product shape (full-codebase
  interactive-confirm, MAR-140 C-1..C-4) and C-22/C-5 ("acs never
  auto-authors an authoritative contract without opt-in").

## Decision C1 — feature-area enumeration: architecture-aware with graceful degradation

**Selected.** When a `docs/architecture` doc set exists, the planner
enumerates feature areas from the `c4-container.md` / `c4-component.md` /
`project-structure.md` views (each top-level container/component/module
they name is a candidate feature area); when absent it degrades to a
**codebase inventory** — top-level modules / route-groups / CLI surfaces /
packages read directly from the repo tree. The gate itself stays
**standalone** (`gate_create_requirements` returns `None`, like
`gate_create_prd`) — architecture-awareness is a planner BEHAVIOR, never a
hard `_require_architecture_doc_set`-style gate. The checkable definition:
a feature area is a top-level module / route-group / CLI surface / package
that the architecture container-component view names, or — absent an
architecture set — that the codebase inventory identifies. Both the planner
and the verifier carry this definition verbatim so the verifier can
independently re-derive the same set and diff against it, making the ≥90%
coverage / 0-silent-omission metric checkable rather than a subjective
judgment.

Rejected alternatives:

- **C2 — codebase-inventory only.** Rejected — ignores the architecture doc
  set even when present, producing a worse decomposition and breaking the
  "architecture-aware" requirement.
- **C3 — require an architecture doc set.** Rejected — would force
  `_require_architecture_doc_set`-style hard gating, breaking the
  standalone (no hard PRD/architecture dependency) requirement.

## Consequences

- The extraction "engine" is coordinator + agent-charter PROSE (mirrors
  `create-prd`'s brownfield mode), not a compiled algorithm — no new stdlib
  helper ships with this decision.
- Every extracted requirement is DRAFT / human-confirm-required and
  code-cited; an ungroundable area is surfaced as an `[OPEN]` point, never
  invented (C-22) — enforced by the verifier's coverage, citation, and
  no-fabrication dimensions.
- Requirements stays a **living contract** alongside the verified
  conformance chain (`PRD → architecture → principles → standards → design
  → specs → code`) — this ADR adds no requirements-conformance verifier
  dimension to `/acs:create-spec` or `/acs:code`, and does not touch the
  chain line in `docs/architecture/lld/contracts.md` (Decision D1, ADR
  0060).
- **ADR numbering deviation, recorded not silenced.** `design.md` (line
  488) and this ticket's own AC-7 text originally reserved **ADR 0058** for
  this decision. By implementation time MAR-145 had shipped and taken
  **0060** (confirmed via `git ls-tree origin/main docs/adr/`, topping at
  `0060-functional-non-functional-requirements-model.md`), leaving 0058 and
  0059 as unused gaps below the new high-water mark. This ADR uses the
  next-free-**above-max** id, **0061**, to keep ADR numbering
  chronologically monotonic rather than backfilling the 0058 gap out of
  order; 0058 and 0059 are deliberately left unused.
