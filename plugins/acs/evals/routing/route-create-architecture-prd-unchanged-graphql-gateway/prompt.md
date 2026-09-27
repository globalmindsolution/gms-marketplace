---
description: >-
  Borrows the vocabulary of /acs:create-prd on purpose -- it talks about the
  PRD and product vision -- while the request still belongs to this skill.
  It tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:create-architecture.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Leave the PRD as it is; the product vision hasn't changed. What is out of date is the system-level docs: redo the C4 views and LLD flows now that we added a GraphQL gateway.
