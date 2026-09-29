---
description: >-
  Borrows the vocabulary of /acs:analyze-requirements on purpose -- it opens
  by saying the impact and acceptance criteria are already analyzed -- while
  the request still belongs to this skill. It tests that the description,
  not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:create-design.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

TKT-86's impact and acceptance criteria are already analyzed, and it came out design-significant with needs_design set. Now weigh the options for its retry queue and settle on one design for approval.
