---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- it asks for a
  pull request -- while the request still belongs to this skill. It tests
  that the description, not a keyword, decides the route. Never names the
  skill.
expected_outcome: Routes to acs:ship.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I don't want just the PR step: TKT-77 hasn't been analyzed or planned yet. Take it through every stage so it ends with an open pull request.
