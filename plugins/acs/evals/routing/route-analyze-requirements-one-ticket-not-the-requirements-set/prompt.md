---
description: >-
  Borrows the vocabulary of /acs:create-requirements on purpose -- it
  mentions the product-wide requirements docs -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:analyze-requirements.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not the product-wide requirements docs, just TKT-88: restate what it asks, list its assumptions and risks, and propose refined acceptance criteria before it is planned.
