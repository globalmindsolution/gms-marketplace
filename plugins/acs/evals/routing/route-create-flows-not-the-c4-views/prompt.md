---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- it
  mentions the C4 views and the integration map -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:create-flows.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not the product-wide C4 views or the integration map; leave the HLD alone. For TKT-102, draw the orders feature's own sequence diagrams and the order's state machine in its low-level design folder.
