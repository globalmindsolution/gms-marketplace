---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it talks about pushing and opening a PR --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:install-hooks.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I'm not ready to push or open a PR. Before I do, set things up so git itself validates my commit subjects and branch name on this clone.
