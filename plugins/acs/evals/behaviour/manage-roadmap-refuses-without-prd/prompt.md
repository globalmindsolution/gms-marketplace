---
description: >-
  /acs:manage-roadmap refusal: the repo has no PRD, so there are no features
  to schedule. It should write no roadmap, finish its run `failed` through
  the post-hook, and point the user at /acs:create-prd, without inventing
  milestones (ADR-0145).
expected_outcome: >-
  No docs/product/roadmap.md or any other document written; the step finished
  `failed` in state.json; nothing committed or pushed; a reply that says
  there is no PRD and points at /acs:create-prd.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:manage-roadmap skill to plan the roadmap for this repo: a
checkout milestone in v2.5.0 and order tracking in v2.6.0. Do not ask me
anything.
