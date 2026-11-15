<!--
  prd-feature-default — built-in template of one feature's own PRD,
  `<prd_dir>/features/<slug>/prd.md` (ADR-0142, ADR-0147). /acs:create-prd starts
  each new feature PRD from it. The `## ` headings below — and only the `## `
  headings — are the contract: the feature_required_sections constraint is
  exactly this list, in this order, and prd_feature_check.py checks it. A repo
  replaces this template with its own `.acs/templates/prd-feature-default.md`;
  ITS headings are then the contract. Whatever the template, a feature PRD keeps
  a `## Requirements` section of `- **R<n>** — …` lines and a `## Goals served`
  section naming hub goals: tickets link `<slug>/R<n>` (ADR-0144) and a
  feature's implemented status is derived from them (ADR-0146). HTML comments
  are guidance and are not kept. The version front matter is written by
  `acs.py design init`, never by hand; the feature's MoSCoW priority lives in
  the hub's index only.
-->
# <Feature name>

## Summary

<!-- What the feature lets a user do, and why it matters — a short paragraph. -->

## Goals served

<!-- The hub goal ids this feature serves — the same set its index bullet names: "- G1 — <goal>". -->

## Requirements

<!-- One line per requirement, ids R1, R2, … each once and never reused:

- **R1** — <what the product must do, observable from outside>

Tickets link them as `<slug>/R<n>`. -->

## Acceptance criteria

<!-- Concrete and testable, each tracing to the R<n> ids: "Given …, when …, then … (R1)". -->

## Dependencies

<!-- Other features (by slug), services or decisions this feature needs; "None." when it needs none. A dependency orders the roadmap. -->

## Out of scope

<!-- What this feature deliberately does not do, beside the hub's Out of scope. -->
