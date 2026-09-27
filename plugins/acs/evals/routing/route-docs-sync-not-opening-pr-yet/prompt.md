---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it talks about opening the pull request --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:docs-sync.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't open the pull request yet. First, TKT-27's branch changed the CSV delimiter to a semicolon and the export docs still say comma; fold the doc fix into that branch.
