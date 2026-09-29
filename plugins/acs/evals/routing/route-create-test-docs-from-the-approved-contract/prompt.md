---
description: >-
  Borrows the vocabulary of /acs:create-api-contract on purpose -- it
  opens on the API contract and its error codes -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:create-test-docs.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

TKT-82's API contract is written and approved, every endpoint and error code. Use it and the plan to derive the test cases, including one for each documented error response.
