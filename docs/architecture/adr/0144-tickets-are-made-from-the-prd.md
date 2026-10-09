# 0144 — Tickets are made from the PRD and link it

**Status**: Accepted · **Date**: 2026-10-09

**Amends**: [0120](0120-design-document-catalog-and-ticket-features.md) (a ticket's `features` become
required for a ticket `/acs:create-ticket` or `/acs:breakdown-ticket` mints,
and gain `requirements`) and [0138](0138-breakdown-ticket-and-typed-ticket-authors.md)
(the typed authors and the reviewer judge the PRD link; children carry it).

## Context

`/acs:create-ticket` read the PRD when one existed and traced a ticket to it
when it could: `prd_trace.feature` was `null` without a PRD, and a request
beyond the PRD was minted once the user confirmed a "divergence". So a backlog
could grow ahead of the product definition, and nothing linked a ticket to the
requirement it delivers — which is what any later question needs, from "what
does this ticket deliver" to "is this feature implemented". Since ADR-0142 each
feature has its own PRD with stable requirement ids (`R<n>`), so a precise link
is possible.

## Decision

1. **No PRD, no ticket.** `/acs:create-ticket` and `/acs:breakdown-ticket`
   refuse at their pre-gate in a repo with no PRD, pointing at
   `/acs:create-prd`. Breakdown also refuses a parent that links no feature.
2. **Every ticket links the PRD.** A ticket carries `features` (at least one
   feature slug, whose own PRD exists and is not `deprecated`) and
   `requirements` (`<slug>/R<n>`, each a requirement its feature's PRD
   declares). A story names at least one requirement; an epic, a task or a bug
   names the ones it delivers or fixes. `acs_lib.prd_link` holds the rule.
3. **Work beyond the PRD is not minted.** The run ends `failed` and points at a
   PRD amendment; the ticket is created from the amended PRD.
   `prd_trace.divergence` stays in the result schema and is always `null`.
4. **Enforced in code, at three points.** `acs.py ticket link-check` judges a
   draft (the authors and the reviewer run it); `post-create-ticket` refuses a
   completed run whose ticket does not link the PRD; `new-ticket.py
   --require-prd-link`, which `/acs:breakdown-ticket` passes for each child,
   refuses before an id is spent. `acs.py ticket save` refuses a
   `requirements` patch that does not resolve, whoever sends it.
5. **The id allocator stays neutral.** Without `--require-prd-link`,
   `new-ticket.py` mints as before — the regression bug `/acs:run-e2e-tests`
   files for a red suite needs no PRD link — but a requirement it is given
   must still resolve.

## Consequences

- A ticket says which requirements it delivers, so coverage of a feature PRD
  by tickets can be derived rather than asserted (the groundwork for deriving
  a feature PRD's `implemented` status and a roadmap's delivery status).
- A repo adopting acs writes its PRD before its first ticket. A brownfield repo
  gets one from `/acs:create-prd`'s brownfield mode.
- Tickets minted before this change keep working; one without `features`
  cannot be broken down until it is linked (`acs.py ticket save`).
