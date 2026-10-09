# 0144 — Product tickets are made from the PRD and link it

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

1. **Product work links the PRD.** An epic, a story or a bug carries
   `features` (at least one feature slug, whose own PRD exists and is not
   `deprecated`) and `requirements` (`<slug>/R<n>`, each a requirement its
   feature's PRD declares). A story names at least one requirement; an epic or
   a bug names the ones it delivers or fixes. In a repo with no PRD, none of
   them is minted: the run points at `/acs:create-prd`.
2. **A technical task may link nothing.** A task — a CI upgrade, a refactor, a
   dependency bump — is work no user sees and needs neither a link nor a PRD;
   what a task does link must resolve like any other link. Relabelling
   user-facing work a task to escape the rule is a reviewer finding.
3. **Product work beyond the PRD is not minted.** The run ends `failed` and
   points at a PRD amendment; the ticket is created from the amended PRD.
   `prd_trace.divergence` stays in the result schema and is always `null`.
4. **Enforced in code, not at a pre-gate.** The ticket's type is decided after
   `/acs:create-ticket` starts, so no gate refuses the start. `acs_lib.prd_link`
   holds the rule; `acs.py ticket link-check` judges a draft (the authors and
   the reviewer run it); `post-create-ticket` refuses a completed run whose
   ticket does not link the PRD as its type requires; `new-ticket.py
   --require-prd-link`, which `/acs:breakdown-ticket` passes for each child,
   refuses before an id is spent; `acs.py ticket save` refuses a
   `requirements` patch that does not resolve, whoever sends it.
5. **The id allocator stays neutral.** Without `--require-prd-link`,
   `new-ticket.py` mints as before — the regression bug `/acs:run-e2e-tests`
   files for a red suite needs no PRD link — but a requirement it is given
   must still resolve.

## Consequences

- A ticket says which requirements it delivers, so coverage of a feature PRD
  by tickets can be derived rather than asserted (the groundwork for deriving
  a feature PRD's `implemented` status and a roadmap's delivery status).
- A repo adopting acs writes its PRD before its first product ticket (a
  brownfield repo gets one from `/acs:create-prd`'s brownfield mode); technical
  tasks can be filed from day one.
- Tickets minted before this change keep working; a child minted from an
  unlinked parent must be a task, or be linked when it is minted.
