---
description: >-
  Borrows the vocabulary of /acs:code on purpose -- it is about the changes
  on a branch -- while the request still belongs to this skill. It tests
  that the description, not a keyword, decides the route. Never names the
  skill.
expected_outcome: Routes to acs:review-code.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't change anything. Just examine what's on this branch against main and tell me what's wrong with it.
