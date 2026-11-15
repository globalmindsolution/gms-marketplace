---
description: >-
  Borrows the vocabulary of /acs:create-ticket on purpose -- it talks about creating tickets --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:breakdown-ticket.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't capture anything new. Take the existing epic TKT-60 and carve it into child tickets the team can pick up, each with its own acceptance criteria.
