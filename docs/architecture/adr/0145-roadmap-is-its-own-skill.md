# 0145 — The roadmap is its own skill, and its delivery status is derived

**Status**: Accepted · **Date**: 2026-10-11

**Amends**: [0142](0142-prd-hub-and-feature-prds.md) (`roadmap.md` leaves the
PRD doc set `/acs:create-prd` writes).

## Context

`/acs:create-prd` wrote `roadmap.md` beside the PRD hub: milestones mapped to
epics, a Release versions table, every Must-have in some milestone. The hub
author owned both files because they were coupled, so every roadmap change —
a milestone moved a release, an epic minted for it — was a PRD amendment, and
nothing said how far a milestone had been delivered. What a milestone holds
(features) is the PRD's; when it ships and whether it has are not. ADR-0144
gave the means to answer the second question: a product ticket links the
features it delivers, so a milestone's tickets can be found.

## Decision

1. **`/acs:manage-roadmap` owns `roadmap.md`.** A hooked, ticketless product
   skill (like `/acs:create-prd`, ADR-0127): surveyor → author → reviewer,
   max 3 iterations, the document left uncommitted for `/acs:create-pr`. Its
   modes are `create` (no roadmap yet), `amend` (the user names a milestone
   change), `replan` (the PRD moved under the roadmap) and `status`. No PRD,
   no roadmap: the run fails and points at `/acs:create-prd`.
2. **`/acs:create-prd` stops at the PRD.** It writes the hub and the feature
   PRDs only; a run that adds, cuts or re-prioritises a feature points the
   user at `/acs:manage-roadmap`. Its floor passes no `--roadmap`, so
   `prd_conformance_check.py`'s `roadmap-outline` family runs only for the
   roadmap skill.
3. **One shape, one floor.** A milestone is a `###` heading ending in its
   release version, with `Status`, `Features` (links to feature PRDs), `Epics`
   (ids or `none yet`) and an optional user-given `Target`; the Release
   versions table has one row per milestone. `roadmap_check.py` enforces it
   against the hub's index: every Must-have scheduled, no Won't-have, every
   linked feature PRD real, every milestone mapped to exactly one version.
4. **Delivery status is derived, never asserted.** `acs.py roadmap status`
   reads the tickets each milestone tracks — its epics, and every ticket whose
   `features` name one of its features — from the tickets index and the
   ticket ids leading commit subjects on the default branch: `delivered` when
   every tracked ticket is done, `in progress` when any has started, `planned`
   otherwise. `--write` rewrites only the Status lines and cells.
5. **A status refresh is not a version.** A change to the plan is one
   `acs.py design bump`; a run whose only change is the derived status moves
   no front matter, because the status is a reading of the tickets, not a
   decision about the plan.

## Consequences

- The roadmap can follow the PRD at its own pace: a cut feature leaves a
  `wont-scheduled` finding the roadmap skill's replan resolves, and a merged
  epic shows up as `delivered` on the next status refresh.
- `/acs:release` still never reads the roadmap to resolve tickets; the table
  is for readers.
- A feature PRD's own `implemented` status is not derived yet; the same
  ticket links make it derivable.
