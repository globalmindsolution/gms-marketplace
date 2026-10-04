# 0121 — `/acs:create-architecture` writes the high-level design only

**Status**: Accepted · **Date**: 2026-10-04

**Amends**: [0118](0118-discovery-design-development-phases.md) (its "`create-architecture`
becomes HLD-only" lands here), [0084](0084-create-architecture-design-requirements-remediation-loop-execute-verify-only.md)
and [0110](0110-parallel-fan-out-and-parallel-groups.md) (create-architecture's write
pass and integration pass, below).

## Context

`/acs:create-architecture` wrote the whole architecture set: the HLD plus
`lld/flows/<flow>.md` sequence diagrams and `lld/contracts.md`. ADR-0118 moves the
low-level design to the Design skills, per ticket, under `lld/<feature>/`, and
ADR-0120 lets a repo choose its HLD document types. Keeping the LLD here would leave
two writers for the same documents.

The LLD was also why the write pass fanned out (one HLD writer plus up to three
flow writers) and why an integration pass then reconciled their seams — HLD
component names against flow participants, the overview's links to flows, contracts
against flows. Without the LLD, the HLD is about ten small files that all name the
same containers and components.

## Decision

1. The skill writes only `hld/`: always `overview.md`, `tech-stack.md` and the new
   `cross-cutting.md` (the API and data conventions, event envelope, security,
   observability and configuration every feature's low-level design follows), plus
   one file per enabled `design.hld_types` entry — including the new
   `integration-map.md` (the API landscape), on by default. It never creates or
   changes anything under `lld/`; on a re-run, a file for a type no longer enabled is
   left as it is.
2. One write architect writes the whole HLD. The write slices, their file
   partition and the integration pass are removed; the survey stays sliced over
   repo areas, the write architect still synthesizes contradicting survey notes,
   and the review stays sliced by dimension.
3. The reviewer drops `hld-lld-consistency`; `internal-consistency` now holds every
   HLD file to the C4 views' vocabulary. Ten dimensions remain.
4. The flow-list question goes: the survey asks only the open points the evidence
   cannot settle.

## Consequences

- **Breaking** for a repo that relied on the skill to bootstrap or regenerate
  `lld/flows/` and `lld/contracts.md`. Existing files stay where they are and
  `docs-sync` keeps maintaining them; new low-level design comes from the Design
  skills once they land (ADR-0118's later phases).
- Fewer subagent spawns per run (one writer instead of two to four plus an
  integration architect) and a shorter skill.
- `states.architecture` in the result document carries `hld` only.
