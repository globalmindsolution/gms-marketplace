---
description: >-
  Borrows the vocabulary of /acs:create-design on purpose -- it opens with
  an approved design -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:create-impl-plan.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The design for TKT-30 is approved. Now turn it into the concrete plan the executors will follow, with the file map and the test strategy.
