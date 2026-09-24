---
description: >-
  Borrows the vocabulary of /acs:create-impl-plan on purpose -- it says
  "implementation plan" -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:analyze-requirements.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

TKT-9 is still vague, so hold off on any implementation plan. First restate what it asks for, map its impact, list the risks and assumptions, and say whether it needs a design.
