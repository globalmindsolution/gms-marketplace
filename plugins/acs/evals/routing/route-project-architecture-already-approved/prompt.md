---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- it talks about the approved architecture set --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:project.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The architecture set is already approved, so don't regenerate it. Use it to scaffold the empty repo: layout, build config, tests, lint and a minimal green slice.
