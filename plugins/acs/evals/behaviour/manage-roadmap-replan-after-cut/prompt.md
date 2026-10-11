---
description: >-
  /acs:manage-roadmap replan mode after a scope cut: the PRD already moved
  order tracking to Won't, and the approved roadmap still schedules it in its
  own v2.6.0 milestone. It should drop that milestone and its Release
  versions row, keep Storefront and Checkout byte-for-byte, bump the
  roadmap's version, leave the PRD untouched, and leave the roadmap as an
  uncommitted local change listed in states.files -- no ticket, branch,
  commit, push or PR (ADR-0127, ADR-0145).
expected_outcome: >-
  docs/product/roadmap.md without the Order tracking milestone or any
  v2.6.0, with the Storefront and Checkout milestones and rows unchanged, its
  front matter bumped from approved v1 to proposed v2; prd.md still approved
  v1; HEAD still the scaffold's commit on main and nothing pushed; the step
  finished with the roadmap in states.files and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:manage-roadmap skill to re-plan our roadmap. Leadership cut order
tracking last week and the PRD already says so, but the roadmap still has it.
I have already decided what changes; treat all of it as confirmed and do not
ask me anything:

- Remove the "Order tracking — v2.6.0" milestone and its v2.6.0 row.
- Version v2.6.0 is simply not used; nothing moves into it.
- Storefront (v2.4.0) and Checkout (v2.5.0) stay exactly as they are, word for
  word.
