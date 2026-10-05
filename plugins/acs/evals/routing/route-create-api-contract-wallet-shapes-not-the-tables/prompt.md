---
description: >-
  Borrows the vocabulary of /acs:create-data-design on purpose -- it talks
  about the tables, columns and indexes behind the feature -- while the
  request still belongs to this skill: the interface, not what is stored. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:create-api-contract.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The tables, columns and indexes behind TKT-55's wallet balance are already designed. The iOS team is blocked on the /v2/wallet/balance endpoint itself: they need its exact JSON shapes, status codes and a sample response before anyone builds it.
