---
description: >-
  Borrows the vocabulary of /acs:create-impl-plan on purpose -- it talks about planning the implementation --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:breakdown-ticket.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

No implementation plan yet: TKT-22 is an epic, so first cut it into children, one per pull request, from its approved design.
