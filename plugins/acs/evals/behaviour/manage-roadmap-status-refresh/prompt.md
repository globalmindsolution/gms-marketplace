---
description: >-
  /acs:manage-roadmap status mode: the approved roadmap says every milestone
  is planned, but the Checkout milestone's epic EVAL-1 merged on main. It
  should run only `acs.py roadmap status --write` -- no subagent, no
  question, no version change -- so Checkout reads `delivered` in its Status
  line and its Release versions row while the other milestones stay
  `planned`, and leave the roadmap as an uncommitted local change listed in
  states.files (ADR-0127, ADR-0145).
expected_outcome: >-
  docs/product/roadmap.md with Checkout `delivered` in both places, Storefront
  and Order tracking still `planned`, front matter still approved v1; no
  Agent call; prd.md untouched; HEAD still the scaffold's commit and nothing
  pushed; the step finished with the roadmap in states.files and no PR.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:manage-roadmap skill with the argument `status`: where does each
milestone of our roadmap really stand? Refresh it from the tickets and do not
ask me anything.
