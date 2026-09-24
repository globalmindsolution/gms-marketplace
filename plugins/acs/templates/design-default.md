<!--
  design-default — built-in design template (the default create-design writes to
  <partition>/design.md). The `## ` headings below — and only the headings — are
  the enforcement contract: enforcement.design_sections defaults to exactly this
  list, in this order, and the create-design structure gate checks their presence
  and order. Fill each section from workspace state; the HTML-comment guidance is
  authoring help, not part of the gate.
-->
## Context & constraints

<!-- Problem, scope, assumptions; binding constraints from PRD/architecture/codebase; NFRs — security and performance REQUIRED, plus others that apply (availability, cost, operability, compliance). -->

## Options considered

<!-- >= 2 real options (### Option A/B/...), each with how it works and explicit trade-offs (pros/cons vs. the NFRs and constraints). No strawmen. -->

## Decision & rationale

<!-- The chosen option, why it wins, why the others lose. One-line decision statement first — it becomes states.decision. -->

## Architecture

<!-- Components (new/changed, mapped to the C4 container/component views), interfaces/contracts (signatures, payloads, error shapes), data model changes (Mermaid ER when entities change), and Mermaid sequence diagrams for every new or changed runtime flow. Include an ### Architecture conformance subsection. -->

## Impact & risks

<!-- Blast radius, affected tickets/components, risks with mitigations. -->

## Rollout/migration

<!-- Ordering, data/schema migration, feature flags, backward compatibility, rollback plan (or "single-step deploy, no migration" with justification). -->
