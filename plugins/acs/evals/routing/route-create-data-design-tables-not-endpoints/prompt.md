---
description: >-
  Borrows the vocabulary of /acs:create-api-contract on purpose -- it
  talks about endpoints and payload shapes -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:create-data-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not the endpoints or payload shapes for TKT-58; those come later. What is needed now is what the shipments feature stores: its ERD, the tables with column types, indexes and constraints, and a migration outline.
