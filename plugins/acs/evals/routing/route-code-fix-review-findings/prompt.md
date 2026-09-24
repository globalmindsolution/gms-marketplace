---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- it starts from a
  review verdict -- while the request still belongs to this skill. It tests
  that the description, not a keyword, decides the route. Never names the
  skill.
expected_outcome: Routes to acs:code.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The review of TKT-12 came back with two blocking findings in verdict.json. Fix them on the ticket branch.
