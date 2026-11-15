# 0122 — Design documents are versioned, and every Design skill looks for design ↔ code gaps

**Status**: Accepted — amended by [0130](0130-prd-versions-and-set-doc-status.md) (the PRD and roadmap are versioned too; `/acs:set-doc-status` moves a status, recording `status_by`, `status_at` and `status_reason`, all or nothing over several documents) and by [0137](0137-docs-sync-keeps-the-feature-lld-current.md) (`/acs:docs-sync` now runs §1's move to `implemented`: its gap analyst marks a document whose code fully matches, and the coordinator moves it after the review passes) · **Date**: 2026-10-04

**Amends**: [0118](0118-discovery-design-development-phases.md) (the Design phase gains
version control for its documents and a gap analysis beside every design pass) and
[0121](0121-create-architecture-writes-the-hld-only.md) (`/acs:create-architecture`
is the first skill to carry both).

## Context

A system design and the code that implements it drift apart. On an existing repo the
design is reverse-engineered from code that has already moved on; on a running product
every ticket risks a change the design never hears about; and a new design is, by
definition, ahead of the code for as long as it takes to build. A design skill that
rewrites documents without looking at the code repeats whatever drift it inherited, and
a reader cannot tell a planned element from a built one — so the design stops being
trusted, and the pipeline that plans against it plans against fiction.

## Decision

1. **Design versions.** Every HLD and LLD document opens with front matter: `status`
   (`proposed` → `approved` → `implemented`, and `deprecated`), `version` (bumped on each
   change), `tickets` (the tickets that changed it) and, on an LLD document, `feature`.
   It is set only through `acs.py design init|bump|status` (`acs_lib.design_docs`),
   which allows only legal transitions — a status is derived and validated, never just
   asserted. A Design skill writes `proposed` for what it designs ahead of the code and
   `implemented` for what it documents as built; a change re-opens a document as
   `proposed`; approval of the docs-only **design PR** is the team's approval; and
   `/acs:docs-sync` moves a design to `implemented` once its code lands and matches.
   Elements designed but not built are drawn with a dashed `planned` style.
2. **Gap detection.** A read-only `gap-analyst` role (kind `survey`) compares the design
   documents in a skill's scope with the code, sliced by code area, and classifies every
   gap — **unimplemented** (designed, not built), **undocumented** (built, not
   designed), **drifted** (both, disagreeing) — each with a citation on both sides.
   Every Design skill runs its own gap analyst **beside its survey**, in the same
   message, so it costs no wall-clock time. Handling: undocumented → documented as
   built; unimplemented → kept and marked planned; drifted → a question in the skill's
   one grouped ask. An unhandled gap is a blocking review finding.
3. **`/acs:audit-design`**, a read-only skill, runs the same analysis over the whole
   architecture set (or one feature) on demand — for onboarding, before a design
   review, or after a run of tickets — reads each gap against the document's status
   (an unimplemented element is expected in a `proposed` document and a regression in
   an `implemented` one), and offers to ticket the gaps.

## Consequences

- `/acs:create-architecture` gains `create-architecture-gap-analyst`; the LLD Design
  skills and `/acs:create-tech-design` gain their own as they land; `/acs:docs-sync`
  owns the move to `implemented`.
- One more subagent role and two agent files now; each later Design skill adds one.
- Documents written before this change have no front matter: `acs.py design check`
  reports them, the next Design run initialises them, and `/acs:audit-design` lists
  them as `unversioned`.
