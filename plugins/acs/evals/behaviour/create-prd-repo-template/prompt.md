---
description: >-
  /acs:create-prd greenfield in a repo that keeps its own feature PRD
  template (ADR-0147): .acs/templates/prd-feature-default.md adds a
  `## Rollout` section. Every feature PRD it writes should carry the
  template's seven sections in order -- Rollout included, filled from the
  stated rollout plan -- while the hub keeps the built-in eight; nothing
  committed, pushed or opened.
expected_outcome: >-
  docs/product/prd.md with the eight built-in hub sections; each of
  docs/product/features/online-booking/prd.md and sms-reminders/prd.md with
  Summary, Goals served, Requirements, Acceptance criteria, Dependencies,
  Rollout and Out of scope in that order, its Rollout naming the stated plan;
  HEAD still the scaffold's commit; the step finished with the documents in
  states.files and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-prd skill to define a brand-new product, groomr. Nothing
is built yet. Everything the skill would elicit is answered below; treat all
of it as confirmed and do not ask me anything. Use our team's PRD templates.

- Vision: every independent dog groomer takes bookings online without phone
  tag.
- Problem statement: groomers lose hours a week to phone booking, and
  no-shows cost them about a fifth of their slots.
- Personas: Groomer (runs a small salon); Pet owner (books from a phone).
- Goals and success metrics: G1 500 bookings a week across all salons by
  2027-03-31; G2 a no-show rate below 5% of appointments by 2027-06-30.
- Features (MoSCoW): Must: online booking (serves G1) and SMS reminders the
  day before (serves G2). Won't: a marketplace ranking groomers.
- Feature slugs: online-booking, sms-reminders.
- Rollout: online booking goes to a beta group of 20 salons first; SMS
  reminders ship behind a feature flag, switched on salon by salon.
- Non-functional requirements: the booking page loads in under 2 s at p95;
  99.5% monthly availability.
- Constraints and assumptions: EU customers only, data stays in the EU.
- Out of scope: native mobile apps; payments.
