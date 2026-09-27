---
description: >-
  Borrows the vocabulary of /acs:create-prd on purpose -- it talks about the PRD and a feature in it --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:create-ticket.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Leave the PRD alone, the rate-limiting feature is already in it. I just need a trackable item for that work, traced back to the PRD feature.
