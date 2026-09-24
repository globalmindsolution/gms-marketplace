---
description: >-
  Borrows the vocabulary of /acs:create-prd on purpose -- it names the PRD
  -- while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:create-requirements.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The PRD is fine as it is. What is missing is the detailed set underneath it: one file per functional feature, plus the non-functional items.
