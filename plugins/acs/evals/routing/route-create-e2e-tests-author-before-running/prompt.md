---
description: >-
  Borrows the vocabulary of /acs:run-e2e-tests on purpose -- it talks about
  running suites -- while the request still belongs to this skill. It tests
  that the description, not a keyword, decides the route. Never names the
  skill.
expected_outcome: Routes to acs:create-e2e-tests.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't run anything yet — the end-to-end suites for TKT-8's checkout cases have not been written. Author them first.
