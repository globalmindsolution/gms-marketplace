---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- it
  mentions the product-wide architecture set and its LLD contracts -- while
  the request still belongs to this skill. It tests that the description,
  not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:create-api-contract.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Leave the product-wide architecture and its LLD contracts alone. For TKT-74 only, spec out the three new /subscriptions endpoints its plan adds: shapes, error codes, examples.
