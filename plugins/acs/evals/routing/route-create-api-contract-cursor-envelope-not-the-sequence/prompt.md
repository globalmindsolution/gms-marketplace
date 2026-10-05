---
description: >-
  Borrows the vocabulary of /acs:create-flows on purpose -- it talks about
  the sequence of calls between the client, the API and the database --
  while the request still belongs to this skill: the request and response
  shapes, not the order of calls. It tests that the description, not a
  keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:create-api-contract.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not the sequence of calls between the client, the API and the database for TKT-69 -- that diagram comes later. TKT-69 switches /customers from offset to cursor pagination: design the new query parameters and response envelope, the errors, and how existing offset clients stay compatible.
