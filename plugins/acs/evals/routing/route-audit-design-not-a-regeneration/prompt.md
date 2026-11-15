---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- the HLD,
  its containers, APIs and data stores -- while the request still belongs to
  this skill: it rules out rewriting the docs and asks only where they are
  wrong about the code. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:audit-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't regenerate or rewrite the architecture docs. I only want to know where the HLD is wrong about today's code -- which containers, APIs and data stores it gets wrong or misses -- so we can decide what to fix.
