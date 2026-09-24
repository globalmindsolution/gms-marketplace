---
description: >-
  Borrows the vocabulary of /acs:release on purpose -- it talks about cutting a release --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:merge-pr.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not cutting a release, just finish TKT-40's approved PR: merge it and move the ticket to done.
