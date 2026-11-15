---
description: >-
  /acs:create-prd amend mode after a scope change: leadership cut order
  tracking, which the existing PRD lists as a Should-have and the roadmap
  schedules in its own v2.6.0 milestone. It should run ticketless, move order
  tracking to Won't and Out of scope, leave every other section and every
  feature PRD byte-for-byte (the cut feature keeps its link and its
  document), leave roadmap.md untouched -- it is /acs:manage-roadmap's
  (ADR-0145), and the reply points there -- and leave the PRD as an
  uncommitted local change listed in states.files -- no ticket, branch,
  commit, push or PR (ADR-0127).
expected_outcome: >-
  docs/product/prd.md lists order tracking under Won't and Out of scope, with
  Vision through Goals and the NFR and Constraints sections unchanged, its
  front matter bumped from approved v1 to proposed v2; docs/product/roadmap.md
  and every feature PRD stay approved v1, the roadmap still carrying its
  v2.6.0 milestone; HEAD is still the scaffold's last commit on main and
  nothing was pushed; the step finished with prd.md, not roadmap.md, in
  states.files and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-prd skill with the argument `cut order tracking from
scope` to amend our PRD. Leadership cut order tracking this week. I have
already decided exactly what changes; treat all of it as confirmed and do not
ask me anything:

- Features (prioritized): order tracking moves from Should to Won't.
- Out of scope: add order tracking.
- Nothing else changes: every other section of the PRD stays exactly as it
  is, word for word.
