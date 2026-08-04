# 0012 — Design-time doc-consistency: gap & staleness analysis in the design skills

**Status**: Accepted · **Date**: 2026-06-14

## Context

acs maintains a graph of doc sets — `product → architecture →
{design → spec → code → requirements}`, plus `quality` and `operations`
([ADR 0011](0011-sdlc-doc-sets-quality-and-operations.md), conformance direction
in [docs/README](../README.md)). Each set is produced by a skill. A change to any
doc can **stale** its dependents or leave **coverage gaps**, and the more sets
there are, the wider that drift surface.

The skills already check their *own immediate* conformance (specs → design,
features → goals) and are charged with "updating all affected documentation."
What's missing is detecting cross-set drift **early — while the user is doing
design work**, not after. Detached mechanisms for this were considered and
rejected (see below): they decouple detection from the design moment and add
surface.

## Decision

Make doc-consistency a **built-in step of the design-producing skills**:
`/create-prd`, `/create-architecture`, `/create-design`, `/create-spec`, and the
new `/create-quality` and `/create-operations`. Add a **shared analysis step to
their planner phase** (the same way the grounding section is shared across
agents):

1. **Read the related slice of the doc graph** — the upstream sets the skill
   derives from and the downstream sets that derive from it — using the existing
   trace links (features → goals, specs → design → architecture, …) and the
   conformance direction.
2. **Detect gaps** (missing required edges: orphan goal, uncovered feature,
   undesigned ticket, architecture component with no quality/operations
   coverage) and **staleness** (downstream that no longer conforms to the
   upstream it traces to).
3. **Surface findings + recommended adjustments to the user in-session**, through
   the existing clarification-ledger / findings mechanism, *before/while*
   producing output — e.g. "amending G3 leaves `architecture/overview` and
   `quality/strategy` stale; recommend updating sections X, Y."
4. The user decides; the skill then **updates the affected docs as part of the
   same change** and its verifier confirms the result is consistent.

No new skill, no CI check, no pre-commit hook — detection rides the design skills
the user already runs.

## Alternatives considered

- **A dedicated `/acs:doctor` command** — *rejected*: decouples detection from
  the design moment and relies on the user remembering to run it; extra surface.
- **A `docs/` pre-commit hook + CI gate** — *rejected*: catches drift only at
  commit/PR, *after* the design decision is made; cheap link-checking is narrow
  (it resolves references but misses semantic gaps); adds tooling.
- **A periodic audit** — *rejected as the primary detector*: too late by
  definition, which was the explicit concern.
- **Provenance fingerprints / manifests** (hash each upstream source to make
  staleness a pure diff) — *deferred*: useful precision, but a separate system;
  the planner can reason over the existing trace links for now, and we revisit
  if agentic detection proves unreliable.

## Consequences

- Each design skill's **planner** (and planner-agent prompt) gains the shared
  consistency-analysis step; the **executor** applies chosen adjustments; the
  **verifier** checks the affected docs end consistent. Completion-report
  findings gain a gaps/staleness section.
- Detection happens **at design time, in the same session** as the change — the
  earliest practical point — with no separate command, gate, or schedule.
- Detection power scales with **trace-link quality**; weak/missing links reduce
  it — a standing incentive to keep traces current (which the skills already
  enforce). Provenance fingerprints remain a future upgrade if needed.
- [`/acs:test`](0011-sdlc-doc-sets-quality-and-operations.md) is unaffected — it
  stays the QA/regression runner, not a doc tool.

## Amendment — MAR-156

**Date**: 2026-07-29 · **Status**: Accepted (stale-reference note)

`/acs:create-spec` is deleted outright (ADR 0066): the design-producing
skill list in the Decision above drops `/create-spec`, leaving
`/create-prd`, `/create-architecture`, `/create-design`, `/create-quality`,
and `/create-operations`. Its shared doc-consistency planner step migrates
with the deletion — there is no separate create-spec plan phase left to
carry it. This amendment does not add any new participant to the list.

## Amendment — MAR-160

**Date**: 2026-07-30 · **Status**: Accepted (non-participant note)

A new hooked skill, `/acs:docs-sync`, lands running AFTER `/acs:code` (and
the post-code `/acs:test` step, when it ran) and BEFORE `/acs:create-pr` —
not during design. Its planner/executor/verifier re-derive doc impact from
`git diff <default_branch>...HEAD`, `/code`'s `result.json`, and the final
code-verify artifact — a changeset-diff-grounded re-check, not the
design-time gap/staleness analysis this ADR's Decision describes (upstream
trace links, in-session findings during design work). `/acs:docs-sync` is
therefore **not** added to the design-producing skill list above: it is a
post-implementation doc-sync re-check, not a design-time doc-consistency
participant. This amendment does not add any new participant to the list.

## Amendment — MAR-164

**Date**: 2026-08-04 · **Status**: Accepted (bounded touched-area participant)

`/acs:code` (specifically `code-planner.md`'s charter item 4) joins as a
**bounded, touched-area, post-plan participant** — explicitly distinguished
from the full design-producing-skill participation the Decision above
(`:21-45`) describes. It is **not** added to that participant list; this is
a narrower, separately-scoped addition running alongside it, at plan time in
the delivery lane rather than at design time.

**The true residual, stated exactly**: trace-link gap detection for
`needs_design: false` tickets — the population that never runs
`/acs:create-design` and so never receives the full step above.
`needs_design: true` tickets continue to receive the full ADR-0012 step at
`/acs:create-design` (`create-design-planner.md:62-102`); this amendment
changes nothing about that path.

`code-planner.md`'s item 4 detects four bounded doc-graph edges (E1-E4) for
the touched area only, riding the SAME `problems` carrier the item's
existing Boy-scout drift item already uses into the execute report and
`/acs:docs-sync`:

- **E1** a touched/added component has no entry in
  `<architecture_path>/hld/c4-component.md`.
- **E2** a touched/added persisted entity or state shape has no row in
  `<architecture_path>/hld/data-model.md`.
- **E3** a touched/added runtime flow has no sequence diagram under
  `<architecture_path>/lld/flows/`.
- **E4** a user-visible capability the change delivers has no PRD goal or
  roadmap row to trace to in `docs/product/prd.md` / `docs/product/roadmap.md`.

These four edges are the only doc-graph gaps this bounded participation
detects. `requirements_path` edges and `adr_path` edges are explicitly
**not** covered by it — they remain the responsibility of
`/acs:create-design`'s full ADR-0012 step (for `needs_design: true`
tickets) and `/acs:docs-sync`'s independent, changeset-diff-grounded
re-derivation, which — per this ADR's own `## Amendment — MAR-160` above —
runs after `/acs:code` and `/acs:test`, before `/acs:create-pr`, and is
already established there as a distinct, later-timed check from the
design-time analysis this Decision describes. This amendment adds no new
question type, no new `problems` field, and no new lifecycle.

**Reconciling DR-2**: the Decision's participant list (`:21-45`) still names
the pre-MAR-156 count. Today, **8** planner agents actually carry the
canonical `### Design-time doc-consistency step (ADR 0012)` block:
`create-prd-planner`, `create-architecture-planner`, `create-design-planner`,
`create-quality-planner`, `create-operations-planner`,
`create-principles-planner`, `create-standards-planner`, and
`create-requirements-planner`. `code-planner.md` is **not** one of the 8 —
it carries the extended Boy-scout bullet above, not the canonical block, and
this amendment does not add it to that carrier list.
