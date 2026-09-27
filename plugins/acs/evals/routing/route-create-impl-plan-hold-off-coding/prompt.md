---
description: >-
  Borrows the vocabulary of /acs:code on purpose -- it talks about coding
  and implementation -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:create-impl-plan.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Hold off on writing any code for TKT-85. First I need the plan the implementation will follow: files to change, which executor owns each, and the tests to run.
