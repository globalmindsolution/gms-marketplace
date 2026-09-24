---
description: >-
  Borrows the vocabulary of /acs:run-e2e-tests on purpose -- it talks
  about running suites -- while the request still belongs to this skill.
  It tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:create-test-docs.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

There's nothing to run for TKT-75 yet — no suite has anything for it. First decide what should be tested: derive its test cases from the acceptance criteria and give each a target suite.
