# 0146 — A feature PRD's implemented status is derived from its tickets

**Status**: Accepted · **Date**: 2026-10-11

**Amends**: [0130](0130-prd-versions-and-set-doc-status.md) (moving a feature
PRD to `implemented` is no longer a person's assertion alone).

## Context

A feature PRD (ADR-0142) moved to `implemented` when someone ran
`/acs:set-doc-status implemented` on it: nothing checked that the feature had
been built. ADR-0144 made every product ticket name the requirements it
delivers (`<feature>/R<n>`), and ADR-0145 derived a roadmap milestone's
delivery from its tickets. The same links answer "is this feature
implemented?" — by evidence rather than by say-so.

## Decision

1. **Delivery is derived** (`acs_lib.prd_delivery`). A requirement is
   `delivered` when at least one ticket names it and every ticket that does
   is done — `done` in the tickets index, or its id leading a commit subject
   on the default branch (the same evidence the roadmap reads); `in progress`
   once one has started; `planned` while all are open; `uncovered` when none
   names it. A feature is `implemented` when it declares at least one
   requirement and every one is delivered. A later open ticket on a requirement
   — a bug — takes it back out.
2. **`acs.py prd status [--feature F]`** reports each feature's delivery,
   requirement by requirement with the tickets behind it, read-only, and lists
   the approved features now `ready` to mark implemented and the implemented
   ones that `drift`ed.
3. **`acs.py design list`** gives each feature PRD its `delivery`, so
   `/acs:set-doc-status` shows it beside the status and offers `implemented`
   only when delivery says so.
4. **`acs.py design status --set implemented`** refuses a feature PRD whose
   delivery is not `implemented`, naming the open requirements — in code, not
   only in the skill. `--override-delivery` moves it anyway for work delivered
   outside acs tickets, and requires `--reason`, recorded as `status_reason`.
5. **Nothing writes the status by itself.** Delivery is evidence; the move is
   still `/acs:set-doc-status`'s, so a team decides when a feature counts as
   done, and a drifted feature is reported, never silently reopened.

## Consequences

- "Implemented" means the same thing on every feature PRD: its requirements
  shipped through tickets.
- A repo whose features were built before acs, or outside it, marks them with
  `--override-delivery` and a reason, once.
- The LLD's `implemented` is unchanged: `/acs:docs-sync` still moves it when
  its gap analyst finds the code matching (ADR-0137).
