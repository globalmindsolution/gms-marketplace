<!--
  prd-default — built-in template of the PRD hub, `<prd_dir>/prd.md` (ADR-0142,
  ADR-0147). /acs:create-prd starts a new hub from it. The `## ` headings below
  — and only the `## ` headings — are the contract: the required_sections
  constraint is exactly this list, in this order, and the structure floor checks
  their presence, order and that none is empty. A repo replaces this template
  with its own `.acs/templates/prd-default.md`; then ITS headings are the
  contract. HTML comments are authoring guidance and are not kept in the
  document. The version front matter is written by `acs.py design init`, never
  by hand. The hub holds what is true of the whole product; what is true of one
  feature goes in that feature's own PRD (prd-feature-default).
-->
# PRD — <product>

## Vision

<!-- One tight paragraph: what the product is, for whom, and why it wins. -->

## Problem statement

<!-- The user and business pain, grounded in evidence (interviews, metrics, the code as built in a brownfield repo). Who has it, how often, what it costs them. -->

## Target users & personas

<!-- One bullet per persona: **Name** — who they are, their goals and frustrations. -->

## Goals & success metrics

<!-- Ids G1, G2, … Every goal has at least one MEASURABLE metric: value + unit + timeframe ("500 bookings a week by 2027-03-31"). "Improve UX" is not a metric. A table works well:

| Goal | Metric |
|---|---|
| G1 <goal> | <value + unit + timeframe> |
-->

## Features (prioritized)

<!-- The index of the feature PRDs, grouped MoSCoW under ### Must have, ### Should have, ### Could have, ### Won't have. One bullet per feature linking its own PRD and naming the goals it serves:

- [Online booking](features/online-booking/prd.md) — pet owners book a slot (supports G1)

A goal no feature serves gets an explicit deferral note. Never restate a feature's requirements here: they live in its PRD. When and in which release each feature ships is the roadmap's (/acs:manage-roadmap). -->

## Non-functional requirements

<!-- Product-wide NFRs, each concrete enough to verify: "the booking page loads in under 2 s at p95 on a 4G phone". -->

## Constraints & assumptions

<!-- Technical, legal, budget and timeline constraints; the assumptions the plan rests on. -->

## Out of scope

<!-- Explicit non-goals, so downstream skills can flag divergence. -->
