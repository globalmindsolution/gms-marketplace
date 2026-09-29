---
description: >-
  Borrows the vocabulary of /acs:code on purpose -- it talks about implementing the ticket --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:handoff.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't keep coding, TKT-12's implementation can wait. Pause the run where it is, save the context, and give me the line to pick it up in a new session.
