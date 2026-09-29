---
description: >-
  Borrows the vocabulary of /acs:create-ticket on purpose -- it asks for
  tickets to be filed -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:run-e2e-tests.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Execute all the nightly suites now, file a regression ticket for each failure, and keep going until those are resolved.
