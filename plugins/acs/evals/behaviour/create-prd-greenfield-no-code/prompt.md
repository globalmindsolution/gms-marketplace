---
description: >-
  /acs:create-prd greenfield: a repo with no code at all and every product
  fact supplied in the prompt, since the run cannot answer questions. It
  should write docs/product/prd.md with the eight required sections carrying
  exactly the stated facts, a roadmap mapping the two milestones to v0.1.0
  and v0.2.0, write no code, push its delivery branch, and report the failed
  gh PR step as a finding.
expected_outcome: >-
  docs/product/prd.md with the eight sections, the 500-bookings and 5%
  no-show metrics, the 2 s and 99.5% NFRs and the Won't item;
  docs/product/roadmap.md with a Release versions table mapping v0.1.0 and
  v0.2.0; no source file created; a task/EVAL-1-* branch pushed with upstream
  set; result.json records the gh failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-prd skill to define a brand-new product, groomr. Nothing
is built yet: this repo has no code. Everything the skill would elicit is
answered below. Treat all of it as confirmed and do not ask me anything.

- Vision: every independent dog groomer takes bookings online without phone
  tag.
- Problem statement: independent groomers lose hours a week to phone and text
  booking, and no-shows cost them about a fifth of their slots.
- Personas: Groomer (runs a one- or two-person salon, sets opening hours and
  services); Pet owner (books and reschedules appointments from a phone).
- Goals and success metrics: G1 online booking adoption, 500 bookings a week
  across all salons by 2027-03-31; G2 fewer no-shows, a no-show rate below 5%
  of appointments by 2027-06-30.
- Features (MoSCoW): Must: online booking (serves G1) and SMS reminders the day
  before (serves G2). Should: deposits at booking (serves G2). Could: a loyalty
  stamp card (serves G1). Won't: a marketplace ranking groomers against each
  other.
- Non-functional requirements: the booking page loads in under 2 s at p95 on
  a 4G phone; 99.5% monthly availability.
- Constraints and assumptions: EU customers only, so all personal data stays
  in an EU region under GDPR; SMS goes through a third-party SMS gateway.
- Out of scope: native mobile apps; payments beyond deposits.
- Roadmap: milestone "Booking MVP" delivers online booking and SMS reminders
  in release v0.1.0; milestone "Deposits" delivers deposits in release
  v0.2.0.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
