---
description: >-
  Borrows the vocabulary of /acs:create-data-design on purpose -- it
  mentions the ERD and the table schema -- while the request still belongs
  to this skill. It tests that the description, not a keyword, decides the
  route. Never names the skill.
expected_outcome: Routes to acs:create-flows.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

TKT-58's ERD and table schema are already written. What is missing is the behaviour: the sequence of calls for creating and cancelling a shipment, and the shipment's state transitions.
