---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- it
  mentions C4 diagrams and architecture docs -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:create-prd.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Skip the C4 diagrams and architecture docs for now; those come later. First we need the product-level document: vision, personas, goals with success metrics, and a roadmap.
