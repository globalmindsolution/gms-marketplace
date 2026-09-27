---
description: >-
  Borrows the vocabulary of /acs:run-e2e-tests on purpose -- it asks for
  the test suite to be run -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:review-code.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't just run the tests on TKT-72. I want the changes themselves inspected for defects from several independent angles, with the build, lint and unit suite as the final gate.
