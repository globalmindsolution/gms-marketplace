---
description: >-
  Borrows the vocabulary of /acs:create-design on purpose -- it opens by
  saying the design is settled -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:create-api-contract.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The design for TKT-5 is settled. What is missing is the precise request and response spec for the new /refunds endpoints, with examples and error codes.
