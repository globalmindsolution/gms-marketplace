---
description: >-
  Borrows the vocabulary of /acs:create-docs on purpose -- it names the
  runbooks and coding standards -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:create-architecture.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not the runbooks or the coding standards, those come later. First we need the product's C4 high-level design and low-level flows written up from the PRD and the repo.
