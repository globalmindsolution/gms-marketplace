---
description: >-
  Borrows the vocabulary of /acs:create-impl-plan on purpose -- it talks
  about the implementation plan -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:create-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

It's too early for an implementation plan on TKT-79: it is flagged as needing a design and has none. Decide how tenant isolation should work, row-level versus schema-per-tenant, and get that approved first.
