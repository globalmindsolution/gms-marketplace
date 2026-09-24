---
description: >-
  Borrows the vocabulary of /acs:project on purpose -- it is about a
  repo's tooling and CI -- while the request still belongs to this skill.
  It tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:setup.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't scaffold any tooling or restructure the repo. I only want acs's own conventions configured here, plus the CI check that every PR references its ticket.
