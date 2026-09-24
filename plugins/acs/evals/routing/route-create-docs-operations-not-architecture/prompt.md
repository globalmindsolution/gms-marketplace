---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- it names
  the architecture set -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:create-docs.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Write the runbooks, the incident-response guide and the observability notes for our service — the operations set, not the architecture.
