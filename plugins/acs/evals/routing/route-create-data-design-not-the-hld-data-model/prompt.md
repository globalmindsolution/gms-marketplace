---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- it
  mentions the HLD's conceptual data model -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:create-data-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Leave the product-wide conceptual data model in the HLD as it is. For TKT-102 only, detail the orders feature's entities with their attributes and keys, and its physical tables and indexes, in that feature's low-level design.
