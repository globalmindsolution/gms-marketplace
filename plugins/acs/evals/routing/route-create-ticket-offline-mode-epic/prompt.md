---
description: >-
  Borrows the vocabulary of /acs:breakdown-ticket on purpose -- it talks about breaking the work down --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:create-ticket.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Product wants a whole offline mode for the mobile app: sync, conflict handling, cached assets. It's too big for one task, so capture it as an epic we can break down later.
