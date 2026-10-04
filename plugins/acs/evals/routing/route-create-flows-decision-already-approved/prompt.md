---
description: >-
  Borrows the vocabulary of /acs:create-design on purpose -- it talks
  about the design decision and its options -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:create-flows.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The design decision for TKT-57 is already approved, so there are no more options to weigh. Now document the chosen approach's runtime interactions as sequence diagrams and the export job's lifecycle as a state machine.
