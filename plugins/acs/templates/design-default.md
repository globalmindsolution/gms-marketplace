<!--
  design-default — built-in tech design template (the default create-tech-design
  writes as tech-design.md, ADR-0135). The `## ` headings below — and only the
  `## ` headings — are the enforcement contract: the required_sections constraint
  is exactly this list, in this order, and the create-tech-design structure gate
  checks their presence and order. Fill each section from workspace state; a
  section a story does not need reads "n/a — <why>". The HTML-comment guidance
  and the `### ` subsections are authoring help the reviewer checks, not part of
  the structure gate. The version front matter is written by `acs.py design
  init`, never by hand.
-->
## Decision & options

<!-- The one-line decision statement first — it becomes states.decision. Then ### Context (problem, scope, assumptions, binding constraints), ### Options considered (>= 2 real options per major decision, #### Option A/B/..., each with how it works and explicit trade-offs — no strawmen), ### Rationale and ### Decision records. -->

## HLD views affected

<!-- One entry per hld/ view the change touches: a link with its version and status, a snapshot excerpt of the part touched, and "conforms — no change" or the exact change it needs. -->

## LLD

<!-- One line naming the feature's LLD folder, then the four subsections: snapshots of the feature's living documents this change touches, each linked with its version and status — or "none yet — run /acs:create-…". -->

### API

### Data

### Flows

### Components

## NFRs

<!-- Security and performance REQUIRED, concretely; plus others that apply (availability, cost, operability, compliance). -->

## Risks

<!-- Blast radius, affected tickets/components, risks with mitigations, and ### Rollout & migration: ordering, data/schema migration, feature flags, backward compatibility, rollback plan. -->

## Open questions

<!-- What the team should settle at review, each with its options and ledger entry — or "none". -->
