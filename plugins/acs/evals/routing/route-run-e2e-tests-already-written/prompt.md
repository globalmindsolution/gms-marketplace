---
description: >-
  Borrows the vocabulary of /acs:create-e2e-tests on purpose -- it mentions
  suites that were written -- while the request still belongs to this skill.
  It tests that the description, not a keyword, decides the route. Never
  names the skill.
expected_outcome: Routes to acs:run-e2e-tests.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The end-to-end suites for TKT-8 are already written. Execute them now and report which cases fail.
