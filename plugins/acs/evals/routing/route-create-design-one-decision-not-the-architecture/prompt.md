---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- it
  mentions the architecture -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:create-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Leave the architecture docs alone. For TKT-20 only, decide between event sourcing and a plain audit table, weigh the trade-offs, and record the chosen design for approval.
