---
description: >-
  EVAL-1 is an epic (card checkout, needs_design true) with no design and no
  children. Asked to ship it, /acs:ship meets the epic brake on its first
  step and must surface the Design-phase path verbatim (create-tech-design, then
  create-ticket --fan-out, then ship each child) and stop: no step recorded,
  no design written, no child minted, no code touched.
expected_outcome: >-
  No step state exists under runs/EVAL-1/steps/; no second ticket was minted;
  src/shop/__init__.py has no checkout code; the reply points at
  /acs:create-tech-design EVAL-1 and the --fan-out children.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Use the /acs:ship skill to ship ticket EVAL-1 end to end, up to its pull
request. Where a step would ask me something, decide it yourself and record
it as an assumption. Do not ask me anything; I will not be able to answer.
